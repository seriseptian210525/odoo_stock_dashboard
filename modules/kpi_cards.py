import streamlit as st
import pandas as pd
import altair as alt
import datetime

# --- HELPER KARTU KUSTOM ---

def _display_insight_card(title, value_str, delta_str, delta_color, insight_caption, stability_caption=""):
    """
    Helper untuk menampilkan kartu kustom yang insightful, berdasarkan referensi Anda.
    """
    with st.container(border=True):
        st.markdown(f"**{title}**")
        st.markdown(f"## {value_str}")
        
        # Tampilkan delta hanya jika ada (tidak 'off')
        if delta_color != "off":
            # Gunakan st.metric hanya untuk delta, non-label
            st.metric(label=" ", value=" ", delta=delta_str, delta_color=delta_color)
        
        # Tampilkan insight caption
        st.caption(f"{insight_caption}\n\n{stability_caption}")

# --- FUNGSI KALKULASI PER KPI ---

def _safe_get_date_value(series, date_key, default=0):
    """Helper untuk mengambil nilai dari series berdasarkan tanggal, menangani KeyError"""
    try:
        # Coba .loc[tanggal] (jika 'Date' adalah index)
        return series.loc[date_key]
    except KeyError:
        # Jika gagal, coba cara fallback
        if not series.empty:
            return default
        return 0 # Jika series kosong
    except Exception:
        return default

def calculate_stock_accuracy_kpi(df: pd.DataFrame, start_date, end_date):
    """Menganalisis Stock Accuracy (Unweighted) dari referensi Anda."""
    
    # 1. Menangani "Semua Waktu" (jika start/end date adalah None)
    if start_date is None: 
        if df.empty: return "N/A", "N/A", "off", "Data tidak cukup.", ""
        start_date = df['Date'].min()
    if end_date is None: 
        if df.empty: return "N/A", "N/A", "off", "Data tidak cukup.", ""
        end_date = df['Date'].max()

    # 2. Hitung akurasi harian
    acc_series = (
        df.groupby('Date')
        .apply(lambda x: (1 - abs(x['Inbound_Qty'].sum() - x['Outbound_Qty'].sum()) /
                         (x['Inbound_Qty'].sum() + x['Outbound_Qty'].sum())) * 100
              if (x['Inbound_Qty'].sum() + x['Outbound_Qty'].sum()) != 0 else 100)
    )
    
    # (PERBAIKAN: Logika defensif untuk menangani ambiguitas 'Date')
    if isinstance(acc_series, pd.DataFrame):
        if 'Date' in acc_series.columns:
            acc_series = acc_series.drop(columns=['Date'])
        acc_series = acc_series.iloc[:, 0] # Ambil kolom data pertama

    acc_df = acc_series.to_frame(name='Stock Accuracy %').reset_index().sort_values(by='Date')
    
    # (PERBAIKAN: Set 'Date' sebagai index untuk .loc[] yang aman)
    acc_series_indexed = acc_df.set_index('Date')['Stock Accuracy %']

    if acc_df.empty:
        return "N/A", "N/A", "off", "Data tidak cukup.", ""

    # 3. Kalkulasi Metrik
    avg_acc = acc_df['Stock Accuracy %'].mean()
    start_acc = _safe_get_date_value(acc_series_indexed, start_date, acc_df.iloc[0]['Stock Accuracy %'])
    end_acc = _safe_get_date_value(acc_series_indexed, end_date, acc_df.iloc[-1]['Stock Accuracy %'])
    trend = end_acc - start_acc
    stability_index = acc_df['Stock Accuracy %'].std()

    # 4. Tentukan Insight
    if avg_acc >= 98: insight = "✅ Excellent — Akurasi stabil tinggi."
    elif avg_acc >= 95: insight = "🟢 Baik — Stok cukup konsisten."
    elif avg_acc >= 85: insight = "🟠 Perlu Perhatian — Fluktuasi tinggi antar hari."
    else: insight = "🔴 Rendah — Sistem stok tidak akurat."
    
    if stability_index < 2: stability = "📊 Performa stabil — variasi rendah antar hari."
    else: stability = f"⚠️ Fluktuasi tinggi (StdDev: {stability_index:.1f}) — Cek konsistensi."
    
    # Akurasi Stok: Naik itu BAGUS (Normal)
    return f"{avg_acc:,.1f}%", f"{trend:+.1f}% vs awal periode", "normal", insight, stability

