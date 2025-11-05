# 📊 Odoo Stock Dashboard

**Odoo Stock Dashboard** adalah aplikasi **analisis stok dan akurasi inventori** berbasis **Streamlit**,  
dibangun untuk memantau performa pergerakan barang (*inbound/outbound*) dan ketepatan stok aktual dari sistem Odoo.  
Aplikasi ini mendukung integrasi langsung ke **Google Sheets** dan menampilkan **visualisasi interaktif, KPI cards, dan pivot analysis**.

---

## 🚀 Fitur Utama

✅ **Upload & Integrasi Otomatis**
- Upload file CSV hasil ekspor dari Odoo
- Sinkronisasi otomatis ke Google Sheets (sheet: *Inbound*, *Outbound*, *Pivot*, *Moves History*)

✅ **Dynamic Filters**
- Filter interaktif: *Location*, *Date Range*, *SKU*, *Created By*
- Semua visualisasi dan tabel otomatis merespons filter

✅ **KPI & Performance Cards**
- Unique SKU count  
- Stock Accuracy (Unweighted & Weighted)  
- Total Adjusted SKUs  
- Internal Location coverage (Pool, Bengkel Rekanan)

✅ **Visualisasi Interaktif**
- 🔥 Pivot Heatmap (Daily Usage, Safety Stock, Shortage, dll.)
- 📊 Grouped Bar Chart: Stock Accuracy by Location Category
- 📈 Trend Line: Adjustment Transactions Over Time
- 📋 Log Table: Moves History detail

✅ **Integrasi Google Sheets**
- Otomatis upload & clear data sesuai tanggal input user  
- Mendukung credential melalui `secrets.toml` (aman untuk deployment)

---

## 🏗️ Struktur Proyek
ODOO_STOCK_DASHBOARD/
│
├── modules/
│ ├── data_processing.py # ETL dan transformasi CSV
│ ├── filters.py # Komponen filter interaktif Streamlit
│ ├── google_sheets.py # Integrasi Google Sheets API
│ ├── kpi_cards.py # KPI & Scorecards
│ ├── visuals_advanced.py # Heatmap, Bar Chart, Trend Chart
│
├── app.py # Entry point Streamlit
├── requirements.txt # Daftar dependencies
├── .env # Konfigurasi lokal (ignored)
├── secrets/ # Folder credential (ignored)
└── README.md # Dokumentasi project
