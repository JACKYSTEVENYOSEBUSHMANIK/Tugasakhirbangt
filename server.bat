@echo off
rem Wrapper to run the powershell service manager from CMD or run commands
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0server.ps1" %*
