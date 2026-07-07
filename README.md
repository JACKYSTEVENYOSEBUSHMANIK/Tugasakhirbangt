# BLE Room Positioning System (IPS) v2.0 - Service Manager Guide

Panduan untuk menjalankan, menghentikan, dan memulai ulang layanan Backend (Flask API) dan Frontend (React Vite) secara otomatis pada Windows menggunakan file `server.bat` / `server.ps1`.

---

## 🛠️ Perintah Utama (CMD / PowerShell)

Buka terminal (Command Prompt atau PowerShell) di direktori root project, lalu jalankan perintah berikut:

### 1. Memulai Layanan (Start)
Menjalankan backend Flask pada port **5000** dan frontend React Vite pada port **3000** di latar belakang.
```bash
# Menggunakan Batch Script (CMD)
.\server.bat start

# Menggunakan PowerShell
.\server.ps1 start
```

### 2. Menghentikan Layanan (Stop)
Menghentikan semua proses backend & frontend dan menutup port 5000 & 3000 dengan aman.
```bash
# Menggunakan Batch Script (CMD)
.\server.bat stop

# Menggunakan PowerShell
.\server.ps1 stop
```

### 3. Memulai Ulang Layanan (Restart)
Melakukan `stop` lalu `start` kembali secara berurutan. Sangat berguna setelah mengubah kode backend/database yang membutuhkan restart server.
```bash
# Menggunakan Batch Script (CMD)
.\server.bat restart

# Menggunakan PowerShell
.\server.ps1 restart
```

### 4. Memeriksa Status Layanan (Status)
Melihat apakah backend dan frontend sedang berjalan beserta PID (Process ID) masing-masing.
```bash
# Menggunakan Batch Script (CMD)
.\server.bat status

# Menggunakan PowerShell
.\server.ps1 status
```

---

## 📂 Lokasi Log & File Temp
Proses dijalankan secara hidden di latar belakang. Anda dapat memantau log stdout/stderr server pada folder `.server/` di root direktori:

*   **Log Backend:**
    *   Stdout: `.server\backend.stdout.log`
    *   Stderr: `.server\backend.stderr.log`
*   **Log Frontend:**
    *   Stdout: `.server\frontend.stdout.log`
    *   Stderr: `.server\frontend.stderr.log`
*   **File PID (Process ID):**
    *   `.server\backend.pid`
    *   `.server\frontend.pid`
