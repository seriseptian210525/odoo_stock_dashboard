import streamlit as st
import pandas as pd
import altair as alt
import hashlib

# --- FUNGSI TAMPILAN TABEL ---

def display_paginated_table(df: pd.DataFrame, key_prefix: str, page_size: int = 50):
    """
    Menampilkan DataFrame dengan paginasi (navigasi halaman) dan pembulatan angka.
    (PERBAIKAN: Mengatasi bug 'Styler' object has no attribute 'iloc')
    """
    if df.empty:
        # Jangan tampilkan warning di sini, biarkan main_content.py yang menangani
        return

    # Buat key unik untuk widget paginasi
    key_hash = f"page_{key_prefix}"

    # Setup Paginasi
    total_rows = len(df)
    # Perhitungan total halaman yang benar
    total_pages = int(total_rows / page_size) + (1 if total_rows % page_size > 0 else 0)
    if total_pages == 0:
        total_pages = 1 
    
    page = st.number_input("Halaman", 1, total_pages, 1, key=key_hash)

    # Tentukan baris awal dan akhir
    start_idx = (page - 1) * page_size
    end_idx = min(page * page_size, total_rows) 

    # --- Logika Tampilan ---
    
    # 1. Ambil "irisan" (slice) DataFrame untuk halaman saat ini
    df_slice = df.iloc[start_idx:end_idx].copy()
    
    # 2. Tentukan kolom numerik (angka)
    try:
        numeric_cols = df_slice.select_dtypes(include='number').columns
        
        cols_to_exclude = ['Lead Time'] 
        numeric_cols_to_format = [col for col in numeric_cols if col not in cols_to_exclude]
        
        format_dict = {}
        for col in numeric_cols_to_format:
            if 'Usage' in col or 'Accuracy' in col or 'Buffer Stock' in col or 'Shortage' in col:
                format_dict[col] = "{:.2f}" # 2 angka desimal
            else:
                format_dict[col] = "{:,.0f}" # 0 angka desimal
        
        # 3. Terapkan styling HANYA pada irisan (slice)
        df_display_styled = df_slice.style.format(format_dict, na_rep="0")

        # (FITUR BARU: Conditional Formatting untuk Adjustment (Penyesuaian))
        def style_adjustment(row):
            """Beri warna hijau untuk Inbound (Inbound) Adj, Merah untuk Outbound (Outbound) Adj."""
            style = [''] * len(row) # Style default (tidak ada)
            
            # Cek jika ini adalah baris adjustment (penyesuaian)
            if 'Type' in row and 'Adjustment Qty' in row and row['Adjustment Qty'] != 0:
                # (PERBAIKAN: Gunakan 'Adjustment Qty' (Kuantitas Penyesuaian) yang bertanda (signed))
                if row['Adjustment Qty'] > 0: # Positif = Inbound (Inbound) (Penambahan)
                    style = ['background-color: #d4edda; color: #155724'] * len(row) # Hijau
                elif row['Adjustment Qty'] < 0: # Negatif = Outbound (Outbound) (Pengurangan)
                    style = ['background-color: #f8d7da; color: #721c24'] * len(row) # Merah
            return style

        # Terapkan HANYA jika ini tabel log (bukan pivot)
        if key_prefix in ["daily_soh", "inbound", "outbound"]:
            df_display = df_display_styled.apply(style_adjustment, axis=1)
        else:
            df_display = df_display_styled # Tampilkan tabel pivot (pivot table) tanpa style baris
        
    except Exception:
        # Fallback jika styling gagal
        df_display = df_slice

    # 4. Tampilkan DataFrame yang sudah di-style
    st.dataframe(df_display, use_container_width=True, height=385) 
    st.caption(f"Menampilkan baris {start_idx + 1}–{end_idx} dari total {total_rows:,} baris.")

# --- FUNGSI TREN PERFORMA STOK ---

