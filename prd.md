# PRD - Indoor Positioning System (IPS)
## Pengembangan Fitur Lanjutan: Otomatisasi & Inteligensi Sistem

**Versi:** 2.0
**Status:** Draft
**Tanggal:** 6 Juli 2026

---

## 1. Latar Belakang

Sistem IPS berbasis BLE (ESP32) dan trilaterasi sinyal saat ini telah berjalan, namun memiliki tiga kelemahan operasional utama:

1. **Akurasi tidak stabil** — sinyal BLE mudah terganggu oleh dinding/sekat, dan kalibrasi parameter trilaterasi masih manual (memerlukan flash ulang firmware ESP32).
2. **Beban database berlebihan** — pelacakan posisi berjalan 24 jam nonstop tanpa mempertimbangkan jam kerja petugas, membebani Neon DB secara tidak perlu.
3. **Pertumbuhan data tak terkendali** — data koordinat masuk setiap detik ke tabel `log_pergerakan`, menyebabkan pembengkakan storage tanpa mekanisme pembersihan otomatis.

Dokumen ini menjabarkan kebutuhan produk untuk mengatasi ketiga masalah tersebut melalui otomatisasi kalibrasi, integrasi manajemen shift, dan efisiensi database (data pruning).

---

## 2. Tujuan (Goals)

| # | Tujuan | Metrik Keberhasilan |
|---|--------|----------------------|
| 1 | Mempermudah kalibrasi sinyal RSSI tanpa flash ulang ESP32 | Kalibrasi selesai < 1 menit per node via web |
| 2 | Mengurangi beban tracking di luar jam kerja | Penurunan volume insert data ke `log_pergerakan` saat di luar shift ≥ 90% |
| 3 | Menjaga ukuran database tetap efisien | Data mentah > 30 hari otomatis terhapus, digantikan ringkasan agregat |
| 4 | Meningkatkan akuntabilitas kerja petugas | Tersedia data pencocokan tugas vs lokasi aktual |
| 5 | Deteksi dini gangguan sinyal | Notifikasi otomatis saat terjadi interferensi sinyal signifikan |

## 3. Non-Goals (Di Luar Cakupan)

- Tidak membahas perubahan hardware ESP32 (hanya interaksi via web).
- Tidak mencakup penggantian metode trilaterasi (tetap menggunakan RSSI-based trilateration).
- Tidak mencakup modul payroll/absensi penuh (hanya terintegrasi sebatas shift & tracking).

---

## 4. Modul & Daftar Fitur

### 4.1 Modul Kalibrasi & Manajemen Sinyal

#### F1 — ESP32 Signal Calibrator Tool
- **Deskripsi:** Admin meletakkan perangkat pada jarak tepat 1 meter dari node ESP32, lalu menekan tombol "Kalibrasi" di web. Sistem menghitung nilai `P_tx` (RSSI pada jarak 1 meter) secara otomatis dan menyimpannya ke database.
- **User story:** Sebagai admin, saya ingin mengkalibrasi sinyal langsung dari web agar tidak perlu membongkar/flash ulang firmware ESP32.
- **Kebutuhan data:** Kolom `p_tx`, `faktor_n` pada tabel `node_esp32`.
- **Kriteria penerimaan:**
  - Tombol "Kalibrasi" memicu pembacaan RSSI real-time dari node terpilih.
  - Nilai `P_tx` tersimpan otomatis setelah proses selesai.
  - Riwayat kalibrasi dapat dilihat (opsional: log waktu & nilai lama vs baru).

#### F2 — Signal Loss & Interference Detector
- **Deskripsi:** Grafik pemantauan kestabilan RSSI. Jika sinyal turun drastis padahal petugas tidak bergerak, sistem memberi peringatan adanya kemungkinan interferensi (misal penghalang baru).
- **User story:** Sebagai admin, saya ingin mendapat notifikasi otomatis saat ada anomali sinyal agar bisa menyelidiki penyebabnya.
- **Kriteria penerimaan:**
  - Grafik RSSI per node ditampilkan secara time-series.
  - Threshold penurunan sinyal dapat dikonfigurasi.
  - Notifikasi/alert muncul di dashboard saat anomali terdeteksi.

### 4.2 Modul Operasional & SDM (Shift & Penugasan)

#### F3 — Manajemen Shift & Jadwal Petugas
- **Deskripsi:** Admin dapat mengatur jadwal kerja (Shift Pagi, Siang, Malam) dan menautkannya ke masing-masing petugas.
- **Kebutuhan data:** Tabel baru `shift_kerja` (`id_shift`, `nama_shift`, `jam_mulai`, `jam_selesai`); kolom `id_shift` pada tabel `petugas`.
- **Kriteria penerimaan:**
  - CRUD shift (tambah/edit/hapus).
  - Assignment petugas ke shift tertentu.

#### F4 — Smart Tracking Toggle (Hemat Data)
- **Deskripsi:** Backend hanya memproses data trilaterasi jika petugas berada dalam jam shift aktif. Di luar jam kerja, data dari ESP32 diabaikan (tidak masuk database).
- **User story:** Sebagai sistem, saya perlu memvalidasi jam kerja sebelum memproses data posisi agar tidak membebani komputasi & storage secara sia-sia.
- **Logika inti:**
  ```sql
  SELECT p.id_petugas, s.nama_shift
  FROM petugas p
  JOIN shift_kerja s ON p.id_shift = s.id_shift
  WHERE p.id_petugas = 1
    AND CURRENT_TIME BETWEEN s.jam_mulai AND s.jam_selesai;
  ```
  Jika hasil query kosong → petugas di luar jam kerja → data koordinat tidak diproses/disimpan.
