# components/resumen_jornada.py

import streamlit as st
import pandas as pd
from utils.date_utils import ahora_argentina

def render_resumen_jornada(df_reclamos):
    """Muestra un resumen conciso con los reclamos del día, pendientes y en curso."""
    st.markdown("---")
    st.markdown("### 📊 Resumen General")

    if df_reclamos.empty:
        st.info("No hay datos de reclamos para mostrar.")
        return

    try:
        # Hacemos una copia para evitar modificar el dataframe original
        df = df_reclamos.copy()

        # Asegurar que la columna de fecha y hora esté en formato datetime
        # Usamos errors='coerce' para manejar posibles errores de formato
        df["Fecha y hora"] = pd.to_datetime(df["Fecha y hora"], dayfirst=True, errors='coerce')

        # 1. Reclamos cargados hoy
        # Nos aseguramos de comparar fechas sin tener en cuenta la zona horaria para evitar errores
        hoy = ahora_argentina().date()
        reclamos_hoy = df[df["Fecha y hora"].dt.date == hoy]

        # 2. Reclamos pendientes
        # Usamos .str.strip().str.lower() para una comparación robusta
        pendientes = df[df["Estado"].str.strip().str.lower() == "pendiente"]

        # 3. Reclamos en curso
        en_curso = df[df["Estado"].str.strip().str.lower() == "en curso"]

        # Mostrar las métricas en tres columnas
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(label="📝 Reclamos de Hoy", value=len(reclamos_hoy))
        with col2:
            st.metric(label="⏳ Pendientes", value=len(pendientes))
        with col3:
            st.metric(label="⚙️ En Curso", value=len(en_curso))

    except Exception as e:
        st.error(f"Ocurrió un error al generar el resumen: {e}")
        st.exception(e) # Para debugging si es necesario