def plot_daily_stock_accuracy_trend(df: pd.DataFrame):
    """
    Menampilkan Tren Akurasi Stok (Unweighted) sebagai line chart (grafik garis) sederhana.
    """
    st.markdown("#### Tren Akurasi Stok Harian (Unweighted)")
    
    if df.empty:
        st.warning("Data tidak cukup untuk tren Akurasi Stok.", icon="⚠️")
        return

    # 1. Hitung akurasi harian
    acc_series = (
        df.groupby('Date')
        .apply(lambda x: (1 - abs(x['Inbound_Qty'].sum() - x['Outbound_Qty'].sum()) /
                         (x['Inbound_Qty'].sum() + x['Outbound_Qty'].sum())) * 100
              if (x['Inbound_Qty'].sum() + x['Outbound_Qty'].sum()) != 0 else 100)
    )
    
    if isinstance(acc_series, pd.DataFrame):
        if 'Date' in acc_series.columns:
            acc_series = acc_series.drop(columns=['Date'])
        acc_series = acc_series.iloc[:, 0] 

    acc_df = acc_series.to_frame(name='Stock Accuracy %').reset_index()
    
    if acc_df.empty:
        st.warning("Data tidak cukup untuk tren Akurasi Stok.", icon="⚠️")
        return

    # 2. Buat Chart (Grafik)
    base = alt.Chart(acc_df).encode(
        x=alt.X('Date:T', title='Tanggal', axis=alt.Axis(format="%Y-%m-%d")),
        y=alt.Y('Stock Accuracy %:Q', title='Akurasi Stok (%)'),
        tooltip=[
            alt.Tooltip('Date:T', format="%d %b %Y"), 
            alt.Tooltip('Stock Accuracy %:Q', format=".1f")
        ]
    ).properties(height=300)

    line = base.mark_line(point=True)
    text = base.mark_text(align='center', dy=-10, color='black').encode(
        text=alt.Text('Stock Accuracy %:Q', format=".0f")
    )
    
    chart = (line + text).interactive()
    st.altair_chart(chart, use_container_width=True)

def plot_weighted_accuracy_trend(df: pd.DataFrame):
    """
    Menampilkan Tren Akurasi Stok (Weighted by SOH) sebagai line chart (grafik garis).
    (PERBAIKAN: Menggunakan rumus "Best Practice" (Praktik Terbaik) untuk akurasi kuantitas)
    """
    st.markdown("#### Tren Akurasi Stok Harian (Weighted by SOH)")
    
    if df.empty or 'Cumulative_SOH' not in df.columns or 'Adjustment Qty' not in df.columns or 'Outbound_Qty' not in df.columns:
        st.warning("Data tidak cukup untuk tren Weighted Accuracy (Kolom 'Cumulative_SOH', 'Adjustment Qty', atau 'Outbound_Qty' tidak ditemukan di Moves History).", icon="⚠️")
        return

    # 1. Agregasi SOH, Adjustment, dan Outbound per hari
    daily_agg = df.groupby('Date').agg(
        Total_SOH=('Cumulative_SOH', 'last'), 
        Total_Adjustment_Qty=('Adjustment Qty', 'sum'), # Ini adalah signed (bertanda)
        Total_Outbound=('Outbound_Qty', 'sum') 
    ).reset_index()

    # 2. Hitung akurasi harian
    def calculate_weighted_acc(row):
        # (PERBAIKAN: Gunakan .abs() (nilai absolut) untuk total kesalahan)
        total_adj_abs = abs(row['Total_Adjustment_Qty'])
        
        # 1. Hitung basis stok (Stok Akhir + Stok Keluar)
        soh_plus_outbound = row['Total_SOH'] + row['Total_Outbound']
        
        # 2. Tentukan denominator (pembagi)
        # Denominator (Pembagi) tidak boleh 0, dan tidak boleh lebih kecil dari 
        # total kesalahan (total_adj_abs).
        denominator = max(soh_plus_outbound, total_adj_abs, 1) # min 1
        
        # 3. Hitung akurasi
        # Rumus baru: (1 - (Total Kesalahan / Denominator (Pembagi) yang Valid))
        accuracy = (1 - (total_adj_abs / denominator)) * 100
        
        # (PERBAIKAN BUG KRITIS: Akurasi minimal 0% (tidak boleh negatif))
        return max(accuracy, 0)

    daily_agg['Weighted Accuracy %'] = daily_agg.apply(calculate_weighted_acc, axis=1)
    
    if daily_agg.empty:
        st.warning("Data tidak cukup untuk tren Weighted Accuracy.", icon="⚠️")
        return

    # 3. Buat Chart (Grafik)
    base = alt.Chart(daily_agg).encode(
        x=alt.X('Date:T', title='Tanggal', axis=alt.Axis(format="%Y-%m-%d")),
        y=alt.Y('Weighted Accuracy %:Q', title='Akurasi (Weighted) (%)', scale=alt.Scale(zero=False)), # Hapus nol agar fokus
        tooltip=[
            alt.Tooltip('Date:T', format="%d %b %Y"), 
            alt.Tooltip('Weighted Accuracy %:Q', format=".1f")
        ]
    ).properties(height=300)

    line = base.mark_line(point=True, color='green')
    text = base.mark_text(align='center', dy=-10, color='green').encode(
        text=alt.Text('Weighted Accuracy %:Q', format=".0f")
    )
    
    chart = (line + text).interactive()
    st.altair_chart(chart, use_container_width=True)

