import streamlit as st
import pandas as pd
from datetime import datetime
from modules import google_sheets # Sesuaikan nama file
from modules import data_processing
import os # Untuk password fallback

# -----------------------------------------------------------------
# OTENTIKASI (PASSWORD)
# -----------------------------------------------------------------

def check_password():
    """Menampilkan form login dan memeriksa password."""
    
    # Ambil password dari .env (Lokal) atau st.secrets (Deploy)
    CORRECT_PASSWORD = None
    try:
        # Mode Deploy
        CORRECT_PASSWORD = st.secrets.get("APP_PASSWORD")
    except:
        # Mode Lokal
        CORRECT_PASSWORD = os.getenv("APP_PASSWORD")

    if not CORRECT_PASSWORD:
        st.error("APP_PASSWORD tidak diatur di server.", icon="🚨")
        return False

    # Jika sudah login, lewati
    if st.session_state.get("password_correct", False):
        return True

    # Tampilkan form login
    with st.form("login"):
        st.title("Login Dasbor")
        password = st.text_input("Masukkan Password", type="password")
        submitted = st.form_submit_button("Login")

        if submitted:
            if password == CORRECT_PASSWORD:
                st.session_state["password_correct"] = True
                st.rerun() # Jalankan ulang skrip setelah login sukses
            else:
                st.error("Password salah.", icon="🔒")
    return False

# -----------------------------------------------------------------
# INISIALISASI SESSION STATE
# -----------------------------------------------------------------

def initialize_session_state():
    """Set nilai default untuk semua kunci di st.session_state."""
    
    defaults = {
        "password_correct": False,
        "data_processed": False,
        "last_gsheet_update": None,
        "pivot_df": pd.DataFrame(),
        "daily_soh_df": pd.DataFrame(),
        "inbound_df": pd.DataFrame(),
        "outbound_df": pd.DataFrame(),
        
        # (PERBAIKAN: Inisialisasi state filter tanggal dengan benar)
        "selected_dates": (None, None),       # Kunci (Key) untuk tanggal
        "period_label": "Semua Waktu",        # Kunci (Key) untuk label KPI
        "date_filter_option": "Semua Waktu", # Kunci (Key) untuk default selectbox
        "custom_date_range": (None, None), # (PERBAIKAN: Ditambahkan untuk 'Kustom..')
        
        "selected_cat_loc": [],
        "selected_spec_loc": [],
        "selected_references": [],
        "selected_skus": [],
        "selected_creators": [],
        "selected_sku_names": [],
        "selected_statuses": [] 
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# -----------------------------------------------------------------
# SINKRONISASI DATA
# -----------------------------------------------------------------

def sync_data_to_state(pivot_df, daily_soh_df, inbound_df, outbound_df, update_time):
    """Memasukkan data yang dimuat ke dalam st.session_state."""
    st.session_state.pivot_df = pivot_df
    st.session_state.daily_soh_df = daily_soh_df
    st.session_state.inbound_df = inbound_df
    st.session_state.outbound_df = outbound_df
    st.session_state.last_gsheet_update = update_time
    st.session_state.data_processed = True

# -----------------------------------------------------------------
# LOGIKA PEMUATAN DATA (CACHE)
# -----------------------------------------------------------------

@st.cache_data(ttl=600, show_spinner=False) # (Dibuat 'silent' (senyap))
def load_initial_data(_spreadsheet_id, _creds):
    """
    Membaca 4 sheet dari Google Sheet.
    Fungsi ini di-cache untuk performa.
    """
    if not _spreadsheet_id:
        raise Exception("SPREADSHEET_ID tidak ditemukan. Harap set di .env atau Streamlit Secrets.")
    
    # Panggil fungsi pembacaan GSheet
    (
        pivot_df, 
        daily_df, 
        inbound_df, 
        outbound_df, 
        update_time
    ) = google_sheets.read_all_data(_spreadsheet_id, _creds)
    
    if pivot_df.empty or daily_df.empty:
        raise Exception("Data di Google Sheet kosong atau tidak dapat dibaca. Coba unggah file CSV baru.")

    return pivot_df, daily_df, inbound_df, outbound_df, update_time

# -----------------------------------------------------------------
# LOGIKA UPLOAD
# -----------------------------------------------------------------

def handle_upload_csv(uploaded_file):
    """
    Memproses CSV dan mengembalikan 4 DataFrame (atau None jika gagal).
    (PERBAIKAN: Penanganan 'KeyError' saat validasi gagal)
    """
    if uploaded_file is None:
        raise Exception("Tidak ada file yang diunggah.")
        
    df_dict = data_processing.process_csv(uploaded_file)
    
    # (PERBAIKAN: Jika validasi gagal, df_dict akan kosong)
    if not df_dict:
        return None, None, None, None # Kembalikan None agar 'controls' tahu
    
    return (
        df_dict["inbound_df"],
        df_dict["outbound_df"],
        df_dict["pivot_df"],
        df_dict["daily_soh_df"]
    )

def handle_upload_to_gsheet(spreadsheet_id, creds, inbound_df, outbound_df, pivot_df, daily_soh_df):
    """Hanya mengunggah 4 DataFrame ke GSheet."""
    
    update_time = google_sheets.upload_all_data(
        spreadsheet_id, 
        creds, 
        inbound_df, 
        outbound_df, 
        pivot_df, 
        daily_soh_df
    )
    return update_time