def calculate_sku_adjusted_kpi(df: pd.DataFrame, start_date, end_date):
    """Menganalisis SKU yang di-Adjustment (Updated/Confirmed)."""
    
    if start_date is None: 
        if df.empty: return "0", "N/A", "off", "Tidak ada SKU yang di-adjustment.", ""
        start_date = df['Date'].min()
    if end_date is None: 
        if df.empty: return "0", "N/A", "off", "Tidak ada SKU yang di-adjustment.", ""
        end_date = df['Date'].max()

    df_adj = df[df['Reference'].str.contains("Product Quantity Updated|Product Quantity Confirmed", case=False, na=False)]
    
    if df_adj.empty:
        return "0", "N/A", "off", "Tidak ada SKU yang di-adjustment.", ""

    adj_per_day = df_adj.groupby('Date')['SKU'].nunique()
    
    if adj_per_day.empty:
        return "0", "N/A", "off", "Tidak ada SKU yang di-adjustment.", ""
        
    total_adj_sku = adj_per_day.sum() # Total adjustment harian dijumlahkan
    avg_adj_sku = adj_per_day.mean()
    
    start_val = _safe_get_date_value(adj_per_day, start_date, adj_per_day.iloc[0])
    end_val = _safe_get_date_value(adj_per_day, end_date, adj_per_day.iloc[-1])
    trend = end_val - start_val
    stability_index = adj_per_day.std()

    if avg_adj_sku <= 1: insight = "✅ Sangat Baik — Adjustment SKU minimal."
    elif avg_adj_sku <= 5: insight = "🟢 Baik — Jumlah adjustment terkendali."
    elif avg_adj_sku <= 15: insight = "🟠 Perlu Perhatian — SKU adjustment cukup sering."
    else: insight = "🔴 Tinggi — Terlalu banyak SKU di-adjustment."
    
    if stability_index < 1: stability = "📊 Adjustment stabil — pola konsisten."
    else: stability = f"⚠️ Fluktuasi tinggi (StdDev: {stability_index:.1f}) — Cek pola adjustment."

    # SKU Adjusted: Naik itu BURUK (Inverse)
    return f"{total_adj_sku:,.0f}", f"{trend:+.0f} SKU/hari vs awal periode", "inverse", insight, stability 

def calculate_sku_variance_kpi(df: pd.DataFrame):
    """Menganalisis SKU Variance (SOH < 0). Ini adalah snapshot, bukan tren harian."""
    
    if df.empty:
        return "0", "N/A", "off", "Tidak ada data SOH.", ""
        
    variance_skus = df[df['SOH'] < 0]
    total_variance_skus = variance_skus['SKU'].nunique()
    
    if total_variance_skus == 0: insight = "✅ Excellent — Tidak ada SOH negatif."
    elif total_variance_skus <= 5: insight = "🟠 Perlu Perhatian — Ada SOH negatif, segera periksa."
    else: insight = "🔴 Kritis — Banyak SKU SOH negatif. Cek segera!"
    
    stability = f"Total Kuantitas Negatif: {variance_skus['SOH'].sum():,.0f}"
    
    return f"{total_variance_skus:,.0f}", "", "off", insight, stability # Tidak ada delta/tren