def plot_adjustment_trend_line(df: pd.DataFrame):
    """
    Menampilkan Tren Transaksi Adjustment (Updated vs Confirmed) sebagai line chart (grafik garis).
    """
    st.markdown("#### Tren Transaksi Adjustment (Updated vs Confirmed)")
    
    if df.empty:
        st.warning("Data tidak cukup untuk tren Adjustment.", icon="⚠️")
        return

    # 1. Buat DataFrame tren
    df_updated = df[df['Reference'].str.contains("Product Quantity Updated", case=False, na=False)]
    df_confirmed = df[df['Reference'].str.contains("Product Quantity Confirmed", case=False, na=False)]

    trend_updated = df_updated.groupby('Date')['SKU'].count().reset_index(name='Jumlah Transaksi')
    trend_confirmed = df_confirmed.groupby('Date')['SKU'].count().reset_index(name='Jumlah Transaksi')
    
    trend_updated['Tipe'] = 'Updated'
    trend_confirmed['Tipe'] = 'Confirmed'
    
    trend_df = pd.concat([trend_updated, trend_confirmed])
    
    if trend_df.empty:
        st.warning("Tidak ada transaksi 'Updated' atau 'Confirmed' di periode ini.", icon="⚠️")
        return

    # 2. Buat Chart (Grafik)
    base = alt.Chart(trend_df).encode(
        x=alt.X('Date:T', title='Tanggal', axis=alt.Axis(format="%Y-%m-%d")),
        y=alt.Y('Jumlah Transaksi:Q', title='Jumlah Transaksi'),
        color=alt.Color('Tipe:N', title="Tipe Adjustment"),
        tooltip=[
            alt.Tooltip('Date:T', format="%d %b %Y"), 
            'Tipe:N',
            'Jumlah Transaksi:Q'
        ]
    ).properties(height=300)

    line = base.mark_line(point=True)
    text = base.mark_text(align='center', dy=-10).encode(
        text=alt.Text('Jumlah Transaksi:Q', format=".0f")
    )
    
    chart = (line + text).interactive()
    st.altair_chart(chart, use_container_width=True)


# --- FUNGSI ANALISIS ADJUSTMENT ---

def plot_adjustment_analysis_tables(df: pd.DataFrame):
    """
    Menampilkan 3 tabel analisis adjustment (SKU, Lokasi, Pembuat)
    dengan tata letak vertikal dan paginasi 10 baris.
    """
    
    df_adj = df[df['Reference'].str.contains("Product Quantity Updated|Product Quantity Confirmed", case=False, na=False)].copy()
    
    if df_adj.empty:
        st.warning("Tidak ada data adjustment untuk dianalisis.", icon="⚠️")
        return

    # 1. Analisis SKU
    st.markdown("#### Top SKU Di-Adjustment")
    sku_analysis = df_adj.groupby(['SKU', 'SKU Name']).agg(
        Jumlah_Adjustment=('SKU', 'count'),
        Terakhir_Adjustment=('Date', 'max')
    ).sort_values(by='Jumlah_Adjustment', ascending=False)
    
    sku_analysis = sku_analysis.reset_index()
    
    display_paginated_table(sku_analysis, key_prefix="adj_sku", page_size=10)

    # 2. Analisis Lokasi
    st.markdown("#### Top Lokasi Adjustment")
    loc_analysis = df_adj.groupby(['Location', 'Location Category']).agg(
        Jumlah_Adjustment=('SKU', 'count'),
        Terakhir_Adjustment=('Date', 'max')
    ).sort_values(by='Jumlah_Adjustment', ascending=False)
    
    loc_analysis = loc_analysis.reset_index()
    display_paginated_table(loc_analysis, key_prefix="adj_loc", page_size=10)

    # 3. Analisis Pembuat
    st.markdown("#### Top User Adjustment")
    creator_analysis = df_adj.groupby('Created by').agg(
        Jumlah_Adjustment=('SKU', 'count'),
        Terakhir_Adjustment=('Date', 'max')
    ).sort_values(by='Jumlah_Adjustment', ascending=False)
    
    creator_analysis = creator_analysis.reset_index()
    display_paginated_table(creator_analysis, key_prefix="adj_creator", page_size=10)