import streamlit as st
from modules import state_manager, google_sheets
from datetime import datetime
import pandas as pd

# --- FUNGSI CALLBACK (LOGIKA TOMBOL) ---

def handle_refresh(spreadsheet_id, creds):
    """Dipanggil saat tombol 'Refresh' ditekan."""
    try:
        # 1. Hapus cache data GSheet
        st.cache_data.clear()
        
        # 2. Panggil fungsi load_initial_data (mengembalikan 5 nilai)
        (
            pivot_df, 
            daily_soh_df, 
            inbound_df, 
            outbound_df, 
            update_time
        ) = state_manager.load_initial_data(spreadsheet_id, creds)
        
        # 3. Sinkronkan data baru ke state
        state_manager.sync_data_to_state(pivot_df, daily_soh_df, inbound_df, outbound_df, update_time)
        st.toast("Data GSheet berhasil dimuat ulang!", icon="✅")
        
        # 4. (PERBAIKAN: Hapus st.rerun(), tidak perlu dalam callback)

    except Exception as e:
        st.error(f"Gagal memuat ulang data dari GSheet: {e}", icon="🚨")
        # st.exception(e) # Uncomment untuk debug


def handle_upload(uploaded_file, spreadsheet_id, creds):
    """Dipanggil saat tombol 'Proses & Update' ditekan."""
    if uploaded_file is None:
        st.warning("Harap unggah file CSV terlebih dahulu.", icon="⚠️")
        return

    try:
        with st.spinner("Memproses file CSV..."):
            # 1. Proses CSV
            (
                inbound_df, 
                outbound_df, 
                pivot_df, 
                daily_soh_df
            ) = state_manager.handle_upload_csv(uploaded_file)
            
            # (PERBAIKAN: Periksa apakah proses CSV gagal (misal: validasi kolom))
            if inbound_df is None:
                # Error sudah ditampilkan oleh data_processing.py
                st.warning("Proses CSV gagal (lihat error di atas). Upload dibatalkan.", icon="⚠️")
                return # Hentikan eksekusi

        with st.spinner("Mengunggah data ke Google Sheet... (Ini mungkin perlu 1-2 menit)"):
            # 2. Upload ke GSheet
            update_time = state_manager.handle_upload_to_gsheet(
                spreadsheet_id, creds, inbound_df, outbound_df, pivot_df, daily_soh_df
            )
        
        with st.spinner("Menyinkronkan data ke dasbor..."):
            # 3. Hapus cache lama
            st.cache_data.clear()
            
            # 4. Sinkronkan data baru ke state
            state_manager.sync_data_to_state(pivot_df, daily_soh_df, inbound_df, outbound_df, update_time)
        
        st.success("File CSV berhasil diproses dan diunggah ke Google Sheet!", icon="🎉")
        
        # 5. (PERBAIKAN: Hapus st.rerun(), tidak perlu dalam callback)
        
    except Exception as e:
        st.error(f"Gagal memproses unggahan: {e}", icon="🚨")
        # st.exception(e) # Uncomment untuk debug

# --- FUNGSI TAMPILAN UTAMA ---

def display_controls(spreadsheet_id, creds):
    """
    Menampilkan UI untuk Kontrol & Upload Data (UI Datar, tanpa st.expander)
    """
    
    st.subheader("Kontrol & Upload Data 📤")
    st.markdown("""
        Selamat datang di Dasbor Stok Odoo.
        - **Refresh Data:** Muat data terbaru yang ada di Google Sheet.
        - **Proses & Update:** Unggah file `moves.csv` baru, proses, dan perbarui data di Google Sheet.
    """)
    
    col_upload, col_buttons = st.columns([1.5, 1]) # Kolom upload lebih besar

    with col_upload:
        uploaded_file = st.file_uploader(
            "Unggah file `moves.csv` dari Odoo", 
            type=["csv"],
            key="csv_uploader"
        )
    
    with col_buttons:
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            st.button(
                "🚀 Proses & Update GSheet",
                on_click=handle_upload,
                args=(st.session_state.csv_uploader, spreadsheet_id, creds),
                use_container_width=True,
                type="primary"
            )
        with col_b2:
            st.button(
                "🔄 Refresh Data GSheet",
                on_click=handle_refresh,
                args=(spreadsheet_id, creds),
                use_container_width=True
            )
        
        # (PERBAIKAN: Logika caption dipindahkan ke DALAM col_buttons)
        # Tampilkan status pembaruan terakhir TEPAT DI BAWAH TOMBOL
        if st.session_state.last_gsheet_update:
            try:
                # Coba format sebagai datetime
                update_time_str = pd.to_datetime(st.session_state.last_gsheet_update).strftime('%d %b %Y, %H:%M:%S')
                st.caption(f"Data GSheet terakhir dimuat: **{update_time_str}**")
            except:
                # Jika gagal (format lama), tampilkan apa adanya
                st.caption(f"Data GSheet terakhir dimuat: **{st.session_state.last_gsheet_update}**")

    # Garis pemisah
    st.divider()