def calculate_active_locations_kpi(df: pd.DataFrame, start_date, end_date):
    """Menganalisis jumlah lokasi yang aktif bertransaksi per hari."""
    
    if start_date is None: 
        if df.empty: return "0", "N/A", "off", "Tidak ada transaksi.", ""
        start_date = df['Date'].min()
    if end_date is None: 
        if df.empty: return "0", "N/A", "off", "Tidak ada transaksi.", ""
        end_date = df['Date'].max()

    if df.empty:
        return "0", "N/A", "off", "Tidak ada transaksi.", ""
        
    locs_per_day = df.groupby('Date')['Location'].nunique()
    
    if locs_per_day.empty:
        return "0", "N/A", "off", "Tidak ada transaksi.", ""
        
    avg_locs = locs_per_day.mean()
    
    start_val = _safe_get_date_value(locs_per_day, start_date, locs_per_day.iloc[0])
    end_val = _safe_get_date_value(locs_per_day, end_date, locs_per_day.iloc[-1])
    trend = end_val - start_val
    stability_index = locs_per_day.std()

    if avg_locs <= 5: insight = "Sangat Terpusat — Aktivitas hanya di beberapa lokasi."
    elif avg_locs <= 15: insight = "Terpusat — Aktivitas terfokus."
    else: insight = "Tersebar — Aktivitas tersebar di banyak lokasi."
    
    if stability_index < 2: stability = "📊 Aktivitas stabil — jumlah lokasi konsisten."
    else: stability = f"⚠️ Fluktuasi tinggi (StdDev: {stability_index:.1f}) — Pola aktivitas tidak menentu."

    # Lokasi Aktif: Naik itu NETRAL (kita anggap Normal)
    return f"{avg_locs:,.1f}", f"{trend:+.0f} Lokasi/hari vs awal periode", "normal", insight, stability

# --- (PERBAIKAN: Logika "Weighted Accuracy" (Akurasi Tertimbang) ditulis ulang total) ---

def calculate_weighted_accuracy_kpi(df: pd.DataFrame, start_date, end_date):
    """
    Menganalisis Weighted Stock Accuracy (berdasarkan kuantitas).
    (PERBAIKAN: Dihitung dari 'daily_soh_df' (Log Harian) untuk tren time series (linimasa))
    """
    
    # 1. Menangani "Semua Waktu" (jika start/end date adalah None)
    if start_date is None: 
        if df.empty: return "N/A", "N/A", "off", "Data tidak cukup.", ""
        start_date = df['Date'].min()
    if end_date is None: 
        if df.empty: return "N/A", "N/A", "off", "Data tidak cukup.", ""
        end_date = df['Date'].max()

    if df.empty or 'Cumulative_SOH' not in df.columns or 'Adjustment Qty' not in df.columns or 'Outbound_Qty' not in df.columns:
        return "N/A", "N/A", "off", "Data tidak cukup (Kolom SOH/Adj/Outbound hilang).", ""

    # 2. Agregasi SOH, Adjustment, dan Outbound per hari
    daily_agg = df.groupby('Date').agg(
        Total_SOH=('Cumulative_SOH', 'last'), 
        Total_Adjustment_Qty=('Adjustment Qty', 'sum'), # Ini adalah signed (bertanda)
        Total_Outbound=('Outbound_Qty', 'sum') 
    ).reset_index()

    # 3. Hitung akurasi harian ("Best Practice" (Praktik Terbaik))
    def calculate_weighted_acc(row):
        # (PERBAIKAN: Gunakan .abs() (nilai absolut) untuk total kesalahan)
        total_adj_abs = abs(row['Total_Adjustment_Qty'])
        
        # Total Stok Dikelola = Stok Akhir + Total Keluar
        total_stock_managed = row['Total_SOH'] + row['Total_Outbound']
        # Denominator (Pembagi) tidak boleh 0, dan tidak boleh lebih kecil dari kesalahan
        denominator = max(total_stock_managed, total_adj_abs, 1) # min 1
        
        accuracy = (1 - (total_adj_abs / denominator)) * 100
        return max(accuracy, 0) # Akurasi tidak boleh negatif

    daily_agg['Weighted Accuracy %'] = daily_agg.apply(calculate_weighted_acc, axis=1)
    
    acc_series_indexed = daily_agg.set_index('Date')['Weighted Accuracy %']

    if acc_series_indexed.empty:
        return "N/A", "N/A", "off", "Data tidak cukup.", ""

    # 4. Kalkulasi Metrik
    avg_acc = acc_series_indexed.mean()
    start_acc = _safe_get_date_value(acc_series_indexed, start_date, acc_series_indexed.iloc[0])
    end_acc = _safe_get_date_value(acc_series_indexed, end_date, acc_series_indexed.iloc[-1])
    trend = end_acc - start_acc
    stability_index = acc_series_indexed.std()

    # 5. Tentukan Insight
    if avg_acc >= 95: insight = "✅ Excellent — Akurasi kuantitas sangat tinggi."
    elif avg_acc >= 90: insight = "🟢 Baik — Akurasi kuantitas terjaga (Target ≥ 90%)."
    elif avg_acc >= 80: insight = "🟠 Perlu Perhatian — Akurasi kuantitas di bawah target."
    else: insight = "🔴 Rendah — Akurasi kuantitas sangat rendah."
    
    if stability_index < 3: stability = "📊 Performa stabil — variasi rendah antar hari."
    else: stability = f"⚠️ Fluktuasi tinggi (StdDev: {stability_index:.1f}) — Cek kuantitas adj."

    # Akurasi (Weighted) (Tertimbang): Naik itu BAGUS (Normal)
    return f"{avg_acc:,.1f}%", f"{trend:+.1f}% vs awal periode", "normal", insight, stability


