import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import datetime
import plotly.express as px

st.set_page_config(page_title="Mi Finanzas Pro", page_icon="📈", layout="wide")

# --- 1. CONFIGURACIÓN DE PRESUPUESTOS BASE ---
PRESUPUESTOS_BASE = {
    "Vivienda y Servicios (Luz/Gas/Internet)": 1500.0,
    "Alimentación y Supermercado": 2000.0,
    "Transporte (Gasolina/Estacionamiento/reparaciones)": 5000.0,
    "Salud, Suplementos y Gimnasio": 1000.0,
    "Mascotas (Alimento/Veterinario)": 700.0,
    "Entretenimiento (Netflix/Cine/Juegos)": 500.0,
    "Gastos Personales (Ropa/Corte/Hobbies)": 120.0,
    "Insumos Proyecto Ivora": 0.0,
    "Ahorro e Inversión": 3000.0,
    "Deudas y Tarjetas": 3000.0,
    "Sueldo/Honorarios": 0.0,
    "Otros / Varios": 500.0
}

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

# --- PESTAÑA 2: PRESUPUESTO CORREGIDO ---
with tab2:
    st.subheader("Presupuesto vs Gasto Real")
    
    # Creamos un DataFrame con el presupuesto fijo dictado por el código
    df_presupuestos_fijos = pd.DataFrame(list(PRESUPUESTOS_BASE.items()), columns=['Categoria', 'Presupuesto'])
    
    if not df_egresos.empty and 'Categoria' in df_egresos.columns:
        # Sumamos solo lo que has gastado
        gastos_reales = df_egresos.groupby('Categoria')['Monto'].sum().reset_index()
        
        # Juntamos los gastos reales con el límite de tu presupuesto fijo
        df_pres = pd.merge(df_presupuestos_fijos, gastos_reales, on='Categoria', how='left').fillna(0)
        df_pres = df_pres[df_pres['Presupuesto'] > 0] # Mostrar solo las que tienen presupuesto asignado
        
        df_pres['Diferencia'] = df_pres['Presupuesto'] - df_pres['Monto']
        
        fig_bar = px.bar(df_pres, x='Categoria', y=['Presupuesto', 'Monto'], barmode='group')
        st.plotly_chart(fig_bar, use_container_width=True)
        st.dataframe(df_pres.style.format({'Presupuesto': '${:,.2f}', 'Monto': '${:,.2f}', 'Diferencia': '${:,.2f}'}), use_container_width=True)
    else:
        st.info("Sin datos de egresos para comparar.")

# --- PESTAÑA 3: FORMULARIO REACTIVO (EN VIVO) ---
with tab3:
    st.subheader("Capturar Transacción")
    
    # Quitamos el "with st.form" para que la pantalla reaccione de inmediato
    c1, c2, c3 = st.columns(3)
    
    with c1:
        fecha = st.date_input("Fecha", datetime.date.today()).strftime("%Y-%m-%d")
        lista_meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        mes = st.selectbox("Mes", lista_meses)
        tipo = st.selectbox("Tipo de Movimiento", ["Egreso", "Ingreso"])
        
    with c2:
        categoria_seleccionada = st.selectbox("Categoría", list(PRESUPUESTOS_BASE.keys()))
        concepto = st.text_input("Concepto / Detalle (Opcional)")
        
        # --- LÓGICA EN VIVO: Calcular cuánto queda de esta categoría ---
        limite_categoria = PRESUPUESTOS_BASE.get(categoria_seleccionada, 0.0)
        
        gasto_acumulado = 0.0
        if not df_egresos.empty and 'Categoria' in df_egresos.columns:
            gasto_acumulado = df_egresos[df_egresos['Categoria'] == categoria_seleccionada]['Monto'].sum()
            
        disponible = limite_categoria - gasto_acumulado
        
        # Mostramos la alerta de dinero restante
        if tipo == "Egreso":
            if disponible >= 0:
                st.info(f"💡 Presupuesto: **${limite_categoria:,.2f}** | Disponible: **${disponible:,.2f}**")
            else:
                st.error(f"⚠️ ¡Te has excedido! Presupuesto: **${limite_categoria:,.2f}** | Disponible: **${disponible:,.2f}**")
        else:
            st.success("💰 Al ser Ingreso, no afecta presupuestos.")
            
    with c3:
        monto = st.number_input("Monto Real ($)", min_value=0.0, step=10.0)
        metodo_pago = st.selectbox("Método de Pago", ["Tarjeta (Crédito/Débito)", "Efectivo", "Transferencia", "Vales / App"])
        
        es_tarjeta = (metodo_pago == "Tarjeta (Crédito/Débito)")
        lista_tarjetas = [
            "N/A", "Débito Nómina", "Débito Mercado Libre", "Débito Nu", 
            "Crédito Nu", "Débito BBVA", "Crédito BBVA", "Crédito Mercado Libre", 
            "Crédito Santander", "Crédito Perro", "Otra"
        ]
        tarjeta_especifica = st.selectbox("¿Qué Tarjeta usaste?", lista_tarjetas, disabled=not es_tarjeta)
        
    # El botón ahora está suelto (no amarrado a un st.form)
    if st.button("Guardar Registro", type="primary"):
        try:
            presupuesto_asignado = limite_categoria if tipo == "Egreso" else 0.0
            
            if not es_tarjeta:
                tarjeta_especifica = "N/A"
                
            worksheet = spreadsheet.worksheet(hoja_seleccionada)
            nueva_fila = [fecha, mes, tipo, categoria_seleccionada, concepto, presupuesto_asignado, monto, metodo_pago, tarjeta_especifica]
            worksheet.append_row(nueva_fila)
            st.success(f"¡Registro guardado! (Gastaste ${monto:,.2f} en {categoria_seleccionada})")
            st.cache_data.clear()
            st.rerun() # Fuerza a recargar la página para limpiar los campos y actualizar saldos
        except Exception as e:
            st.error(f"Error al guardar: {e}. Verifica que añadiste las nuevas columnas en Google Sheets.")
