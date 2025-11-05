import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import APIError
from datetime import datetime
import time
import os

# --- (SKEMA DATA: Harus sinkron dengan data_processing.py) ---
PIVOT_COLS = [
    'SKU', 'SKU Name', 'Location', 'Location Category', 
    'Status', 'Action', 'SOH', 
    'Inbound_Qty', 'Outbound_Qty', 'Adjustment Qty',
    'Daily Usage', 'Moves Category', 'Lead Time', 
    'Buffer Stock', 'Shortage', 
    'Central_SOH', 'Manufacture_SOH'
]

MOVES_COLS = [
    'Date', 'Created by', 'Reference', 'Contact', 'Location', 'Location Category', 
    'SKU', 'SKU Name', 'Inbound_Qty', 'Outbound_Qty', 'Quantity', 
    'Status_Replenishment', # (Kolom Status 🟥 🟨 🟩)
    'Type', # (Tipe Inbound/Outbound)
    'Adjustment Qty', 'Cumulative_SOH'
]


def _post_process_read_df(df, sheet_name):
    """Membersihkan dan mengubah tipe data DataFrame yang dibaca dari GSheet."""
    
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    
    numeric_cols = []
    if sheet_name == "Pivot":
        numeric_cols = [
            'SOH', 'Inbound_Qty', 'Outbound_Qty', 'Adjustment Qty',
            'Daily Usage', 'Lead Time', 'Buffer Stock', 'Shortage', 
            'Central_SOH', 'Manufacture_SOH'
        ]
    
    elif sheet_name in ["Moves History", "Inbound", "Outbound"]:
        numeric_cols = [
            'Inbound_Qty', 'Outbound_Qty', 'Quantity', 
            'Adjustment Qty', 'Cumulative_SOH'
        ]

    for col in numeric_cols:
        if col in df.columns and col != 'Date':
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    df = df.fillna('')
    df.replace('nan', '', inplace=True)
    df.replace('NaT', '', inplace=True)

    return df

@st.cache_resource(ttl=3600)
def get_gspread_client(_credentials_source): # (PERBAIKAN: Ditambahkan '_')
    """
    Membuat klien GSpread dengan cache.
    (PERBAIKAN: Menambahkan '_' untuk mengabaikan hashing argumen st.secrets)
    """
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    creds_path = None
    
    if _credentials_source: # (PERBAIKAN: Ditambahkan '_')
        # Jika creds dikirim langsung (dari app.py)
        creds_path = _credentials_source # (PERBAIKAN: Ditambahkan '_')
    else:
        try:
            # 1. Coba st.secrets (untuk deploy)
            creds_path = st.secrets.get("gcp_service_account")
        except st.errors.StreamlitSecretNotFoundError:
            # 2. Jika gagal (lokal), beralih ke .env
            creds_path = os.getenv("GOOGLE_SERVICE_JSON")
        except Exception:
             # Fallback terakhir jika st.secrets ada tapi kuncinya tidak ada
            creds_path = os.getenv("GOOGLE_SERVICE_JSON")

    if isinstance(creds_path, dict):
        # Jika creds dari st.secrets (sudah berbentuk dict)
        creds = Credentials.from_service_account_info(creds_path, scopes=scopes)
    elif isinstance(creds_path, str) and os.path.exists(creds_path):
        # Jika creds dari .env (berupa path file)
        creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
    else:
        st.error("Kredensial Google Service Account tidak ditemukan. Periksa file .env atau Streamlit Secrets Anda.", icon="🚨")
        return None
    
    client = gspread.authorize(creds)
    client.set_timeout(30)
    return client

