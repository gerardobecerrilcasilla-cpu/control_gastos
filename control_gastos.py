import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import datetime
import plotly.express as px

st.set_page_config(page_title="Mi Finanzas Pro", page_icon="📈", layout="wide")

# --- CONEXIÓN A GOOGLE SHEETS ---
@st.cache_resource
def conectar_google_sheets():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    if "gcp_service_account" in st.secrets:
        creds_dict = dict(st.secrets["gcp_service_account"])
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    else:
        credentials = Credentials.from_service_account_file("credenciales.json", scopes=scopes)
    
    gc = gspread.authorize(credentials)
    return gc.open("Control de Gastos")

# 1. Intento de Conexión
try:
    spreadsheet = conectar_google_sheets()
    worksheets = spreadsheet.worksheets()
    hojas_disponibles = [ws.title for ws in worksheets]
except Exception as e:
    st.error(f"Error al conectar con Google Sheets: {e}")
    st.info("💡 Verifica permisos de Editor al correo de la cuenta de servicio y que el archivo se llame exactamente 'Control de Gastos'.")
    st.stop()

if not hojas_disponibles:
    st.warning("Tu hoja de Google Sheets no tiene pestañas.")
    st.stop()

# --- BARRA LATERAL ---
st.sidebar.title("📈 Opciones")
hoja_seleccionada = st.sidebar.selectbox("📅 Selecciona el Periodo", hojas_disponibles)

# Cargar datos de forma segura
@st.cache_data(ttl=5)
def cargar_datos(nombre_hoja):
    try:
        worksheet = spreadsheet.worksheet(nombre_hoja)
        datos = worksheet.get_all_records()
        df = pd.DataFrame(datos)
        
        # Asegurar columnas numéricas si existen
        if 'Monto' in df.columns:
            df['Monto'] = pd.to_numeric(df['Monto'], errors='coerce').fillna(0)
        else:
            df['Monto'] = 0.0

        if 'Presupuesto' in df.columns:
            df['Presupuesto'] = pd.to_numeric(df['Presupuesto'], errors='coerce').fillna(0)
        else:
            df['Presupuesto'] = 0.0

        return df
    except Exception as e:
        st.warning(f"No se pudieron leer registros en '{nombre_hoja}'. Asegúrate de que la Fila 1 tenga los nombres de las columnas.")
        return pd.DataFrame()

df = cargar_datos(hoja_seleccionada)

# --- CÁLCULOS FINANCIEROS ---
if not df.empty and 'Tipo' in df.columns:
    df_ingresos = df[df['Tipo'].astype(str).str.lower() == 'ingreso']
    df_egresos = df[df['Tipo'].astype(str).str.lower() == 'egreso']
    total_ingresos = df_ingresos['Monto'].sum()
    total_egresos = df_egresos['Monto'].sum()
else:
    total_ingresos = 0.0
    total_egresos = 0.0
    df_egresos = pd.DataFrame()

saldo_actual = total_ingresos - total_egresos

# --- INTERFAZ PRINCIPAL ---
st.title(f"Resumen Financiero: {hoja_seleccionada}")
tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "💰 Presupuestos", "📝 Registrar Movimiento"])

# Pestaña 1: Dashboard
with tab1:
    col1, col2, col3 = st.columns(3)
    col1.metric("Ingresos del Mes", f"${total_ingresos:,.2f}")
    col2.metric("Total Gastado", f"${total_egresos:,.2f}")
    col3.metric("Saldo Disponible", f"${saldo_actual:,.2f}")

    st.divider()
    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        st.subheader("Gastos por Categoría")
        if not df_egresos.empty and 'Categoria' in df_egresos.columns and total_egresos > 0:
            gastos_cat = df_egresos.groupby('Categoria')['Monto'].sum().reset_index()
            fig_pie = px.pie(gastos_cat, values='Monto', names='Categoria', hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No hay egresos registrados en esta pestaña para graficar.")

    with col_chart2:
        st.subheader("Últimos Registros")
        if not df.empty:
            st.dataframe(df.tail(8), use_container_width=True, hide_index=True)
        else:
            st.info("La pestaña está vacía. Añade movimientos en la pestaña 'Registrar Movimiento'.")

# Pestaña 2: Presupuestos
with tab2:
    st.subheader("Presupuesto vs Gasto Real")
    if not df_egresos.empty and 'Categoria' in df_egresos.columns:
        df_pres = df_egresos.groupby('Categoria')[['Presupuesto', 'Monto']].sum().reset_index()
        df_pres['Diferencia'] = df_pres['Presupuesto'] - df_pres['Monto']
        fig_bar = px.bar(df_pres, x='Categoria', y=['Presupuesto', 'Monto'], barmode='group')
        st.plotly_chart(fig_bar, use_container_width=True)
        st.dataframe(df_pres, use_container_width=True)
    else:
        st.info("No hay datos de egresos para mostrar comparativa de presupuesto.")

# Pestaña 3: Formulario
with tab3:
    with st.form("nuevo_registro", clear_on_submit=True):
        st.subheader("Nuevo Ingreso o Egreso")
        c1, c2, c3 = st.columns(3)
        with c1:
            fecha = st.date_input("Fecha", datetime.date.today()).strftime("%Y-%m-%d")
            mes = st.text_input("Mes", hoja_seleccionada)
            tipo = st.selectbox("Tipo", ["Egreso", "Ingreso"])
        with c2:
            categoria = st.selectbox("Categoría", ["Servicios", "Gastos", "Deudas", "Ahorro/Inversión", "Total Cuenta", "Sueldo/Honorarios"])
            concepto = st.text_input("Concepto")
        with c3:
            presupuesto = st.number_input("Presupuesto ($)", min_value=0.0, step=10.0)
            monto = st.number_input("Monto ($)", min_value=0.0, step=10.0)
            
        submit = st.form_submit_button("Guardar en Google Sheets", type="primary")
        
        if submit:
            try:
                worksheet = spreadsheet.worksheet(hoja_seleccionada)
                # Formato en Fila 1: Fecha, Mes, Tipo, Categoria, Concepto, Presupuesto, Monto
                nueva_fila = [fecha, mes, tipo, categoria, concepto, presupuesto, monto]
                worksheet.append_row(nueva_fila)
                st.success("¡Guardado correctamente!")
                st.cache_data.clear()
            except Exception as e:
                st.error(f"Error al guardar: {e}")
