import streamlit as st
import os
from dotenv import load_dotenv

# Impor modul-modul logika
from modules import page_setup
from modules import state_manager
from modules import controls
from modules import main_content
from modules import filters

def main(spreadsheet_id, creds):
    """
    Fungsi utama untuk menjalankan alur aplikasi Streamlit.
    """
    # 1. Setup Halaman (Judul, CSS, dll.)
    # (Dipanggil dari modules/page_setup.py)
    page_setup.setup_page()

    # 2. Cek Password (Otentikasi)
    if not state_manager.check_password():
        st.stop() # Menghentikan eksekusi jika password salah

    # 3. Inisialisasi Session State (jika belum ada)
    # (Dipanggil dari modules/state_manager.py)
    state_manager.initialize_session_state()

    # 4. Muat Data Awal (dari GSheet atau Cache) saat startup
    # (Ini hanya berjalan sekali per sesi atau saat cache kedaluwarsa)
    if not st.session_state.data_processed:
        try:
            (
                pivot_df, 
                daily_soh_df, 
                inbound_df, 
                outbound_df, 
                update_time
            ) = state_manager.load_initial_data(spreadsheet_id, creds)
            
            # 5. Sinkronkan data yang dimuat ke state
            state_manager.sync_data_to_state(pivot_df, daily_soh_df, inbound_df, outbound_df, update_time)
            
        except Exception as e:
            # Tampilkan error GSheet jika GSheet gagal dimuat saat startup
            st.error(f"🚨 {e}", icon="🚨")

    # 6. Tampilkan Kontrol Atas (Upload & Refresh)
    # (Dipanggil dari modules/controls.py)
    controls.display_controls(spreadsheet_id, creds)

    # 7. Tampilkan Konten Utama (KPI, Tabs, Charts)
    # (Dipanggil dari modules/main_content.py)
    # Filter sekarang ditampilkan di dalam main_content
    main_content.display_main_content()
    
    # 8. Tampilkan Panel Filter (jika tata letak filter di bawah)
    # (PERBAIKAN: Panggilan filter sekarang ada di dalam main_content.py)
    # st.subheader("Filter Data Dinamis 🔬")
    # filters.display_filters(st.session_state.daily_soh_df) 

# --- Titik Masuk Aplikasi ---
if __name__ == "__main__":
    # 1. Muat file .env (untuk testing lokal)
    load_dotenv()

    # 2. Dapatkan Kredensial (Mode Hibrid: Deploy/Lokal)
    SPREADSHEET_ID = None
    CREDS = None
    
    try:
        # Mode Deploy (Mengambil dari Streamlit Secrets)
        SPREADSHEET_ID = st.secrets.get("SPREADSHEET_ID")
        CREDS = st.secrets.get("gcp_service_account")
    except st.errors.StreamlitSecretNotFoundError:
        # Mode Lokal (Mengambil dari .env)
        SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
        # Biarkan CREDS = None (google_sheets.py akan menanganinya)
    except Exception as e:
        st.error(f"Terjadi error saat memuat kredensial: {e}")

    # 3. Jalankan aplikasi utama
    main(spreadsheet_id=SPREADSHEET_ID, creds=CREDS)