def read_all_data(spreadsheet_id, creds):
    """
    Membaca 4 sheet data dari GSheet dengan cara yang "tahan banting".
    """
    client = get_gspread_client(creds) # Panggilan ini sekarang aman untuk di-cache
    if client is None:
        raise Exception("Gagal mendapatkan klien Google Sheet.")
    
    try:
        sh = client.open_by_key(spreadsheet_id)
        
        try:
            update_time = pd.to_datetime(sh.updated)
        except Exception:
            update_time = datetime.now() 
        
        def read_sheet_safely(ws_name, expected_cols):
            """
            (PERBAIKAN: Ini adalah logika paling aman untuk 'KeyError')
            """
            try:
                ws = sh.worksheet(ws_name)
                data = ws.get_values()
                
                if len(data) < 1: 
                    return pd.DataFrame(columns=expected_cols)

                gsheet_header = data[0]
                
                if len(data) < 2:
                    data_rows = []
                else:
                    data_rows = data[1:]

                df = pd.DataFrame(data_rows, columns=gsheet_header)
                df = df.reindex(columns=expected_cols) 
                return df
                
            except Exception as e:
                st.error(f"Gagal membaca nilai dari sheet '{ws_name}': {e}", icon="🚨")
                return pd.DataFrame(columns=expected_cols)

        # Gunakan fungsi aman yang baru
        pivot_df = read_sheet_safely("Pivot", PIVOT_COLS)
        daily_df = read_sheet_safely("Moves History", MOVES_COLS)
        inbound_df = read_sheet_safely("Inbound", MOVES_COLS)
        outbound_df = read_sheet_safely("Outbound", MOVES_COLS)

        # Post-process (konversi tipe data)
        pivot_df = _post_process_read_df(pivot_df, "Pivot")
        daily_df = _post_process_read_df(daily_df, "Moves History")
        inbound_df = _post_process_read_df(inbound_df, "Inbound")
        outbound_df = _post_process_read_df(outbound_df, "Outbound")

        return pivot_df, daily_df, inbound_df, outbound_df, update_time
        
    except APIError as e:
        raise Exception(f"Gagal membuka Spreadsheet. Periksa ID dan izin: {e}")
    except Exception as e:
        raise Exception(f"Gagal membaca Google Sheet saat startup: {e}")

def upload_all_data(spreadsheet_id, creds, inbound_df, outbound_df, pivot_df, daily_soh_df):
    """
    Mengunggah 4 DataFrame ke GSheet dengan chunking dan jeda.
    """
    client = get_gspread_client(creds) # Panggilan ini aman
    if client is None:
        raise Exception("Gagal mendapatkan klien Google Sheet untuk upload.")
    
    try:
        sh = client.open_by_key(spreadsheet_id)
    except Exception as e:
        st.error(f"Gagal membuka GSheet untuk upload. Periksa ID: {e}", icon="🚨")
        return None
    
    def upload_sheet(df, ws_name):
        """Helper untuk mengunggah satu sheet dengan chunking."""
        try:
            ws = sh.worksheet(ws_name)
            ws.clear()
            
            df_upload = df.fillna('').astype(str)
            df_upload.replace('NaT', '', inplace=True)
            
            header = df_upload.columns.tolist()
            values = df_upload.values.tolist()
            
            chunk_size = 2000
            total_chunks = (len(values) // chunk_size) + 1
            
            if len(values) > chunk_size:
                for i in range(0, len(values), chunk_size):
                    chunk = values[i:i+chunk_size]
                    if i == 0:
                        ws.update([header] + chunk, value_input_option='USER_ENTERED')
                    else:
                        ws.append_rows(chunk, value_input_option='USER_ENTERED')
                    
                    if total_chunks > 1:
                        time.sleep(1.5) 
            else:
                ws.update([header] + values, value_input_option='USER_ENTERED')
            
        except gspread.exceptions.WorksheetNotFound:
            st.error(f"Sheet '{ws_name}' tidak ditemukan di GSheet Anda!", icon="🚨")
            raise Exception(f"Worksheet {ws_name} not found")
        except Exception as e:
            st.error(f"Gagal mengunggah ke sheet '{ws_name}': {e}", icon="🚨")
            raise e

    try:
        # Upload satu per satu
        upload_sheet(pivot_df, "Pivot")
        time.sleep(2) # Jeda antar sheet
        upload_sheet(daily_soh_df, "Moves History")
        time.sleep(2)
        upload_sheet(inbound_df, "Inbound")
        time.sleep(2)
        upload_sheet(outbound_df, "Outbound")
        
        # Jika semua berhasil, kembalikan timestamp
        return datetime.now()

    except Exception as e:
        # Error sudah ditampilkan oleh upload_sheet
        return None