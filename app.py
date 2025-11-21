import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px

# 1. CONFIGURACIÓN DE LA PÁGINA
st.set_page_config(
    page_title="Mi Cartera de Inversión",
    page_icon="📈",
    layout="wide"
)

st.title("📈 Dashboard de Inversiones")

# 2. CONEXIÓN Y CARGA DE DATOS
# Usamos caché para no recargar los datos cada vez que tocas un botón
@st.cache_data(ttl=600) # Actualiza cada 10 min
def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    # Leemos la hoja de datos crudos para poder filtrar dinámicamente
    df = conn.read(worksheet="598707666") 
    return df

try:
    df = load_data()
except Exception as e:
    st.error(f"Error conectando a Google Sheets: {e}")
    st.stop()

# 3. LIMPIEZA DE DATOS (Aseguramos tipos)
# Convertimos el porcentaje si viene como string o numérico
if df['Real Weight in Portfolio (%)'].dtype == 'O':
    df['Peso Real'] = df['Real Weight in Portfolio (%)'].astype(str).str.replace('%','').str.replace(',','.').astype(float)
else:
    df['Peso Real'] = df['Real Weight in Portfolio (%)']

# Renombrar columnas para facilitar uso
df = df.rename(columns={
    "Security Name": "Accion",
    "Country": "Pais",
    "Fund Name": "Fondo Origen"
})

# 4. BARRA LATERAL (FILTROS)
st.sidebar.header("Filtros")
fondos_selected = st.sidebar.multiselect(
    "Filtrar por Fondo:",
    options=df["Fondo Origen"].unique(),
    default=df["Fondo Origen"].unique()
)

# Aplicar filtro
df_filtered = df[df["Fondo Origen"].isin(fondos_selected)]

# 5. METRICAS PRINCIPALES (KPIs)
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Posiciones", len(df_filtered))
with col2:
    top_holding = df_filtered.loc[df_filtered['Peso Real'].idxmax()]
    st.metric("Mayor Posición", f"{top_holding['Accion']}", f"{top_holding['Peso Real']:.2f}%")
with col3:
    # Suma total (debería ser cerca de 100% si están todos los fondos)
    total_exposure = df_filtered['Peso Real'].sum()
    st.metric("Exposición Total Analizada", f"{total_exposure:.1f}%")

st.markdown("---")

# 6. GRÁFICOS PRINCIPALES
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("🌍 Distribución por País")
    # Agrupamos dinámicamente
    df_pais = df_filtered.groupby("Pais")["Peso Real"].sum().reset_index()
    fig_pais = px.pie(df_pais, values="Peso Real", names="Pais", hole=0.4)
    st.plotly_chart(fig_pais, use_container_width=True)

with col_right:
    st.subheader("🏭 Distribución por Sector")
    df_sector = df_filtered.groupby("Sector")["Peso Real"].sum().reset_index()
    fig_sector = px.pie(df_sector, values="Peso Real", names="Sector", hole=0.4)
    st.plotly_chart(fig_sector, use_container_width=True)

# 7. TOP POSICIONES (TABLA)
st.subheader("🏆 Top 20 Posiciones Reales (Consolidado)")

# Agrupamos por Acción (por si tienes Microsoft en 2 fondos distintos, que sume el peso)
df_top = df_filtered.groupby("Accion")[["Peso Real", "Pais", "Sector"]].agg({
    "Peso Real": "sum",
    "Pais": "first",   # Cogemos el primer país que salga
    "Sector": "first"
}).reset_index()

df_top = df_top.sort_values("Peso Real", ascending=False).head(20)

# Formato bonito para la tabla
st.dataframe(
    df_top,
    column_config={
        "Peso Real": st.column_config.ProgressColumn(
            "Peso en Cartera",
            format="%.2f%%",
            min_value=0,
            max_value=df_top["Peso Real"].max(),
        ),
    },
    hide_index=True,
    use_container_width=True
)

# 8. EXPORTE
st.download_button(
    label="Descargar datos actuales como CSV",
    data=df_filtered.to_csv(index=False).encode('utf-8'),
    file_name='mi_cartera_filtrada.csv',
    mime='text/csv',
)
