import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import plotly.express as px

st.set_page_config(page_title="Mi Finanzas Pro", page_icon="📈", layout="wide")

# --- CONEXIÓN A GOOGLE SHEETS ---
@st.cache_resource
def conectar_google_sheets():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    # Lee las credenciales desde los secretos de Streamlit (nube) o un archivo local
    if "gcp_service_account" in st.secrets:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        # Para pruebas locales con tu archivo JSON descargado
        creds = ServiceAccountCredentials.from_json_keyfile_name('credenciales.json', scope)
    
    client = gspread.authorize(creds)
    # Abre la hoja por su nombre exacto en Google Drive
    sheet = client.open("Control de Gastos")
    return sheet

try:
    spreadsheet = conectar_google_sheets()
    hojas_disponibles = [worksheet.title for worksheet in spreadsheet.worksheets()]
except Exception as e:
    st.error(f"Error al conectar con Google Sheets: {e}")
    st.stop()

# --- BARRA LATERAL ---
st.sidebar.title("📈 Opciones")
hoja_seleccionada = st.sidebar.selectbox("📅 Selecciona el Periodo", hojas_disponibles)

# Cargar datos de la pestaña seleccionada
@st.cache_data(ttl=10)
def cargar_datos(nombre_hoja):
    worksheet = spreadsheet.worksheet(nombre_hoja)
    datos = worksheet.get_all_records()
    df = pd.DataFrame(datos)
    if not df.empty:
        df['Monto'] = pd.to_numeric(df['Monto'], errors='coerce').fillna(0)
        df['Presupuesto'] = pd.to_numeric(df['Presupuesto'], errors='coerce').fillna(0)
    return df

df = cargar_datos(hoja_seleccionada)

# --- CÁLCULOS FINANCIEROS ---
if not df.empty and 'Tipo' in df.columns:
    df_ingresos = df[df['Tipo'].str.lower() == 'ingreso']
    df_egresos = df[df['Tipo'].str.lower() == 'egreso']
    total_ingresos = df_ingresos['Monto'].sum()
    total_egresos = df_egresos['Monto'].sum()
else:
    total_ingresos = 0.0
    total_egresos = 0.0

saldo_actual = total_ingresos - total_egresos

# --- VISTA PRINCIPAL ---
st.title(f"Resumen Financiero: {hoja_seleccionada}")
tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "💰 Presupuestos", "📝 Registrar Movimiento"])

with tab1:
    col1, col2, col3 = st.columns(3)
    col1.metric("Ingresos del Mes", f"${total_ingresos:,.2f}")
    col2.metric("Total Gastado", f"${total_egresos:,.2f}")
    col3.metric("Saldo Disponible", f"${saldo_actual:,.2f}")

    st.divider()
    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        st.subheader("Gastos por Categoría")
        if not df.empty and 'Tipo' in df.columns and not df_egresos.empty:
            gastos_cat = df_egresos.groupby('Categoria')['Monto'].sum().reset_index()
            fig_pie = px.pie(gastos_cat, values='Monto', names='Categoria', hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("Sin registros de egresos para mostrar.")
            
    with col_chart2:
        st.subheader("Últimos Registros")
        if not df.empty:
            st.dataframe(df.tail(8), use_container_width=True, hide_index=True)

with tab2:
    st.subheader("Presupuesto vs Gasto Real")
    if not df.empty and 'Tipo' in df.columns and not df_egresos.empty:
        df_pres = df_egresos.groupby('Categoria')[['Presupuesto', 'Monto']].sum().reset_index()
        df_pres['Diferencia'] = df_pres['Presupuesto'] - df_pres['Monto']
        fig_bar = px.bar(df_pres, x='Categoria', y=['Presupuesto', 'Monto'], barmode='group')
        st.plotly_chart(fig_bar, use_container_width=True)
        st.dataframe(df_pres, use_container_width=True)

with tab3:
    with st.form("nuevo_registro", clear_on_submit=True):
        st.subheader("Nuevo Ingreso o Egreso")
        c1, c2, c3 = st.columns(3)
        with c1:
            fecha = st.date_input("Fecha", datetime.date.today()).strftime("%Y-%m-%d")
            mes = st.text_input("Mes", hoja_seleccionada)
            tipo = st.selectbox("Tipo", ["Egreso", "Ingreso"])
        with c2:
            categoria = st.selectbox("Categoría", ["Servicios", "Gastos", "Deudas", "Ahorro/Inversión", "Total Cuenta", "Sueldo"])
            concepto = st.text_input("Concepto")
        with c3:
            presupuesto = st.number_input("Presupuesto ($)", min_value=0.0)
            monto = st.number_input("Monto ($)", min_value=0.0)
            
        submit = st.form_submit_button("Guardar en Google Sheets", type="primary")
        
        if submit:
            try:
                worksheet = spreadsheet.worksheet(hoja_seleccionada)
                nueva_fila = [fecha, mes, tipo, categoria, concepto, presupuesto, monto]
                worksheet.append_row(nueva_fila)
                st.success("¡Guardado directamente en tu Google Sheet!")
                st.cache_data.clear()
            except Exception as e:
                st.error(f"Error al guardar: {e}")