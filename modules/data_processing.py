import streamlit as st
import pandas as pd
import numpy as np
from datetime import timedelta

def _validate_columns(df):
    """Memvalidasi bahwa kolom yang diperlukan ada di CSV."""
    # Kolom wajib untuk menjalankan proses
    REQUIRED_COLS = [
        'Date', 'Product', 'Status', 'Reference', 'Quantity', 
        'From', 'To', 'Created by'
    ]
    missing_cols = [col for col in REQUIRED_COLS if col not in df.columns]
    
    if missing_cols:
        st.error(f"File CSV Anda tidak valid. Kolom berikut tidak ditemukan: {', '.join(missing_cols)}", icon="🚨")
        return False
    return True

def _categorize_location(loc_series):
    """
    Menerapkan logika kategori lokasi baru yang diminta.
    Urutan ini penting.
    """
    loc_series_str = loc_series.astype(str) # Pastikan tipe data string
    
    conditions = [
        loc_series_str.str.contains("CM Warehouse", case=False, na=False),
        loc_series_str.str.contains("Central Warehouse Pondok Indah|Warehouse Bitung", case=False, na=False),
        loc_series_str.str.contains("Pool", case=False, na=False),
        loc_series_str.str.contains("Bengkel Rekanan", case=False, na=False),
        loc_series_str.str.contains("Partners/Vendors", case=False, na=False),
        loc_series_str.str.contains("Virtual Locations", case=False, na=False),
        loc_series_str.str.contains("Unknown", case=False, na=False)
    ]
    choices = [
        "Manufacture",
        "Central Warehouse",
        "Pool",
        "Bengkel Rekanan",
        "Partners/Vendors",
        "Virtual Locations",
        "Unknown"
    ]
    # Default 'Others' untuk yang tidak cocok
    return np.select(conditions, choices, default="Others")

