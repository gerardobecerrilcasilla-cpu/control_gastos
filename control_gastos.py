import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import datetime
import plotly.express as px

st.set_page_config(page_title="Mi Finanzas Pro", page_icon="📈", layout="wide")

# --- CONEXIÓN MODERNA Y SEGURA A GOOGLE SHEETS ---
@st.cache_resource
def conectar_google_sheets():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # Intenta leer desde los secrets de Streamlit Cloud
    if "gcp_service_account" in st.secrets:
        creds_dict = dict(st.secrets["gcp_service_account"])
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    else:
        # Si estás en local
        credentials = Credentials.from_service_account_file("credenciales.json", scopes=scopes)
    
    gc = gspread.authorize(credentials)
    
    # ABRE TU HOJA EN GOOGLE DRIVE
    # Asegúrate de que tu hoja en Google Sheets se llame exactamente "Control de Gastos"
    return gc.open("Control de Gastos")

try:
    spreadsheet = conectar_google_sheets()
    hojas_disponibles = [worksheet.title for worksheet in spreadsheet.worksheets()]
except Exception as e:
    st.error(f"Error al conectar con Google Sheets: {e}")
    st.info("💡 Verifica que le hayas compartido la hoja en Google Drive al correo de la cuenta de servicio con permisos de Editor.")
    st.stop()
