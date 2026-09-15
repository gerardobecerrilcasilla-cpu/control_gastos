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
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
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
    st.warning("Tu archivo no tiene pestañas.")
    st.stop()

st.sidebar.title("📈 Opciones")
hoja_seleccionada = st.sidebar.selectbox("📅 Selecciona el Periodo", hojas_disponibles)

# --- CARGAR DATOS ---
@st.cache_data(ttl=5)
def cargar_datos(nombre_hoja):
    try:
        worksheet = spreadsheet.worksheet(nombre_hoja)
        datos = worksheet.get_all_records()
        df = pd.DataFrame(datos)
        
        def limpiar_moneda(valor):
            if isinstance(valor, str):
                valor = valor.replace('$', '').replace(',', '').strip()
            return pd.to_numeric(valor, errors='coerce')

        if 'Monto' in df.columns:
            df['Monto'] = df['Monto'].apply(limpiar_moneda).fillna(0)
        else:
            df['Monto'] = 0.0

        if 'Presupuesto' in df.columns:
            df['Presupuesto'] = df['Presupuesto'].apply(limpiar_moneda).fillna(0)
        else:
            df['Presupuesto'] = 0.0

        return df
    except Exception as e:
        st.warning(f"Error al leer la hoja. ¿Están las columnas correctas? Detalles: {e}")
        return pd.DataFrame()

df = cargar_datos(hoja_seleccionada)

# --- CÁLCULOS FINANCIEROS ---
if not df.empty and 'Tipo' in df.columns:
    tipo_limpio = df['Tipo'].astype(str).str.replace(' ', '').str.strip().str.lower()
    df_ingresos = df[tipo_limpio.str.contains('ingreso', na=False)]
    df_egresos = df[tipo_limpio.str.contains('egreso', na=False)]
    total_ingresos = df_ingresos['Monto'].sum()
    total_egresos = df_egresos['Monto'].sum()
else:
    total_ingresos = 0.0
    total_egresos = 0.0
    df_ingresos = pd.DataFrame()
    df_egresos = pd.DataFrame()

saldo_actual = total_ingresos - total_egresos

# --- VISTA PRINCIPAL ---
st.title(f"Resumen Financiero: {hoja_seleccionada}")
tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "💰 Presupuestos", "📝 Registrar Movimiento"])

with tab1:
    col1, col2, col3 = st.columns(3)
    col1.metric("Ingresos de la quincena", f"${total_ingresos:,.2f}")
    col2.metric("Total Gastado", f"${total_egresos:,.2f}")
    saldo_color = "normal" if saldo_actual >= 0 else "inverse"
    col3.metric("Saldo Disponible", f"${saldo_actual:,.2f}", delta_color=saldo_color)

    st.divider()
    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        st.subheader("Gastos por Categoría")
        if not df_egresos.empty and 'Categoria' in df_egresos.columns and total_egresos > 0:
            gastos_cat = df_egresos.groupby('Categoria')['Monto'].sum().reset_index()
            fig_pie = px.pie(gastos_cat, values='Monto', names='Categoria', hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("Sin egresos.")
            
    with col_chart2:
        st.subheader("Últimos Registros")
        if not df.empty:
            cols_mostrar = [c for c in ['Fecha', 'Categoria', 'Monto', 'Metodo_Pago'] if c in df.columns]
            st.dataframe(df[cols_mostrar].tail(8), use_container_width=True, hide_index=True)
        else:
            st.info("Sin registros.")

with tab2:
    st.subheader("Presupuesto vs Gasto Real")
    if not df_egresos.empty and 'Categoria' in df_egresos.columns:
        df_pres = df_egresos.groupby('Categoria')[['Presupuesto', 'Monto']].sum().reset_index()
        df_pres['Diferencia'] = df_pres['Presupuesto'] - df_pres['Monto']
        fig_bar = px.bar(df_pres, x='Categoria', y=['Presupuesto', 'Monto'], barmode='group')
        st.plotly_chart(fig_bar, use_container_width=True)
        st.dataframe(df_pres.style.format({'Presupuesto': '${:,.2f}', 'Monto': '${:,.2f}', 'Diferencia': '${:,.2f}'}), use_container_width=True)
    else:
        st.info("Sin datos.")

with tab3:
    with st.form("nuevo_registro", clear_on_submit=True):
        st.subheader("Capturar Transacción")
        c1, c2, c3 = st.columns(3)
        
        with c1:
            fecha = st.date_input("Fecha", datetime.date.today()).strftime("%Y-%m-%d")
            
            # --- MEJORA: Mes como lista desplegable ---
            lista_meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
            mes = st.selectbox("Mes", lista_meses)
            
            tipo = st.selectbox("Tipo de Movimiento", ["Egreso", "Ingreso"])
            
        with c2:
            # Lista de categorías actualizada
            categorias_lista = [
                "Vivienda y Servicios (Luz/Gas/Internet)", "Alimentación y Supermercado", 
                "Transporte (Gasolina/Estacionamiento/Ecobici)", "Salud, Suplementos y Gimnasio", 
                "Mascotas (Alimento/Veterinario)", "Entretenimiento (Netflix/Cine/Juegos)", 
                "Gastos Personales (Ropa/Corte/Hobbies)", "Insumos Proyecto Ivora", 
                "Ahorro e Inversión", "Deudas y Tarjetas", "Sueldo/Honorarios", "Otros / Varios"
            ]
            categoria_seleccionada = st.selectbox("Categoría", categorias_lista)
            
            concepto = st.text_input("Concepto")
            
            # --- MEJORA: Presupuesto asignado manualmente ---
            presupuesto_asignado = st.number_input("Presupuesto ($)", min_value=0.0, step=10.0)
            
        with c3:
            monto = st.number_input("Monto Real ($)", min_value=0.0, step=10.0)
            metodo_pago = st.selectbox("Método de Pago", ["Tarjeta (Crédito/Débito)", "Efectivo", "Transferencia", "Vales / App"])
            
            # --- MEJORA: Activación/Desactivación dinámica del campo Tarjeta ---
            es_tarjeta = (metodo_pago == "Tarjeta (Crédito/Débito)")
            lista_tarjetas = [
                "N/A", "Débito Nómina", "Débito Mercado Libre", "Débito Nu", 
                "Crédito Nu", "Débito BBVA", "Crédito BBVA", "Crédito Mercado Libre", 
                "Crédito Santander", "Crédito Perro", "Otra"
            ]
            
            tarjeta_especifica = st.selectbox(
                "¿Qué Tarjeta usaste?", 
                lista_tarjetas, 
                disabled=not es_tarjeta  # Se desactiva si no eligió tarjeta
            )
            
        submit = st.form_submit_button("Guardar Registro", type="primary")
        
        if submit:
            try:
                # Si el campo de tarjeta estaba desactivado, forzamos que se guarde como N/A
                if not es_tarjeta:
                    tarjeta_especifica = "N/A"
                    
                worksheet = spreadsheet.worksheet(hoja_seleccionada)
                # Fila exacta: Fecha, Mes, Tipo, Categoria, Concepto, Presupuesto, Monto, Metodo_Pago, Tarjeta
                nueva_fila = [fecha, mes, tipo, categoria_seleccionada, concepto, presupuesto_asignado, monto, metodo_pago, tarjeta_especifica]
                worksheet.append_row(nueva_fila)
                st.success("¡Registro guardado con éxito!")
                st.cache_data.clear()
            except Exception as e:
                st.error(f"Error al guardar: {e}. Verifica que añadiste las nuevas columnas en Google Sheets.")
