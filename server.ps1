[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('start', 'stop', 'restart', 'status')]
    [string]$Action = 'status'
)

$ErrorActionPreference = 'Stop'

$RootDir = $PSScriptRoot
$BackendDir = Join-Path $RootDir 'backend'
$FrontendDir = Join-Path $RootDir 'frontend'
$RuntimeDir = Join-Path $RootDir '.server'
$BackendPidFile = Join-Path $RuntimeDir 'backend.pid'
$FrontendPidFile = Join-Path $RuntimeDir 'frontend.pid'
$BackendPython = Join-Path $BackendDir '.venv\Scripts\python.exe'
$RequirementsFile = Join-Path $BackendDir 'requirements.txt'
$RequirementsHashFile = Join-Path $BackendDir '.venv\.requirements.sha256'

function Ensure-RuntimeDirectory {
    if (-not (Test-Path -LiteralPath $RuntimeDir)) {
        New-Item -ItemType Directory -Path $RuntimeDir | Out-Null
    }
}

function Get-SavedProcess {
    param([string]$PidFile)

    if (-not (Test-Path -LiteralPath $PidFile)) {
        return $null
    }

    $savedPid = Get-Content -LiteralPath $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not ($savedPid -as [int])) {
        Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
        return $null
    }

    $process = Get-Process -Id ([int]$savedPid) -ErrorAction SilentlyContinue
    if (-not $process) {
        Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
        return $null
    }

    return $process
}

function Stop-SavedProcess {
    param(
        [string]$Name,
        [string]$PidFile
    )

    $process = Get-SavedProcess -PidFile $PidFile
    if (-not $process) {
        Write-Host "$Name is not running."
        return
    }

    Write-Host "Stopping $Name (PID $($process.Id))..."
    & taskkill.exe /PID $process.Id /T /F | Out-Null
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
}

function Stop-PortListener {
    param(
        [string]$Name,
        [int]$Port
    )

    $listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($listener in $listeners) {
        # These ports are reserved by this project. Killing by listener PID also
        # handles Flask's debug child process and old runs without PID files.
        Write-Host "Stopping $Name listener on port $Port (PID $($listener.OwningProcess))..."
        & taskkill.exe /PID $listener.OwningProcess /T /F | Out-Null
    }
}

