import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import datetime
import plotly.express as px

# Configuración inicial de la página
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

try:
    spreadsheet = conectar_google_sheets()
    worksheets = spreadsheet.worksheets()
    hojas_disponibles = [ws.title for ws in worksheets]
except Exception as e:
    st.error(f"Error al conectar con Google Sheets: {e}")
    st.stop()

if not hojas_disponibles:
    st.warning("Tu archivo de Google Sheets no tiene pestañas disponibles.")
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
        
        # Limpieza de columnas numéricas
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
        st.warning(f"No se pudieron leer registros en '{nombre_hoja}'.")
        return pd.DataFrame()

df = cargar_datos(hoja_seleccionada)

# --- CÁLCULOS FINANCIEROS Y LIMPIEZA DE DATOS EXHAUSTIVA ---
if not df.empty and 'Tipo' in df.columns:
    # 1. Convertimos a string, quitamos todos los espacios y pasamos a minúsculas
    tipo_limpio = df['Tipo'].astype(str).str.replace(' ', '').str.strip().str.lower()
    
    # 2. Usamos contains para atrapar "ingreso", "ingresos", etc.
    df_ingresos = df[tipo_limpio.str.contains('ingreso', na=False)]
    df_egresos = df[tipo_limpio.str.contains('egreso', na=False)]
    
    total_ingresos = df_ingresos['Monto'].sum()
    total_egresos = df_egresos['Monto'].sum()
    
    # Herramienta oculta por si necesitas ver qué pasa en el futuro
    with st.expander("🛠️ Depuración de Datos"):
        st.write("Valores encontrados en la columna 'Tipo':", df['Tipo'].unique())
        st.write("Columnas detectadas:", df.columns.tolist())
else:
    total_ingresos = 0.0
    total_egresos = 0.0
    df_ingresos = pd.DataFrame()
    df_egresos = pd.DataFrame()

saldo_actual = total_ingresos - total_egresos

# --- VISTA PRINCIPAL ---
st.title(f"Resumen Financiero: {hoja_seleccionada}")
tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "💰 Presupuestos", "📝 Registrar Movimiento"])

# --- PESTAÑA 1: DASHBOARD ---
with tab1:
    col1, col2, col3 = st.columns(3)
    col1.metric("Ingresos del Mes", f"${total_ingresos:,.2f}")
    col2.metric("Total Gastado", f"${total_egresos:,.2f}")
    
    saldo_color = "normal" if saldo_actual >= 0 else "inverse"
    col3.metric("Saldo Disponible", f"${saldo_actual:,.2f}", delta_color=saldo_color)

    st.divider()
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.subheader("Distribución de Gastos")
        if not df_egresos.empty and 'Categoria' in df_egresos.columns and total_egresos > 0:
            gastos_cat = df_egresos.groupby('Categoria')['Monto'].sum().reset_index()
            fig_pie = px.pie(gastos_cat, values='Monto', names='Categoria', hole=0.4,
                             color_discrete_sequence=px.colors.sequential.Teal)
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No hay egresos para graficar.")
            
    with col_chart2:
        st.subheader("Últimos Registros")
        if not df.empty:
            st.dataframe(df.tail(8), use_container_width=True, hide_index=True)
        else:
            st.info("Sin registros.")

# --- PESTAÑA 2: PRESUPUESTOS ---
with tab2:
    st.subheader("Presupuesto vs Gasto Real")
    if not df_egresos.empty and 'Categoria' in df_egresos.columns:
        df_pres = df_egresos.groupby('Categoria')[['Presupuesto', 'Monto']].sum().reset_index()
        df_pres['Diferencia'] = df_pres['Presupuesto'] - df_pres['Monto']
        
        fig_bar = px.bar(df_pres, x='Categoria', y=['Presupuesto', 'Monto'], barmode='group',
                         color_discrete_map={'Presupuesto': '#A5D6A7', 'Monto': '#EF9A9A'})
        st.plotly_chart(fig_bar, use_container_width=True)
        st.dataframe(df_pres.style.format({'Presupuesto': '${:.2f}', 'Monto': '${:.2f}', 'Diferencia': '${:.2f}'}), use_container_width=True)
    else:
        st.info("No hay datos comparativos.")

# --- PESTAÑA 3: FORMULARIO DE CAPTURA ---
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
            concepto = st.text_input("Concepto / Detalle")
            
        with c3:
            presupuesto = st.number_input("Presupuesto ($)", min_value=0.0, step=10.0)
            monto = st.number_input("Monto ($)", min_value=0.0, step=10.0)
            
        submit = st.form_submit_button("Guardar Registro", type="primary")
        
        if submit:
            try:
                worksheet = spreadsheet.worksheet(hoja_seleccionada)
                nueva_fila = [fecha, mes, tipo, categoria, concepto, presupuesto, monto]
                worksheet.append_row(nueva_fila)
                st.success("¡Registro guardado exitosamente!")
                st.cache_data.clear()
            except Exception as e:
                st.error(f"Error al guardar: {e}")