# --- FUNGSI UTAMA UNTUK DIPANGGIL DARI main_content.py ---

def display_kpi_metrics(daily_soh_df_filtered: pd.DataFrame, pivot_df_filtered: pd.DataFrame, start_date, end_date, period_label):
    """
    Menampilkan 5 Metrik KPI Utama dengan insight dan analisis periode.
    """
    
    st.info(f"Menampilkan metrik untuk periode: **{period_label}**")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    # --- 1. Stock Accuracy (Unweighted) ---
    try:
        acc_val, acc_del, acc_col, acc_ins, acc_sta = calculate_stock_accuracy_kpi(daily_soh_df_filtered, start_date, end_date)
        with col1:
            _display_insight_card(
                "📈 Akurasi Stok (Transaksi)",
                acc_val, acc_del, acc_col, acc_ins, acc_sta
            )
    except Exception as e:
        with col1:
            st.error(f"Gagal hitung Akurasi Stok.\n{e}", icon="🚨")

    # --- 2. Weighted Stock Accuracy ---
    try:
        # (PERBAIKAN BUG KONEKSI: Kirim 'daily_soh_df_filtered' (Log Harian yang difilter) ke KPI ini)
        w_acc_val, w_acc_del, w_acc_col, w_acc_ins, w_acc_sta = calculate_weighted_accuracy_kpi(daily_soh_df_filtered, start_date, end_date)
        
        with col2:
            _display_insight_card(
                "⚖️ Akurasi Stok (Kuantitas)",
                w_acc_val, w_acc_del, w_acc_col, w_acc_ins, w_acc_sta
            )
    except Exception as e:
        with col2:
            st.error(f"Gagal hitung Weighted Akurasi.\n{e}", icon="🚨")
            st.exception(e) # Tampilkan traceback

    # --- 3. SKU Adjusted ---
    try:
        # (PERBAIKAN: Argumen sudah benar)
        adj_val, adj_del, adj_col, adj_ins, adj_sta = calculate_sku_adjusted_kpi(daily_soh_df_filtered, start_date, end_date)
        with col3:
            _display_insight_card(
                "🔧 Total SKU Adjusted",
                adj_val, adj_del, adj_col, adj_ins, adj_sta
            )
    except Exception as e:
        with col3:
            st.error(f"Gagal hitung SKU Adjusted.\n{e}", icon="🚨")
            st.exception(e) # Tampilkan traceback

    # --- 4. SKU Variance (SOH < 0) ---
    try:
        var_val, var_del, var_col, var_ins, var_sta = calculate_sku_variance_kpi(pivot_df_filtered)
        with col4:
            _display_insight_card(
                "🔩 SKU Variance (SOH < 0)",
                var_val, var_del, var_col, var_ins, var_sta
            )
    except Exception as e:
        with col4:
            st.error(f"Gagal hitung SKU Variance.\n{e}", icon="🚨")
            
    # --- 5. Active Locations ---
    try:
        loc_val, loc_del, loc_col, loc_ins, loc_sta = calculate_active_locations_kpi(daily_soh_df_filtered, start_date, end_date)
        with col5:
            _display_insight_card(
                "🏭 Lokasi Aktif (Rata-rata/Hari)",
                loc_val, loc_del, loc_col, loc_ins, loc_sta
            )
    except Exception as e:
        with col5:
            st.error(f"Gagal hitung Lokasi Aktif.\n{e}", icon="🚨")