function Test-Port {
    param([int]$Port)

    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Wait-ForPort {
    param(
        [int]$Port,
        [int]$TimeoutSeconds = 20
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Port -Port $Port) {
            return $true
        }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Wait-ForPortClosed {
    param(
        [int]$Port,
        [int]$TimeoutSeconds = 10
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (-not (Test-Port -Port $Port)) {
            return $true
        }
        Start-Sleep -Milliseconds 250
    }
    return $false
}

function Ensure-BackendVenv {
    if (-not (Test-Path -LiteralPath $BackendPython)) {
        Write-Host 'Creating backend virtual environment...'

        $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
        if ($launcher) {
            & $launcher.Source -3 -m venv (Join-Path $BackendDir '.venv')
        }
        else {
            $python = Get-Command python.exe -ErrorAction Stop
            & $python.Source -m venv (Join-Path $BackendDir '.venv')
        }

        if ($LASTEXITCODE -ne 0) {
            throw 'Failed to create the backend virtual environment.'
        }
    }

    $currentHash = (Get-FileHash -LiteralPath $RequirementsFile -Algorithm SHA256).Hash
    $installedHash = if (Test-Path -LiteralPath $RequirementsHashFile) {
        Get-Content -LiteralPath $RequirementsHashFile -ErrorAction SilentlyContinue | Select-Object -First 1
    }
    else {
        $null
    }

    if ($currentHash -ne $installedHash) {
        Write-Host 'Installing backend dependencies into .venv...'
        & $BackendPython -m pip install -r $RequirementsFile
        if ($LASTEXITCODE -ne 0) {
            throw 'Failed to install backend dependencies.'
        }
        Set-Content -LiteralPath $RequirementsHashFile -Value $currentHash
    }
}

function Start-Servers {
    Ensure-RuntimeDirectory

    if ((Get-SavedProcess -PidFile $BackendPidFile) -or (Test-Port -Port 5000)) {
        throw 'Backend or another process is already using port 5000. Run .\server.ps1 stop first.'
    }
    if ((Get-SavedProcess -PidFile $FrontendPidFile) -or (Test-Port -Port 3000)) {
        throw 'Frontend or another process is already using port 3000. Run .\server.ps1 stop first.'
    }

    Ensure-BackendVenv

    if (-not (Test-Path -LiteralPath (Join-Path $FrontendDir 'node_modules'))) {
        Write-Host 'Installing frontend dependencies...'
        Push-Location $FrontendDir
        try {
            & npm.cmd install
            if ($LASTEXITCODE -ne 0) {
                throw 'Failed to install frontend dependencies.'
            }
        }
        finally {
            Pop-Location
        }
    }

    Write-Host 'Starting backend on http://0.0.0.0:5000 ...'
    $backendProcess = Start-Process `
        -FilePath $BackendPython `
        -ArgumentList 'app.py' `
        -WorkingDirectory $BackendDir `
        -RedirectStandardOutput (Join-Path $RuntimeDir 'backend.stdout.log') `
        -RedirectStandardError (Join-Path $RuntimeDir 'backend.stderr.log') `
        -WindowStyle Hidden `
        -PassThru
    Set-Content -LiteralPath $BackendPidFile -Value $backendProcess.Id

    Write-Host 'Starting frontend on http://0.0.0.0:3000 ...'
    $frontendProcess = Start-Process `
        -FilePath 'npm.cmd' `
        -ArgumentList @('run', 'dev', '--', '--host', '0.0.0.0', '--port', '3000') `
        -WorkingDirectory $FrontendDir `
        -RedirectStandardOutput (Join-Path $RuntimeDir 'frontend.stdout.log') `
        -RedirectStandardError (Join-Path $RuntimeDir 'frontend.stderr.log') `
        -WindowStyle Hidden `
        -PassThru
    Set-Content -LiteralPath $FrontendPidFile -Value $frontendProcess.Id

    $backendReady = Wait-ForPort -Port 5000
    $frontendReady = Wait-ForPort -Port 3000

    if (-not $backendReady -or -not $frontendReady) {
        Write-Warning 'One or more servers did not become ready. Check the logs in .server\.'
        Show-Status
        return
    }

    Write-Host 'Servers started successfully.' -ForegroundColor Green
    Show-Status
}

function Stop-Servers {
    Ensure-RuntimeDirectory
    Stop-SavedProcess -Name 'frontend' -PidFile $FrontendPidFile
    Stop-SavedProcess -Name 'backend' -PidFile $BackendPidFile
    Stop-PortListener -Name 'frontend' -Port 3000
    Stop-PortListener -Name 'backend' -Port 5000

    $frontendStopped = Wait-ForPortClosed -Port 3000
    $backendStopped = Wait-ForPortClosed -Port 5000
    if (-not $frontendStopped -or -not $backendStopped) {
        throw 'A server port is still active after stop. Run PowerShell as Administrator and try again.'
    }
}

function Show-Status {
    $backendProcess = Get-SavedProcess -PidFile $BackendPidFile
    $frontendProcess = Get-SavedProcess -PidFile $FrontendPidFile
    $backendListening = Test-Port -Port 5000
    $frontendListening = Test-Port -Port 3000

    $backendState = if ($backendProcess -and $backendListening) {
        "running (PID $($backendProcess.Id), port 5000)"
    }
    elseif ($backendListening) {
        'running (unmanaged process on port 5000)'
    }
    else {
        'stopped'
    }

    $frontendState = if ($frontendProcess -and $frontendListening) {
        "running (PID $($frontendProcess.Id), port 3000)"
    }
    elseif ($frontendListening) {
        'running (unmanaged process on port 3000)'
    }
    else {
        'stopped'
    }

    Write-Host "Backend : $backendState"
    Write-Host "Frontend: $frontendState"
}

switch ($Action) {
    'start' {
        Start-Servers
    }
    'stop' {
        Stop-Servers
        Show-Status
    }
    'restart' {
        Stop-Servers
        Start-Servers
    }
    'status' {
        Ensure-RuntimeDirectory
        Show-Status
    }
}