- **Kriteria penerimaan:**
  - Data di luar jam shift tidak tercatat di `log_pergerakan`.
  - Tidak ada penurunan performa signifikan pada endpoint yang menerima data ESP32.

#### F5 — Task Location Matching (Sistem Penugasan)
- **Deskripsi:** Admin memberikan tugas di ruangan tertentu (misal "Security cek Ruang VIP"). Sistem otomatis mendeteksi apakah petugas benar-benar hadir di ruangan tersebut dan mengukur durasi kehadirannya.
- **Kebutuhan data:** Tabel `tugas_petugas` (`id_tugas`, `id_petugas`, `nama_tugas`, `target_ruangan`, `status_tugas`, `waktu_mulai`, `waktu_selesai`).
- **Kriteria penerimaan:**
  - Status tugas otomatis berubah (`Pending` → `On Progress` → `Completed`) berdasarkan deteksi lokasi.
  - Riwayat tugas dapat difilter per petugas/ruangan/tanggal.

### 4.3 Modul Analitik Lanjutan

#### F6 — Dwelling Time Heatmap (Peta Durasi Diam)
- **Deskripsi:** Heatmap yang menampilkan area di mana petugas paling lama berhenti/diam, bukan sekadar area yang sering dilewati. Berguna untuk mendeteksi perilaku tidak wajar (misal terlalu lama di pantry).
- **Kriteria penerimaan:**
  - Visualisasi heatmap dengan skala waktu diam (durasi, bukan frekuensi).
  - Filter berdasarkan rentang waktu dan ruangan.

#### F7 — Auto-Data Pruning (Pembersih Database Otomatis)
- **Deskripsi:** Halaman pengaturan untuk menghapus log koordinat mentah berusia > 30 hari secara otomatis, sambil tetap menyisakan data ringkasan (total jam kerja, riwayat pelanggaran zona).
- **User story:** Sebagai admin, saya ingin database tetap ringan tanpa kehilangan insight historis penting.
- **Kriteria penerimaan:**
  - Job terjadwal (scheduled job/cron) menjalankan agregasi harian sebelum penghapusan data mentah.
  - Data ringkasan tetap tersedia setelah data mentah dihapus.
  - Ambang waktu (30 hari) dapat dikonfigurasi oleh admin.

---

## 5. Skema Database Tambahan (Neon DB)

```sql
-- 1. TABEL SHIFT KERJA
CREATE TABLE shift_kerja (
    id_shift SERIAL PRIMARY KEY,
    nama_shift VARCHAR(50) NOT NULL,
    jam_mulai TIME NOT NULL,
    jam_selesai TIME NOT NULL
);

-- 2. MODIFIKASI TABEL PETUGAS
ALTER TABLE petugas ADD COLUMN id_shift INT REFERENCES shift_kerja(id_shift);

-- 3. MODIFIKASI TABEL NODE ESP32
ALTER TABLE node_esp32 ADD COLUMN p_tx FLOAT DEFAULT -59.0;
ALTER TABLE node_esp32 ADD COLUMN faktor_n FLOAT DEFAULT 2.0;

-- 4. TABEL TUGAS LOKASI
CREATE TABLE tugas_petugas (
    id_tugas SERIAL PRIMARY KEY,
    id_petugas INT REFERENCES petugas(id_petugas),
    nama_tugas VARCHAR(100) NOT NULL,
    target_ruangan VARCHAR(50) NOT NULL,
    status_tugas VARCHAR(20) DEFAULT 'Pending',
    waktu_mulai TIMESTAMP,
    waktu_selesai TIMESTAMP
);
```

---

## 6. Prioritas Pengembangan (Roadmap Sederhana)

| Prioritas | Fitur | Alasan |
|-----------|-------|--------|
| P0 | F4 Smart Tracking Toggle, F3 Manajemen Shift | Dampak langsung ke efisiensi database & biaya |
| P0 | F7 Auto-Data Pruning | Mencegah pembengkakan storage yang sudah berjalan |
| P1 | F1 Signal Calibrator Tool | Meningkatkan akurasi tanpa maintenance hardware |
| P1 | F5 Task Location Matching | Nilai tambah operasional (akuntabilitas kerja) |
| P2 | F2 Signal Loss Detector | Fitur monitoring lanjutan |
| P2 | F6 Dwelling Time Heatmap | Analitik lanjutan, tidak kritis di awal |

---

## 7. Risiko & Mitigasi

| Risiko | Dampak | Mitigasi |
|--------|--------|----------|
| Kalibrasi manual salah input jarak | Akurasi trilaterasi menurun | Beri instruksi jelas di UI + validasi input |
| Job pruning gagal berjalan | Database tetap membengkak | Tambahkan monitoring/alert jika job gagal & retry otomatis |
| Perubahan jam shift mendadak | Data tracking tidak konsisten | Cache jadwal shift & refresh berkala, bukan query per-request saja |
| False positive interference detector | Alert berlebihan, admin abai notifikasi | Threshold dapat dikonfigurasi, tambahkan cooldown alert |

---

## 8. Ringkasan

Rencana ini mengubah IPS dari sistem pelacakan posisi pasif menjadi sistem yang **otomatis, hemat sumber daya, dan berbasis data operasional (shift & tugas)**. Tiga pilar utama: **Kalibrasi Otomatis**, **Smart Tracking berbasis Shift**, dan **Data Pruning otomatis** — akan langsung berdampak pada akurasi, efisiensi database, dan kemudahan penggunaan bagi admin.
