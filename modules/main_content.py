import streamlit as st
import pandas as pd
from modules import filters
from modules import kpi_cards
from modules import visuals_advanced
import altair as alt
import datetime 

def display_main_content():
    """
    Menampilkan seluruh konten utama dasbor, termasuk KPI, Filter, Tabel, dan Chart.
    (Versi Final Lengkap)
    """
    
    # --- 1. Validasi State ---
    if 'data_processed' not in st.session_state or not st.session_state.data_processed:
        st.info("Silakan muat data dari Google Sheet atau unggah file CSV baru untuk memulai.", icon="ℹ️")
        return

    # --- 2. Ambil Data dari Session State ---
    try:
        daily_soh_df = st.session_state.daily_soh_df
        pivot_df = st.session_state.pivot_df
        inbound_df = st.session_state.inbound_df
        outbound_df = st.session_state.outbound_df
    except AttributeError:
        st.error("Gagal memuat data dari session state. Coba muat ulang data.", icon="🚨")
        return

    # --- 3. Ambil Pilihan Filter dari Session State ---
    (start_date, end_date) = st.session_state.get('selected_dates', (None, None))
    period_label = st.session_state.get('period_label', 'Semua Waktu') 
    
    # Pemeriksaan tipe defensif
    if not isinstance(start_date, (datetime.date, datetime.datetime, type(None))):
        start_date = None
    if not isinstance(end_date, (datetime.date, datetime.datetime, type(None))):
        end_date = None
    
    selected_cat_loc = st.session_state.get('selected_cat_loc', [])
    selected_spec_loc = st.session_state.get('selected_spec_loc', [])
    selected_statuses = st.session_state.get('selected_statuses', [])
    selected_sku_names = st.session_state.get('selected_sku_names', [])
    selected_skus = st.session_state.get('selected_skus', [])
    selected_creators = st.session_state.get('selected_creators', [])
    selected_references = st.session_state.get('selected_references', [])

    # (PERBAIKAN TypeError: date vs str)
    # Konversi kolom 'Date' di DataFrame utama (jika belum)
    try:
        # Pastikan ini adalah objek date, bukan datetime, agar cocok dengan filter
        daily_soh_df['Date'] = pd.to_datetime(daily_soh_df['Date'], errors='coerce').dt.date
        inbound_df['Date'] = pd.to_datetime(inbound_df['Date'], errors='coerce').dt.date
        outbound_df['Date'] = pd.to_datetime(outbound_df['Date'], errors='coerce').dt.date
    except Exception as e:
        st.error(f"Gagal mengonversi kolom 'Date' di data mentah: {e}", icon="🚨")
        return

    # --- 4. Terapkan Filter ke Data ---
    filtered_daily_soh_df = daily_soh_df.copy()
    filtered_pivot_df = pivot_df.copy()
    filtered_inbound_df = inbound_df.copy()
    filtered_outbound_df = outbound_df.copy()

    # Filter Tanggal (Wajib)
    if start_date and end_date:
        try:
            # (PERBAIKAN TypeError: date vs str)
            # Konversi start/end date (dari filter) ke tipe date
            start_date_d = pd.to_datetime(start_date).date()
            end_date_d = pd.to_datetime(end_date).date()
            
            # DataFrame sudah dikonversi ke .dt.date di LANGKAH 3
            filtered_daily_soh_df = filtered_daily_soh_df[
                (filtered_daily_soh_df['Date'] >= start_date_d) &
                (filtered_daily_soh_df['Date'] <= end_date_d)
            ]
            filtered_inbound_df = filtered_inbound_df[
                (filtered_inbound_df['Date'] >= start_date_d) &
                (filtered_inbound_df['Date'] <= end_date_d)
            ]
            filtered_outbound_df = filtered_outbound_df[
                (filtered_outbound_df['Date'] >= start_date_d) &
                (filtered_outbound_df['Date'] <= end_date_d)
            ]
            
            # Filter Pivot (agak rumit karena pivot tidak memiliki 'Date')
            # Kita filter berdasarkan SKU/Lokasi yang aktif di rentang tanggal tersebut
            skus_in_date_range = filtered_daily_soh_df['SKU'].unique()
            locs_in_date_range = filtered_daily_soh_df['Location'].unique()
            
            filtered_pivot_df = filtered_pivot_df[
                (filtered_pivot_df['SKU'].isin(skus_in_date_range)) &
                (filtered_pivot_df['Location'].isin(locs_in_date_range))
            ]
        except Exception as e:
            st.warning(f"Gagal memfilter tanggal: {e}. Pastikan format tanggal di GSheet benar.", icon="⚠️")
            # Jika gagal, jangan filter berdasarkan tanggal

    # Filter Opsional
    if selected_cat_loc:
        filtered_daily_soh_df = filtered_daily_soh_df[filtered_daily_soh_df['Location Category'].isin(selected_cat_loc)]
        filtered_pivot_df = filtered_pivot_df[filtered_pivot_df['Location Category'].isin(selected_cat_loc)]
        filtered_inbound_df = filtered_inbound_df[filtered_inbound_df['Location Category'].isin(selected_cat_loc)]
        filtered_outbound_df = filtered_outbound_df[filtered_outbound_df['Location Category'].isin(selected_cat_loc)]

    if selected_spec_loc:
        filtered_daily_soh_df = filtered_daily_soh_df[filtered_daily_soh_df['Location'].isin(selected_spec_loc)]
        filtered_pivot_df = filtered_pivot_df[filtered_pivot_df['Location'].isin(selected_spec_loc)]
        filtered_inbound_df = filtered_inbound_df[filtered_inbound_df['Location'].isin(selected_spec_loc)]
        filtered_outbound_df = filtered_outbound_df[filtered_outbound_df['Location'].isin(selected_spec_loc)]

    if selected_statuses:
        # (PERBAIKAN: Filter 'Status' 🟥 🟨 🟩 HANYA berlaku untuk PIVOT_DF)
        if 'Status' in filtered_pivot_df.columns:
            filtered_pivot_df = filtered_pivot_df[filtered_pivot_df['Status'].isin(selected_statuses)]

    if selected_sku_names:
        filtered_daily_soh_df = filtered_daily_soh_df[filtered_daily_soh_df['SKU Name'].isin(selected_sku_names)]
        filtered_pivot_df = filtered_pivot_df[filtered_pivot_df['SKU Name'].isin(selected_sku_names)]
        filtered_inbound_df = filtered_inbound_df[filtered_inbound_df['SKU Name'].isin(selected_sku_names)]
        filtered_outbound_df = filtered_outbound_df[filtered_outbound_df['SKU Name'].isin(selected_sku_names)]

    if selected_skus:
        filtered_daily_soh_df = filtered_daily_soh_df[filtered_daily_soh_df['SKU'].isin(selected_skus)]
        filtered_pivot_df = filtered_pivot_df[filtered_pivot_df['SKU'].isin(selected_skus)]
        filtered_inbound_df = filtered_inbound_df[filtered_inbound_df['SKU'].isin(selected_skus)]
        filtered_outbound_df = filtered_outbound_df[filtered_outbound_df['SKU'].isin(selected_skus)]

    if selected_creators:
        filtered_daily_soh_df = filtered_daily_soh_df[filtered_daily_soh_df['Created by'].isin(selected_creators)]
        filtered_inbound_df = filtered_inbound_df[filtered_inbound_df['Created by'].isin(selected_creators)]
        filtered_outbound_df = filtered_outbound_df[filtered_outbound_df['Created by'].isin(selected_creators)]
        
    if selected_references:
        filtered_daily_soh_df = filtered_daily_soh_df[filtered_daily_soh_df['Reference'].isin(selected_references)]
        filtered_inbound_df = filtered_inbound_df[filtered_inbound_df['Reference'].isin(selected_references)]
        filtered_outbound_df = filtered_outbound_df[filtered_outbound_df['Reference'].isin(selected_references)]

    # --- 5. Tampilkan Ringkasan Metrik (KPI) 📈 ---
    st.subheader("Ringkasan Metrik (KPI) 📈")
    
    # (PERBAIKAN: Tambahkan kembali argumen ke-5 'period_label' untuk mengatasi TypeError)
    kpi_cards.display_kpi_metrics(
        filtered_daily_soh_df, 
        filtered_pivot_df, 
        start_date, 
        end_date,
        period_label # Argumen ke-5 yang hilang
    )

    # --- 6. Tampilkan Panel Filter (Lokasi Baru) ---
    st.subheader("Filter Data Dinamis 🔬")
    # Kirim data mentah (daily_soh_df) untuk membangun opsi filter
    # Ini memastikan opsi filter selalu penuh, tidak terpengaruh filter lain
    filters.display_filters(daily_soh_df) 

    # --- 7. Tampilkan Detail Tabel (Tabs) 📊 ---
    st.subheader("Detail Tabel 📊")
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "Tabel Pivot SOH (Agregat) 📋", 
        "Log: Moves History 📜", 
        "Log: Inbound 📥", 
        "Log: Outbound 📤"
    ])

    with tab1:
        if filtered_pivot_df.empty:
            st.warning("Tidak ada data Pivot SOH untuk ditampilkan berdasarkan filter Anda.", icon="⚠️")
        else:
            visuals_advanced.display_paginated_table(filtered_pivot_df, key_prefix="pivot")

    with tab2:
        if filtered_daily_soh_df.empty:
            st.warning("Tidak ada data Moves History untuk ditampilkan berdasarkan filter Anda.", icon="⚠️")
        else:
            visuals_advanced.display_paginated_table(filtered_daily_soh_df, key_prefix="daily_soh")

    with tab3:
        if filtered_inbound_df.empty:
            st.warning("Tidak ada data Inbound untuk ditampilkan berdasarkan filter Anda.", icon="⚠️")
        else:
            visuals_advanced.display_paginated_table(filtered_inbound_df, key_prefix="inbound")

    with tab4:
        if filtered_outbound_df.empty:
            st.warning("Tidak ada data Outbound untuk ditampilkan berdasarkan filter Anda.", icon="⚠️")
        else:
            visuals_advanced.display_paginated_table(filtered_outbound_df, key_prefix="outbound")

    # --- 8. Tren Performa Stok 📈 ---
    st.subheader("Tren Performa Stok 📈")
    with st.expander("Klik di sini untuk melihat rumus kalkulasi metrik"):
        st.markdown("""
            **Rumus Kalkulasi Metrik:**
            - **Tren Akurasi Stok (Unweighted):** Dihitung sebagai `(1 - (Total Discrepancy / Total Pergerakan)) * 100%` per hari. Ini mengukur akurasi *transaksi*.
            - **Tren Akurasi Stok (Weighted):** Dihitung sebagai `(1 - (Total Qty Adjustment / Total SOH)) * 100%` per hari. Ini mengukur akurasi *kuantitas*.
            - **Tren Transaksi Adjustment:** Dihitung sebagai jumlah (count) transaksi harian yang mengandung referensi "Product Quantity Updated" atau "Product Quantity Confirmed".
        """)
    
    if filtered_daily_soh_df.empty:
        st.warning("Data 'Moves History' tidak ditemukan untuk menghitung tren akurasi.", icon="⚠️")
    else:
        visuals_advanced.plot_daily_stock_accuracy_trend(filtered_daily_soh_df)
        visuals_advanced.plot_adjustment_trend_line(filtered_daily_soh_df)
        
    # (PERBAIKAN: Kirim 'filtered_daily_soh_df' ke 'plot_weighted_accuracy_trend')
    if filtered_daily_soh_df.empty:
        st.warning("Data 'Moves History' tidak ditemukan untuk menghitung tren weighted accuracy.", icon="⚠️")
    else:
        # Chart ini membutuhkan data harian (yang sekarang memiliki 'Cumulative_SOH' dan 'Adjustment Qty')
        visuals_advanced.plot_weighted_accuracy_trend(filtered_daily_soh_df) 
        
    # --- 9. Analisis Adjustment 🔬 ---
    st.subheader("Analisis Adjustment 🔬")
    if filtered_daily_soh_df.empty:
        st.warning("Data 'Moves History' tidak ditemukan untuk menghitung analisis adjustment.", icon="⚠️")
    else:
        visuals_advanced.plot_adjustment_analysis_tables(filtered_daily_soh_df)

