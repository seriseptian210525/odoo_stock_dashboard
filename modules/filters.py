import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

def calculate_dates(period_option):
    """Helper untuk menghitung start_date dan end_date berdasarkan pilihan."""
    today = datetime.now().date()
    start_date, end_date = None, None
    period_label = "Kustom.."

    if period_option == "Hari Ini":
        start_date = today
        end_date = today
        period_label = "Hari Ini"
    elif period_option == "7 Hari Terakhir":
        start_date = today - timedelta(days=6)
        end_date = today
        period_label = "7 Hari Terakhir"
    elif period_option == "30 Hari Terakhir":
        start_date = today - timedelta(days=29)
        end_date = today
        period_label = "30 Hari Terakhir"
    elif period_option == "90 Hari Terakhir":
        start_date = today - timedelta(days=89)
        end_date = today
        period_label = "90 Hari Terakhir"
    elif period_option == "Semua Waktu":
        start_date = None
        end_date = None
        period_label = "Semua Waktu"
    
    # 'Kustom..' akan ditangani oleh callback 'set_date_filter'
    
    return (start_date, end_date), period_label

def set_date_filter():
    """Callback untuk memperbarui state tanggal saat selectbox atau date_input berubah."""
    
    period_option = st.session_state.date_filter_option
    
    if period_option == "Kustom..":
        dates = st.session_state.custom_date_range
        
        # (PERBAIKAN: Tambahkan pemeriksaan 'None' di sini)
        # Hanya format label jika tanggalnya valid (bukan None)
        if dates and len(dates) == 2 and dates[0] is not None and dates[1] is not None:
            st.session_state.selected_dates = (dates[0], dates[1])
            try:
                # Coba format tanggal
                st.session_state.period_label = f"{pd.to_datetime(dates[0]).strftime('%d %b %Y')} - {pd.to_datetime(dates[1]).strftime('%d %b %Y')}"
            except Exception:
                # Fallback jika format gagal
                st.session_state.period_label = "Kustom.."
        else:
            # Jika 'custom_date_range' belum diisi (masih None)
            # Atur tanggal default yang aman
            default_start = datetime.now().date() - timedelta(days=7)
            default_end = datetime.now().date()
            st.session_state.selected_dates = (default_start, default_end)
            st.session_state.period_label = "Kustom.." # Label default
            # (PENTING: Perbarui juga state 'custom_date_range' agar widget date_input konsisten)
            st.session_state.custom_date_range = (default_start, default_end) 
            
    else:
        # Hitung tanggal preset
        (dates, label) = calculate_dates(period_option)
        st.session_state.selected_dates = dates
        st.session_state.period_label = label

def display_filters(df: pd.DataFrame):
    """
    Menampilkan 8 filter dinamis (4x2 grid).
    (PERBAIKAN: Menggunakan 'key' dan 'on_change' untuk manajemen state)
    """
    if df.empty:
        st.info("Data mentah (Moves History) kosong, filter tidak dapat dibuat.", icon="ℹ️")
        return
        
    col1, col2, col3, col4 = st.columns(4)

    # --- BARIS 1 ---
    
    with col1:
        # Filter 1: Rentang Tanggal (Dinamis)
        st.selectbox(
            "Pilih Rentang Tanggal",
            options=["Semua Waktu", "Hari Ini", "7 Hari Terakhir", "30 Hari Terakhir", "90 Hari Terakhir", "Kustom.."],
            key="date_filter_option",
            on_change=set_date_filter
        )
        
        # Tampilkan date_input hanya jika 'Kustom..' dipilih
        if st.session_state.date_filter_option == "Kustom..":
            # (PERBAIKAN: Gunakan 'custom_date_range' untuk 'value')
            st.date_input(
                "Tanggal Awal - Tanggal Akhir",
                value=st.session_state.custom_date_range,
                key="custom_date_range",
                on_change=set_date_filter
            )

    with col2:
        # Filter 2: Kategori Lokasi
        options = sorted(df['Location Category'].dropna().unique())
        st.multiselect("Pilih Kategori Lokasi", options, key="selected_cat_loc")

    with col3:
        # Filter 3: Lokasi Spesifik
        options = sorted(df['Location'].dropna().unique())
        st.multiselect("Pilih Lokasi Spesifik", options, key="selected_spec_loc")

    with col4:
        # Filter 4: Status (dari Pivot)
        if 'Status_Replenishment' in df.columns:
            options = sorted(df['Status_Replenishment'].dropna().unique())
            # (PERBAIKAN: Pastikan 'key' benar)
            st.multiselect("Pilih Status Replenishment", options, key="selected_statuses")
        else:
            st.warning("Kolom 'Status_Replenishment' tidak ditemukan.")

    # --- BARIS 2 ---
    col5, col6, col7, col8 = st.columns(4)

    with col5:
        # Filter 5: SKU
        options = sorted(df['SKU'].dropna().unique())
        st.multiselect("Pilih SKU", options, key="selected_skus")

    with col6:
        # Filter 6: SKU Name
        options = sorted(df['SKU Name'].dropna().unique())
        st.multiselect("Pilih SKU Name", options, key="selected_sku_names")

    with col7:
        # Filter 7: Dibuat Oleh (Created by)
        # (PERBAIKAN: Tambahkan .dropna() untuk mengatasi TypeError float vs str)
        options = sorted(df['Created by'].dropna().unique())
        st.multiselect("Pilih Pembuat (Created by)", options, key="selected_creators")

    with col8:
        # Filter 8: Referensi
        options = sorted(df['Reference'].dropna().unique())
        st.multiselect("Pilih Referensi", options, key="selected_references")