def process_csv(uploaded_file):
    """
    Memproses file CSV Odoo (moves.csv) menjadi 4 DataFrame utama 
    dengan logika bisnis yang canggih.
    """
    
    # --- LANGKAH 1: Muat & Validasi Data ---
    try:
        df = pd.read_csv(uploaded_file)
    except Exception as e:
        st.error(f"Gagal membaca file CSV: {e}", icon="🚨")
        return {} # Kembalikan dict kosong jika gagal

    if not _validate_columns(df):
        return {} # Menghentikan eksekusi jika kolom tidak valid

    # Konversi tipe data awal
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce').fillna(0)
    
    # Filter hanya transaksi yang 'done'
    df = df[df['Status'] == 'done'].copy()
    
    # Buat kolom SKU
    df['SKU'] = df['Product'].str.extract(r'\[(.*?)\]').fillna('NO_SKU')
    df['SKU Name'] = df['Product'].str.replace(r'\[.*?\]\s*', '', regex=True).str.strip()

    # --- LANGKAH 2: Buat merged_df (Data Transaksi Utama) ---
    inbound_df_raw = df.copy()
    outbound_df_raw = df.copy()
    inbound_df_raw['Location'] = inbound_df_raw['To']
    outbound_df_raw['Location'] = outbound_df_raw['From']
    inbound_df_raw['Type'] = 'Inbound'
    outbound_df_raw['Type'] = 'Outbound'

    merged_df = pd.concat([inbound_df_raw, outbound_df_raw], ignore_index=True)
    
    merged_df['Inbound_Qty'] = np.where(merged_df['Type'] == 'Inbound', merged_df['Quantity'], 0)
    merged_df['Outbound_Qty'] = np.where(merged_df['Type'] == 'Outbound', merged_df['Quantity'], 0)

    # (PERBAIKAN: Buat 'Signed_Quantity' (Kuantitas Bertanda) untuk kalkulasi SOH (Stok di Tangan) yang benar)
    merged_df['Signed_Quantity'] = np.where(
        merged_df['Type'] == 'Inbound',
        merged_df['Quantity'],  # Inbound (Inbound) adalah Positif
        -merged_df['Quantity']  # Outbound (Outbound) adalah Negatif
    )

    # Buat Kategori Lokasi
    merged_df['Location Category'] = _categorize_location(merged_df['Location'])
    
    # (PERBAIKAN BUG 1a: Gunakan 'Signed_Quantity' (Kuantitas Bertanda) untuk Adjustment Qty (Kuantitas Penyesuaian))
    adj_mask = merged_df['Reference'].str.contains("Product Quantity Updated|Product Quantity Confirmed", case=False, na=False)
    merged_df['Adjustment Qty'] = np.where(adj_mask, merged_df['Signed_Quantity'], 0)

    # (FITUR BARU: Pisahkan Adjustment Increase dan Decrease)
    merged_df['Adjustment Increase'] = np.where(merged_df['Adjustment Qty'] > 0, merged_df['Adjustment Qty'], 0)
    merged_df['Adjustment Decrease'] = np.where(merged_df['Adjustment Qty'] < 0, merged_df['Adjustment Qty'], 0)

    merged_df['Date'] = pd.to_datetime(merged_df['Date'], errors='coerce')
    merged_df = merged_df.dropna(subset=['Date']) 
    
    merged_df = merged_df.sort_values(by=['Location', 'SKU', 'Date'])
    
    # (PERBAIKAN: Gunakan 'Signed_Quantity' (Kuantitas Bertanda) untuk SOH (Stok di Tangan) "Debet/Kredit" (Debit/Kredit) yang benar)
    merged_df['Cumulative_SOH'] = merged_df.groupby(['Location', 'SKU'])['Signed_Quantity'].cumsum()

    # --- LANGKAH 3: Hitung SOH Agregat (untuk Visibilitas) ---
    # (PERBAIKAN: Gunakan 'Signed_Quantity' (Kuantitas Bertanda) untuk SOH (Stok di Tangan) Agregat)
    soh_agg_df = merged_df.groupby(['SKU', 'Location Category'])['Signed_Quantity'].sum().unstack(fill_value=0)
    
    soh_to_merge = pd.DataFrame(index=soh_agg_df.index)
    if 'Central Warehouse' in soh_agg_df.columns:
        soh_to_merge['Central_SOH'] = soh_agg_df['Central Warehouse']
    if 'Manufacture' in soh_agg_df.columns:
        soh_to_merge['Manufacture_SOH'] = soh_agg_df['Manufacture']

    # --- LANGKAH 3.5 (BARU): Agregasi Adjustment Qty (Kuantitas Penyesuaian) SEBELUM difilter ---
    # (PERBAIKAN BUG 1b: Ini memperbaiki 'Adjustment Qty = 0' di pivot)
    # (UPDATE: Tambahkan Increase dan Decrease ke agregasi)
    adj_agg_unfiltered = merged_df.groupby(['SKU', 'Location']).agg({
        'Adjustment Qty': 'sum',
        'Adjustment Increase': 'sum',
        'Adjustment Decrease': 'sum'
    }).reset_index()

    # --- LANGKAH 4: Filter merged_df (setelah menghitung SOH agregat) ---
    merged_df_filtered = merged_df[~merged_df['Location Category'].isin(['Virtual Locations', 'Partners/Vendors'])]
    
    # --- LANGKAH 5: Logika Pivot Table (Tabel Pivot) Canggih ---
    
    # 5a. Hitung Daily Usage (Pemakaian Harian)
    # (PERBAIKAN "Best Practice" (Praktik Terbaik): Ambil SEMUA outbound KECUALI adjustment)
    # Ini akan memperbaiki bug 'Status' (Status) N/A
    adjustment_refs = ["Product Quantity Updated", "Product Quantity Confirmed"]
    usage_df = merged_df_filtered[
        (merged_df_filtered['Type'] == 'Outbound') &
        (~merged_df_filtered['Reference'].str.contains("|".join(adjustment_refs), case=False, na=False))
    ].copy()
    
    if not usage_df.empty:
        usage_df['Date'] = pd.to_datetime(usage_df['Date'], errors='coerce')
        usage_df = usage_df.dropna(subset=['Date']) 
        
        usage_df['Days Since'] = (usage_df['Date'].max() - usage_df['Date']).dt.days
        usage_df = usage_df[usage_df['Days Since'] <= 90] 
        
        usage_agg = usage_df.groupby(['SKU', 'Location'])['Outbound_Qty'].sum()
        usage_df = (usage_agg / 90).reset_index(name='Daily Usage')
    else:
        usage_df = pd.DataFrame(columns=['SKU', 'Location', 'Daily Usage'])

    # 5b. Buat Pivot Table (Tabel Pivot) Agregat per Lokasi
    # (PERBAIKAN BUG OVERCOUNTING (PERHITUNGAN BERLEBIH): Hapus 'SOH' (Stok di Tangan) dari .agg())
    # (PERBAIKAN BUG 1b: Hapus 'Adjustment_Qty' (Kuantitas Penyesuaian) dari .agg() ini)
    pivot_df = merged_df_filtered.groupby(['SKU', 'SKU Name', 'Location', 'Location Category']).agg(
        Inbound_Qty=('Inbound_Qty', 'sum'),
        Outbound_Qty=('Outbound_Qty', 'sum')
    ).reset_index()
    
    # (PERBAIKAN BUG OVERCOUNTING (PERHITUNGAN BERLEBIH): Hitung SOH (Stok di Tangan) dari In/Out)
    pivot_df['SOH'] = pivot_df['Inbound_Qty'] - pivot_df['Outbound_Qty']

    # 5c. Gabungkan (Merge) Daily Usage ke Pivot
    pivot_df = pd.merge(pivot_df, usage_df, on=['SKU', 'Location'], how='left')
    
    # (PERBAIKAN BUG 1b: Gabungkan (Merge) 'adj_agg_unfiltered' (Kuantitas Penyesuaian agregat yang tidak difilter) yang sudah kita hitung)
    pivot_df = pd.merge(pivot_df, adj_agg_unfiltered, on=['SKU', 'Location'], how='left')

    # 5d. Gabungkan (Merge) SOH Agregat (Central & Manufacture)
    if not soh_to_merge.empty:
        pivot_df = pd.merge(pivot_df, soh_to_merge, on='SKU', how='left')
    
    # 5e. Isi NaN dan Hitung Metrik Turunan
    if 'Daily Usage' not in pivot_df.columns: pivot_df['Daily Usage'] = 0.0
    if 'Central_SOH' not in pivot_df.columns: pivot_df['Central_SOH'] = 0.0
    if 'Manufacture_SOH' not in pivot_df.columns: pivot_df['Manufacture_SOH'] = 0.0
    
    pivot_df['Daily Usage'] = pivot_df['Daily Usage'].fillna(0)
    pivot_df['Central_SOH'] = pivot_df['Central_SOH'].fillna(0)
    pivot_df['Manufacture_SOH'] = pivot_df['Manufacture_SOH'].fillna(0)

    # Logika Kategori Pergerakan & Waktu Tunggu
    def get_moves_info(daily_usage):
        if daily_usage > 1.0: return "Fast", 21
        elif daily_usage > 0.1: return "Medium", 14
        else: return "Slow", 7
    
    pivot_df[['Moves Category', 'Lead Time']] = pivot_df['Daily Usage'].apply(
        lambda x: pd.Series(get_moves_info(x))
    )

    # Logika Buffer Stock (Stok Penyangga) / Safety Stock (Stok Pengaman)
    pivot_df['Buffer Stock'] = pivot_df['Daily Usage'] * pivot_df['Lead Time']
    pivot_df['Shortage'] = (pivot_df['Buffer Stock'] - pivot_df['SOH']).apply(lambda x: max(x, 0))

    # Logika Status 🟥 🟨 🟩 dan Action (Tindakan)
    def get_status_and_action(row):
        # (PERBAIKAN: Mengubah 'N/A' menjadi '🟥 Danger')
        if row['Buffer Stock'] == 0:
            if row['SOH'] < 0: return "🟥 Danger", "SOH Negatif!"
            return "🟥 Danger", "Stok 0 Pemakaian (N/A)" # N/A sekarang Danger
        
        soh_ratio = row['SOH'] / row['Buffer Stock']
        
        if soh_ratio < 0.5:
            return "🟥 Danger", f"Stok Kritis (<50% BS). Replenish {row['Shortage']:.0f} pcs."
        elif soh_ratio <= 1:
            if row['Shortage'] > 0: return "🟨 Alert", f"Segera Replenish ({row['Shortage']:.0f} pcs)"
            else: return "🟨 Alert", "Stok di Buffer Level"
        else:
            return "🟩 Safe", "Stok Cukup"
            
    pivot_df[['Status', 'Action']] = pivot_df.apply(get_status_and_action, axis=1, result_type='expand')
    
    # (PERBAIKAN: Pindahkan 'Adjustment Qty' ke sini, setelah semua merge selesai)
    for col in ['Adjustment Qty', 'Adjustment Increase', 'Adjustment Decrease']:
        if col not in pivot_df.columns:
            pivot_df[col] = 0.0
        pivot_df[col] = pivot_df[col].fillna(0)

    # 5f. Filter Pivot agar hanya menampilkan "Pool" dan "Bengkel Rekanan"
    pivot_df = pivot_df[pivot_df['Location Category'].isin(['Pool', 'Bengkel Rekanan'])].copy()

    # 5g. Tentukan kolom final
    cols_pivot = [
        'SKU', 'SKU Name', 'Location', 'Location Category', 
        'Status', 'Action', 'SOH', 
        'Inbound_Qty', 'Outbound_Qty', 
        'Adjustment Qty', 'Adjustment Increase', 'Adjustment Decrease',
        'Daily Usage', 'Moves Category', 'Lead Time', 
        'Buffer Stock', 'Shortage', 
        'Central_SOH', 'Manufacture_SOH'
    ]
    pivot_df = pivot_df.reindex(columns=cols_pivot).fillna(0)

    # --- LANGKAH 6: Buat DataFrame 'Moves History' (Log Harian) ---
    
    # 6a. Gabungkan (Merge) 'Daily Usage' (Pemakaian Harian) ke merged_df (untuk Moves Category (Kategori Pergerakan))
    merged_df_filtered = pd.merge(merged_df_filtered, usage_df, on=['SKU', 'Location'], how='left')
    merged_df_filtered['Daily Usage'] = merged_df_filtered['Daily Usage'].fillna(0)
    
    # 6b. Terapkan Moves Category (Kategori Pergerakan) & Buffer Stock (Stok Penyangga) ke merged_df
    merged_df_filtered[['Moves Category', 'Lead Time']] = merged_df_filtered['Daily Usage'].apply(
        lambda x: pd.Series(get_moves_info(x))
    )
    merged_df_filtered['Buffer Stock'] = merged_df_filtered['Daily Usage'] * merged_df_filtered['Lead Time']
    merged_df_filtered['Shortage'] = (merged_df_filtered['Buffer Stock'] - merged_df_filtered['Cumulative_SOH']).apply(lambda x: max(x, 0))

    # 6c. Terapkan Status (Status) 🟥 🟨 🟩 ke merged_df (menggunakan SOH Kumulatif)
    def get_status_daily(row):
        # (PERBAIKAN: Mengubah 'N/A' menjadi '🟥 Danger')
        if row['Buffer Stock'] == 0:
            if row['Cumulative_SOH'] < 0: return "🟥 Danger"
            return "🟥 Danger" # N/A sekarang Danger
        soh_ratio = row['Cumulative_SOH'] / row['Buffer Stock']
        if soh_ratio < 0.5: return "🟥 Danger"
        elif soh_ratio <= 1: return "🟨 Alert"
        else: return "🟩 Safe"
            
    merged_df_filtered['Status_Replenishment'] = merged_df_filtered.apply(get_status_daily, axis=1)

    log_df = merged_df_filtered[merged_df_filtered['Location Category'].isin(['Pool', 'Bengkel Rekanan'])].copy()
    log_df['Status'] = 'done' 
    
    cols_moves = [
        'Date', 'Created by', 'Reference', 'Contact', 'Location', 'Location Category', 
        'SKU', 'SKU Name', 'Inbound_Qty', 'Outbound_Qty', 'Quantity', 
        'Status_Replenishment', 
        'Type', 
        'Adjustment Qty', 'Adjustment Increase', 'Adjustment Decrease', 'Cumulative_SOH'
    ]
    
    daily_soh_df = log_df.reindex(columns=cols_moves).sort_values(by=['Location', 'SKU', 'Date'], ascending=True)
    
    # --- LANGKAH 7: Buat DataFrame Inbound & Outbound (Log Spesifik) ---
    inbound_df = daily_soh_df[daily_soh_df['Type'] == 'Inbound'].reindex(columns=cols_moves).sort_values(by=['Location', 'SKU', 'Date'], ascending=True)
    outbound_df = daily_soh_df[daily_soh_df['Type'] == 'Outbound'].reindex(columns=cols_moves).sort_values(by=['Location', 'SKU', 'Date'], ascending=True)

    return {
        "pivot_df": pivot_df,
        "daily_soh_df": daily_soh_df,
        "inbound_df": inbound_df,
        "outbound_df": outbound_df
    }