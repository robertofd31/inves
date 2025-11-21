import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Mi Cartera",
    page_icon="📈",
    layout="wide"
)

# --- 2. SISTEMA DE CONTRASEÑA ---
def check_password():
    """Retorna True si la contraseña es correcta."""
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False

    if st.session_state.password_correct:
        return True

    st.markdown("### 🔒 Acceso Restringido")
    pwd_input = st.text_input("Contraseña:", type="password")
    
    if pwd_input:
        # Busca la clave en secrets.toml -> [passwords] access_code
        if pwd_input == st.secrets["passwords"]["access_code"]:
            st.session_state.password_correct = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta")
    return False

if not check_password():
    st.stop()

# --- 3. CARGA DE DATOS ---
st.title("📊 Dashboard Global de Inversiones")

@st.cache_data(ttl=600) # Recarga cada 10 min
def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    # Usamos el GID "0" (suele ser la primera hoja). Cambialo si usas otra pestaña.
    df = conn.read(worksheet="0") 
    return df

try:
    df_raw = load_data()
except Exception as e:
    st.error(f"Error de conexión: {e}")
    st.stop()

# --- 4. LIMPIEZA Y PREPARACIÓN (BLINDADA) ---

# A. Renombrado por posición (Evita KeyErrors por espacios)
# Asumimos el orden de tu Google Sheet:
nuevos_nombres = [
    "Fund ISIN", "Fondo", "Accion", "Ticker", "ISIN Security", 
    "Sector", "Pais", "Weight Fund", "Alloc", "Peso Real"
]

if len(df_raw.columns) >= 10:
    df_raw.columns.values[:10] = nuevos_nombres
else:
    st.error("El Excel tiene menos de 10 columnas. Revisa la hoja de origen.")
    st.stop()

# B. Limpieza numérica (Formato Europeo: 1.000,50 -> 1000.50)
try:
    df_raw['Peso Real'] = (
        df_raw['Peso Real']
        .astype(str)
        .str.replace('%', '', regex=False)
        .str.replace('€', '', regex=False)
        # Primero quitamos puntos de miles (si los hubiera)
        .str.replace('.', '', regex=False) 
        # Luego cambiamos la coma decimal por punto
        .str.replace(',', '.', regex=False)
    )
    df_raw['Peso Real'] = pd.to_numeric(df_raw['Peso Real'], errors='coerce').fillna(0)
except Exception as e:
    st.error(f"Error procesando números: {e}")

# C. Agrupación (Consolidar acciones repetidas en varios fondos)
df = df_raw.groupby("Accion")[["Peso Real", "Pais", "Sector"]].agg({
    "Peso Real": "sum",
    "Pais": "first",   # Tomamos el primer país encontrado
    "Sector": "first"  # Tomamos el primer sector encontrado
}).reset_index()

# Ordenar descendente
df = df.sort_values("Peso Real", ascending=False).reset_index(drop=True)

# --- 5. MÉTRICAS (KPIs) ---
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Posiciones", len(df))
c2.metric("Paises", df['Pais'].nunique())
c3.metric("Sectores", df['Sector'].nunique())
c4.metric("Exposición Total", f"{df['Peso Real'].sum():.2f}%")

st.markdown("---")

# --- 6. GRÁFICOS CIRCULARES (PIE) ---
def prepare_pie_data(dataframe, col_name, threshold=0.5):
    """Agrupa los pequeños en 'Otros'"""
    grouped = dataframe.groupby(col_name)['Peso Real'].sum().reset_index()
    main = grouped[grouped['Peso Real'] >= threshold]
    others = grouped[grouped['Peso Real'] < threshold]
    
    if not others.empty:
        others_row = pd.DataFrame({
            col_name: [f'Otros (<{threshold}%)'],
            'Peso Real': [others['Peso Real'].sum()]
        })
        return pd.concat([main, others_row])
    return main

col_left, col_right = st.columns(2)

with col_left:
    st.subheader("🌍 Distribución Geográfica")
    df_pais = prepare_pie_data(df, "Pais")
    fig_p = px.pie(df_pais, values="Peso Real", names="Pais", hole=0.4)
    fig_p.update_traces(textposition='inside', textinfo='percent+label')
    st.plotly_chart(fig_p, use_container_width=True)

with col_right:
    st.subheader("🏭 Distribución Sectorial")
    df_sec = prepare_pie_data(df, "Sector")
    fig_s = px.pie(df_sec, values="Peso Real", names="Sector", hole=0.4)
    fig_s.update_traces(textposition='inside', textinfo='percent+label')
    st.plotly_chart(fig_s, use_container_width=True)

# --- 7. GRÁFICOS DE BARRAS ---

# A) TOP 10 FIJO
st.subheader("🏆 Top 10 Posiciones")
df_top10 = df.head(10).sort_values("Peso Real", ascending=True) # Invertimos para que salga arriba la nº1

fig_10 = px.bar(
    df_top10, x="Peso Real", y="Accion", orientation='h',
    text_auto='.2f', color="Peso Real", color_continuous_scale="Blues"
)
fig_10.update_layout(showlegend=False, xaxis_title="Peso (%)", yaxis_title="")
st.plotly_chart(fig_10, use_container_width=True)

# B) RANGO DINÁMICO
st.subheader("🔍 Explorador de Posiciones")
rango = st.slider("Rango de visualización:", 1, len(df), (11, 25))

df_range = df.iloc[rango[0]-1 : rango[1]].sort_values("Peso Real", ascending=True)

if not df_range.empty:
    fig_r = px.bar(
        df_range, x="Peso Real", y="Accion", orientation='h',
        text_auto='.2f', color="Peso Real", color_continuous_scale="Teal"
    )
    fig_r.update_layout(title=f"Posiciones {rango[0]} - {rango[1]}", showlegend=False, xaxis_title="Peso (%)", yaxis_title="")
    st.plotly_chart(fig_r, use_container_width=True)
