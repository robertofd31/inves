import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px

# 1. CONFIGURACIÓN
st.set_page_config(page_title="Mi Cartera", page_icon="📈", layout="wide")

# 2. CONTRASEÑA
def check_password():
    """Gestión simple de contraseña."""
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False

    if st.session_state.password_correct:
        return True

    st.markdown("### 🔒 Acceso Restringido")
    pwd = st.text_input("Contraseña:", type="password")
    
    if pwd:
        # Verifica contra secrets.toml
        if pwd == st.secrets["passwords"]["access_code"]:
            st.session_state.password_correct = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta")
    return False

if not check_password():
    st.stop()

# --- BARRA LATERAL ---
st.title("📊 Dashboard Global de Inversiones")

# 3. CARGA DE DATOS
@st.cache_data(ttl=60) 
def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    # Usamos el ID de la hoja que confirmaste que funciona
    df = conn.read(worksheet="598707666") 
    return df

try:
    df_raw = load_data()
except Exception as e:
    st.error(f"Error crítico conectando: {e}")
    st.stop()

# --- DIAGNÓSTICO ---
if debug_mode:
    st.warning("🚧 MODO DEBUG ACTIVADO 🚧")
    st.markdown("**Columnas detectadas:**")
    st.write(list(df_raw.columns))
    st.dataframe(df_raw.head())

# 4. LIMPIEZA Y PREPARACIÓN

# A. Limpieza de nombres de columnas
df_raw.columns = df_raw.columns.str.strip()

# B. Renombrado INTELIGENTE (Mapeo por posición para evitar errores)
expected_cols = [
    "Fund ISIN", "Fondo", "Accion", "Ticker", "ISIN Security", 
    "Sector", "Pais", "Weight Fund", "Alloc", "Peso Real"
]
current_cols = list(df_raw.columns)
mapping = {}
for i, new_name in enumerate(expected_cols):
    if i < len(current_cols):
        mapping[current_cols[i]] = new_name

df_raw = df_raw.rename(columns=mapping)

# C. Limpieza de Números (Peso Real)
if "Peso Real" not in df_raw.columns:
    st.error(f"❌ No encuentro la columna del peso (Columna 10).")
    st.stop()

try:
    df_raw['Peso Real'] = (
        df_raw['Peso Real']
        .astype(str)
        .str.replace('%', '', regex=False)
        .str.replace('€', '', regex=False)
        .str.replace('nan', '0', regex=False)
        .str.replace('.', '', regex=False) # Quitar punto de miles (Europa)
        .str.replace(',', '.', regex=False) # Cambiar coma por punto decimal
    )
    df_raw['Peso Real'] = pd.to_numeric(df_raw['Peso Real'], errors='coerce').fillna(0)
except Exception as e:
    st.error(f"Error limpiando números: {e}")

# D. Agrupación (Consolidar acciones repetidas)
df = df_raw.groupby("Accion")[["Peso Real", "Pais", "Sector"]].agg({
    "Peso Real": "sum",
    "Pais": "first",
    "Sector": "first"
}).reset_index()

# Ordenamos de mayor a menor
df = df.sort_values("Peso Real", ascending=False).reset_index(drop=True)

# 5. VISUALIZACIÓN (KPIs)
# Solo 3 columnas (hemos quitado Exposición Total)
c1, c2, c3 = st.columns(3)
c1.metric("Posiciones", len(df))
c2.metric("Paises", df['Pais'].nunique())
c3.metric("Sectores", df['Sector'].nunique())

st.markdown("---")

# --- LÓGICA DE GRÁFICOS (Pastel) ---
def prepare_pie_data(dataframe, col_name, threshold=0.5):
    """Agrupa valores pequeños en 'Otros'."""
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
        # Etiquetas DENTRO para limpieza visual
        fig_p.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_p, use_container_width=True)

with col_right:
    st.subheader("🏭 Distribución Sectorial")
    if not df.empty:
        df_sec = prepare_pie_data(df, "Sector")
        fig_s = px.pie(df_sec, values="Peso Real", names="Sector", hole=0.4)
        # Etiquetas DENTRO para limpieza visual
        fig_s.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_s, use_container_width=True)

# --- GRÁFICOS DE BARRAS ---

# 1. Top 10 Fijo
st.subheader("🏆 Top 10 Posiciones")
if not df.empty:
    df_top10 = df.head(10).sort_values("Peso Real", ascending=True)
    fig_10 = px.bar(
        df_top10, 
        x="Peso Real", 
        y="Accion", 
        orientation='h', 
        text_auto='.2f', 
        color="Peso Real"
    )
    fig_10.update_layout(showlegend=False, xaxis_title="Peso (%)", yaxis_title="")
    st.plotly_chart(fig_10, use_container_width=True)

# 2. Explorador Manual
st.subheader("🔍 Explorador de Posiciones")

if len(df) > 1:
    col_r1, col_r2 = st.columns(2)
    
    with col_r1:
        start_rank = st.number_input(
            "Desde la posición:", 
            min_value=1, 
            max_value=len(df), 
            value=11
        )
    
    with col_r2:
        end_rank = st.number_input(
            "Hasta la posición:", 
            min_value=start_rank, 
            max_value=len(df), 
            value=min(30, len(df))
        )

    # Filtrado manual
    df_range = df.iloc[start_rank-1 : end_rank].sort_values("Peso Real", ascending=True)
    
    if not df_range.empty:
        fig_r = px.bar(
            df_range, 
            x="Peso Real", 
            y="Accion", 
            orientation='h', 
            text_auto='.2f', 
            color="Peso Real"
        )
        fig_r.update_layout(
            title=f"Posiciones del {start_rank} al {end_rank}", 
            showlegend=False, 
            xaxis_title="Peso (%)", 
            yaxis_title=""
        )
        st.plotly_chart(fig_r, use_container_width=True)
    else:
        st.info("Rango inválido.")
