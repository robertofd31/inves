import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px

# 1. CONFIGURACIÓN
st.set_page_config(page_title="Mi Cartera", page_icon="📈", layout="wide")

# 2. CONTRASEÑA
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False
    if st.session_state.password_correct:
        return True
    st.markdown("### 🔒 Acceso Restringido")
    pwd = st.text_input("Contraseña:", type="password")
    if pwd:
        if pwd == st.secrets["passwords"]["access_code"]:
            st.session_state.password_correct = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta")
    return False

if not check_password():
    st.stop()

# --- BARRA LATERAL ---
st.sidebar.title("Opciones")
debug_mode = st.sidebar.checkbox("🕵️‍♂️ Modo Debug (Ver datos crudos)")

st.title("📊 Dashboard Global de Inversiones")

# 3. CARGA DE DATOS
@st.cache_data(ttl=60) # Bajamos el caché a 60 segundos para pruebas
def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    # Leemos tal cual viene de Google
    df = conn.read(worksheet="0") 
    return df

try:
    df_raw = load_data()
except Exception as e:
    st.error(f"Error crítico conectando: {e}")
    st.stop()

# --- DIAGNÓSTICO (SOLO SI ACTIVAS EL CHECKBOX) ---
if debug_mode:
    st.warning("🚧 MODO DEBUG ACTIVADO 🚧")
    st.markdown("**1. Columnas detectadas:**")
    st.write(list(df_raw.columns))
    st.markdown("**2. Primeras 5 filas CRUDAS (sin tocar):**")
    st.dataframe(df_raw.head())
    st.markdown(f"**3. Total filas:** {len(df_raw)} | **Total columnas:** {len(df_raw.columns)}")

# 4. LIMPIEZA Y PREPARACIÓN

# A. Limpieza de nombres de columnas
# Quitamos espacios en blanco al principio y final de los nombres
df_raw.columns = df_raw.columns.str.strip()

# B. Renombrado INTELIGENTE
# Definimos los nombres que queremos
expected_cols = [
    "Fund ISIN", "Fondo", "Accion", "Ticker", "ISIN Security", 
    "Sector", "Pais", "Weight Fund", "Alloc", "Peso Real"
]

# Intentamos renombrar. Si hay menos columnas, rellenamos con cuidado.
# Esto evita el error si el Excel viene incompleto.
current_cols = list(df_raw.columns)
mapping = {}
for i, new_name in enumerate(expected_cols):
    if i < len(current_cols):
        mapping[current_cols[i]] = new_name

df_raw = df_raw.rename(columns=mapping)

# C. Limpieza de Números (Peso Real)
# Aseguramos que la columna existe
if "Peso Real" not in df_raw.columns:
    st.error(f"❌ No encuentro la columna del peso (Columna 10). Columnas actuales: {df_raw.columns.tolist()}")
    st.stop()

try:
    # Convertimos a string, limpiamos basura y pasamos a float
    df_raw['Peso Real'] = (
        df_raw['Peso Real']
        .astype(str)
        .str.replace('%', '', regex=False)
        .str.replace('€', '', regex=False)
        .str.replace('nan', '0', regex=False)
        .str.replace('.', '', regex=False) # Quitar punto de miles (Europa)
        .str.replace(',', '.', regex=False) # Cambiar coma decimal por punto
    )
    df_raw['Peso Real'] = pd.to_numeric(df_raw['Peso Real'], errors='coerce').fillna(0)
except Exception as e:
    st.error(f"Error limpiando números: {e}")

# Si estamos en debug, mostramos cómo quedó la columna peso
if debug_mode:
    st.markdown("**4. Columna 'Peso Real' después de limpiar:**")
    st.write(df_raw['Peso Real'].head())

# D. Agrupación
df = df_raw.groupby("Accion")[["Peso Real", "Pais", "Sector"]].agg({
    "Peso Real": "sum",
    "Pais": "first",
    "Sector": "first"
}).reset_index()

df = df.sort_values("Peso Real", ascending=False).reset_index(drop=True)

# 5. VISUALIZACIÓN (DASHBOARD)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Posiciones", len(df))
c2.metric("Paises", df['Pais'].nunique())
c3.metric("Sectores", df['Sector'].nunique())
c4.metric("Exposición Total", f"{df['Peso Real'].sum():.2f}%")

st.markdown("---")

# Gráficos
def prepare_pie_data(dataframe, col_name, threshold=0.5):
    grouped = dataframe.groupby(col_name)['Peso Real'].sum().reset_index()
    main = grouped[grouped['Peso Real'] >= threshold]
    others = grouped[grouped['Peso Real'] < threshold]
    if not others.empty:
        others_row = pd.DataFrame({col_name: [f'Otros (<{threshold}%)'], 'Peso Real': [others['Peso Real'].sum()]})
        return pd.concat([main, others_row])
    return main

col_left, col_right = st.columns(2)
with col_left:
    st.subheader("🌍 Distribución Geográfica")
    if not df.empty:
        df_pais = prepare_pie_data(df, "Pais")
        fig_p = px.pie(df_pais, values="Peso Real", names="Pais", hole=0.4)
        st.plotly_chart(fig_p, use_container_width=True)

with col_right:
    st.subheader("🏭 Distribución Sectorial")
    if not df.empty:
        df_sec = prepare_pie_data(df, "Sector")
        fig_s = px.pie(df_sec, values="Peso Real", names="Sector", hole=0.4)
        st.plotly_chart(fig_s, use_container_width=True)

st.subheader("🏆 Top 10 Posiciones")
if not df.empty:
    df_top10 = df.head(10).sort_values("Peso Real", ascending=True)
    fig_10 = px.bar(df_top10, x="Peso Real", y="Accion", orientation='h', text_auto='.2f', color="Peso Real")
    st.plotly_chart(fig_10, use_container_width=True)

st.subheader("🔍 Explorador")
if len(df) > 1:
    rango = st.slider("Rango:", 1, len(df), (11, min(25, len(df))))
    df_range = df.iloc[rango[0]-1 : rango[1]].sort_values("Peso Real", ascending=True)
    if not df_range.empty:
        fig_r = px.bar(df_range, x="Peso Real", y="Accion", orientation='h', text_auto='.2f', color="Peso Real")
        st.plotly_chart(fig_r, use_container_width=True)
