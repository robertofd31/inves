import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(
    page_title="Cartera Privada",
    page_icon="🔒",
    layout="wide"
)

# --- SISTEMA DE CONTRASEÑA SIMPLE ---
def check_password():
    """Retorna True si la contraseña es correcta."""
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False

    if st.session_state.password_correct:
        return True

    st.markdown("### 🔒 Acceso Restringido")
    pwd_input = st.text_input("Introduce la contraseña de acceso:", type="password")
    
    # Validación
    if pwd_input:
        # Busca la clave en secrets.toml bajo [passwords] access_code
        if pwd_input == st.secrets["passwords"]["access_code"]:
            st.session_state.password_correct = True
            st.rerun() # Recarga la página para mostrar contenido
        else:
            st.error("Contraseña incorrecta")
    
    return False

if not check_password():
    st.stop() # Detiene la ejecución si no hay login

# --- A PARTIR DE AQUÍ, SOLO SE VE SI HAY LOGIN ---

st.title("📊 Dashboard Global de Inversiones")

# 2. CARGA DE DATOS
@st.cache_data(ttl=600)
def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    # RECUERDA: Usa el GID (número) de la hoja como string. "0" suele ser la primera.
    df = conn.read(worksheet="0") 
    return df

try:
    df_raw = load_data()
except Exception as e:
    st.error(f"Error conectando a Google Sheets: {e}")
    st.stop()

# 3. LIMPIEZA Y PREPARACIÓN
# Convertir peso a numérico
if df_raw['Real Weight in Portfolio (%)'].dtype == 'O':
    df_raw['Peso Real'] = df_raw['Real Weight in Portfolio (%)'].astype(str).str.replace('%','').str.replace(',','.').astype(float)
else:
    df_raw['Peso Real'] = df_raw['Real Weight in Portfolio (%)']

df_raw = df_raw.rename(columns={"Security Name": "Accion", "Country": "Pais", "Fund Name": "Fondo"})

# --- AGRUPACIÓN PRINCIPAL ---
# Sumamos pesos por si una acción está en varios fondos
df = df_raw.groupby("Accion")[["Peso Real", "Pais", "Sector"]].agg({
    "Peso Real": "sum",
    "Pais": "first",
    "Sector": "first"
}).reset_index()

# Ordenamos por peso de mayor a menor
df = df.sort_values("Peso Real", ascending=False).reset_index(drop=True)

# 4. MÉTRICAS (KPIs)
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Posiciones", len(df))
with col2:
    st.metric("Paises Distintos", df['Pais'].nunique())
with col3:
    st.metric("Sectores Distintos", df['Sector'].nunique())
with col4:
    st.metric("Exposición Total", f"{df['Peso Real'].sum():.2f}%")

st.markdown("---")

# 5. GRÁFICOS CIRCULARES (PIE CHARTS) CON LÓGICA DE 0.5%
def prepare_pie_data(dataframe, column_name, threshold=0.5):
    """Agrupa valores menores al threshold en 'Otros' para limpiar el gráfico"""
    grouped = dataframe.groupby(column_name)['Peso Real'].sum().reset_index()
    
    # Separar grandes y pequeños
    main_data = grouped[grouped['Peso Real'] >= threshold]
    small_data = grouped[grouped['Peso Real'] < threshold]
    
    # Crear fila de 'Otros'
    if not small_data.empty:
        others_row = pd.DataFrame({
            column_name: [f'Otros (<{threshold}%)'],
            'Peso Real': [small_data['Peso Real'].sum()]
        })
        return pd.concat([main_data, others_row])
    return main_data

col_left, col_right = st.columns(2)

with col_left:
    st.subheader("🌍 Por País")
    df_pais_clean = prepare_pie_data(df, "Pais")
    fig_pais = px.pie(df_pais_clean, values="Peso Real", names="Pais", hole=0.4)
    fig_pais.update_traces(textposition='inside', textinfo='percent+label')
    st.plotly_chart(fig_pais, use_container_width=True)

with col_right:
    st.subheader("🏭 Por Sector")
    df_sector_clean = prepare_pie_data(df, "Sector")
    fig_sector = px.pie(df_sector_clean, values="Peso Real", names="Sector", hole=0.4)
    fig_sector.update_traces(textposition='inside', textinfo='percent+label')
    st.plotly_chart(fig_sector, use_container_width=True)

# 6. GRÁFICOS DE BARRAS HORIZONTALES

# A) TOP 10 FIJO
st.subheader("🏆 Top 10 Posiciones (Mayor Peso)")
df_top10 = df.head(10).sort_values("Peso Real", ascending=True) # Ascendente para que Plotly lo pinte de arriba a abajo bien

fig_bar_10 = px.bar(
    df_top10, 
    x="Peso Real", 
    y="Accion", 
    orientation='h',
    text_auto='.2f',
    color="Peso Real",
    color_continuous_scale="Blues"
)
fig_bar_10.update_layout(showlegend=False, xaxis_title="Peso en Cartera (%)", yaxis_title="")
st.plotly_chart(fig_bar_10, use_container_width=True)

# B) RANGO SELECCIONABLE (Por defecto 11-25)
st.subheader("🔍 Analizar resto de posiciones")

# Deslizador doble para elegir rango
# Max value es el total de filas del dataframe
total_rows = len(df)
rango = st.slider(
    "Selecciona el rango de posiciones a visualizar:",
    min_value=1,
    max_value=total_rows,
    value=(11, 25) # Valor por defecto
)

start_idx = rango[0] - 1 # Ajuste base 0 de Python
end_idx = rango[1]

# Filtrar datos
df_range = df.iloc[start_idx:end_idx].sort_values("Peso Real", ascending=True)

if not df_range.empty:
    fig_bar_range = px.bar(
        df_range, 
        x="Peso Real", 
        y="Accion", 
        orientation='h',
        text_auto='.2f',
        color="Peso Real",
        color_continuous_scale="Teal" # Color distinto para diferenciar
    )
    fig_bar_range.update_layout(
        title=f"Posiciones de la {rango[0]} a la {rango[1]}",
        showlegend=False, 
        xaxis_title="Peso en Cartera (%)", 
        yaxis_title=""
    )
    st.plotly_chart(fig_bar_range, use_container_width=True)
else:
    st.warning("El rango seleccionado está fuera de los límites de datos.")
