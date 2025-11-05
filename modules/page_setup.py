import streamlit as st

def setup_page():
    """
    Mengatur konfigurasi halaman Streamlit dan CSS kustom.
    (Nama fungsi diperbaiki menjadi setup_page)
    """
    st.set_page_config(
        page_title="Odoo Stock Dashboard",
        page_icon="📦",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # CSS Kustom untuk tampilan yang lebih bersih
    st.markdown("""
        <style>
            /* Sembunyikan footer Streamlit */
            footer {visibility: hidden;}
            
            /* Sembunyikan menu hamburger (opsional, jika ingin lebih bersih) */
            /* #MainMenu {visibility: hidden;} */
            
            /* Styling untuk container (jika digunakan) */
            .st-emotion-cache-1jicfl2 { 
                /* st.container(border=True) */
                border-radius: 0.5rem;
            }
            
            /* Mengurangi padding atas */
            .block-container {
                padding-top: 2rem;
                padding-bottom: 2rem;
                padding-left: 3rem;
                padding-right: 3rem;
            }

            /* Perbaikan kecil untuk delta 'st.metric' (agar tidak terpotong) */
            div[data-testid="stMetric"] div[data-testid="stMetricDelta"] {
                max-width: fit-content;
            }
        </style>
    """, unsafe_allow_html=True)

