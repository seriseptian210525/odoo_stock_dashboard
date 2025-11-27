# Product Requirements Document (PRD)
**Proyek:** Odoo Stock Dashboard  
**Versi:** 1.0  
**Tanggal:** 26 November 2025  
**Status:** Draft

---

## 1. Pendahuluan

### 1.1 Latar Belakang
Perusahaan membutuhkan cara yang efisien untuk memantau pergerakan stok (*moves*) dan akurasi inventori secara *real-time* atau periodik. Data dari Odoo ERP perlu diolah lebih lanjut untuk mendapatkan *insight* seperti *Stock on Hand* (SOH), *Buffer Stock*, dan status *replenishment* yang tidak tersedia secara langsung di tampilan standar Odoo.

### 1.2 Tujuan
Membangun dashboard berbasis web yang dapat:
1.  Mengolah data ekspor CSV dari Odoo (`moves.csv`) secara otomatis.
2.  Menghitung metrik kunci: SOH, Daily Usage, Buffer Stock, dan Status Stok (Safe/Alert/Danger).
3.  Menyediakan visualisasi interaktif untuk analisis cepat.
4.  Menyinkronkan hasil olahan kembali ke Google Sheets untuk akses kolaboratif.

---

## 2. Spesifikasi Fitur

### 2.1 Manajemen Data (ETL)
*   **Input:** File CSV (`moves.csv`) dengan kolom wajib: `Date`, `Product`, `Status`, `Reference`, `Quantity`, `From`, `To`, `Created by`.
*   **Validasi:** Sistem menolak file jika kolom wajib hilang.
*   **Transformasi:**
    *   Pemisahan transaksi menjadi *Inbound* (Masuk) dan *Outbound* (Keluar).
    *   Perhitungan *Signed Quantity* (Positif untuk Inbound, Negatif untuk Outbound).
    *   Kategorisasi Lokasi (misal: "Pool", "Bengkel Rekanan", "Central Warehouse") berdasarkan *keyword* string.
    *   Pembersihan data (menghapus transaksi *draft* atau *cancelled*).

### 2.2 Logika Bisnis (Business Logic)
*   **Daily Usage:** Rata-rata pemakaian per hari selama 90 hari terakhir.
*   **Moves Category:**
    *   *Fast*: Usage > 1.0 (Lead Time 21 hari)
    *   *Medium*: Usage > 0.1 (Lead Time 14 hari)
    *   *Slow*: Usage <= 0.1 (Lead Time 7 hari)
*   **Buffer Stock:** `Daily Usage * Lead Time`
*   **Stock Status:**
    *   🟥 **Danger**: SOH < 0 atau SOH < 50% Buffer Stock.
    *   🟨 **Alert**: 50% Buffer Stock <= SOH <= 100% Buffer Stock.
    *   🟩 **Safe**: SOH > Buffer Stock.

### 2.3 Visualisasi (Dashboard)
*   **Filter Interaktif:** Berdasarkan Lokasi, Rentang Tanggal, SKU, dan Pembuat (Created By).
*   **KPI Cards:** Menampilkan ringkasan total SKU, Akurasi Stok, dan Cakupan Lokasi.
*   **Pivot Table:** Tabel utama yang menampilkan status per SKU per Lokasi.
*   **Grafik:**
    *   Heatmap untuk visualisasi distribusi stok.
    *   Bar Chart untuk akurasi per kategori lokasi.

### 2.4 Integrasi Google Sheets
*   **Sync:** Upload otomatis 4 DataFrame utama ke sheet terpisah:
    1.  `Pivot` (Ringkasan Status)
    2.  `Moves History` (Log Transaksi Harian)
    3.  `Inbound` (Log Masuk)
    4.  `Outbound` (Log Keluar)
*   **Security:** Menggunakan Service Account (`secrets.toml` atau `.env`).

---

## 3. Alur Kerja (Workflow)

1.  **Login:** User masuk menggunakan password aplikasi.
2.  **Load:** Aplikasi memuat data terakhir dari Google Sheets (Cache).
3.  **Upload:** User mengunggah file `moves.csv` terbaru dari Odoo.
4.  **Process:** Sistem memproses CSV, menghitung ulang semua metrik.
5.  **Review:** User melihat *preview* data yang telah diproses di dashboard.
6.  **Sync:** User menekan tombol "Update Google Sheets" untuk menyimpan hasil.

---

## 4. Arsitektur Teknis

### 4.1 Tech Stack
*   **Bahasa:** Python 3.x
*   **Framework:** Streamlit
*   **Data Processing:** Pandas, NumPy
*   **Integrasi:** GSpread (Google Sheets API)
*   **Deployment:** Streamlit Cloud (mendukung `secrets.toml`)

### 4.2 Struktur Direktori
*   `app.py`: Entry point aplikasi.
*   `modules/`:
    *   `data_processing.py`: Logika ETL.
    *   `google_sheets.py`: Koneksi API.
    *   `state_manager.py`: Manajemen sesi user.
    *   `visuals_advanced.py`: Komponen grafik.

---

## 5. Rencana Pengembangan Masa Depan
*   [ ] Konfigurasi aturan bisnis (Lead Time, Kategori) via UI (menghindari hardcode).
*   [x] Optimasi Adjustment Analysis 
		(Menambahkan: 
		Frekuensi: Jumlah kali transaksi dilakukan.
		Adj. Increase: Total penambahan stok.
		Adj. Decrease: Total pengurangan stok (merah).
		Net Adjustment: Total bersih (Increase + Decrease).
		).
*   [ ] Notifikasi email/Telegram untuk status "Danger".
