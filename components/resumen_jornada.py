# components/resumen_jornada.py

import streamlit as st
import pandas as pd
import pytz
from datetime import datetime, timedelta
from utils.date_utils import format_fecha, ahora_argentina
from config.settings import NOTIFICATION_TYPES, DEBUG_MODE

def render_resumen_jornada(df_reclamos):
    """
    Muestra un resumen del estado general de los reclamos.
    """

    if df_reclamos.empty:
        st.info("No hay datos de reclamos para mostrar.")
        return

    try:
        # --- Preparación de Datos ---
        df_copy = df_reclamos.copy()
        df_copy["Fecha y hora"] = pd.to_datetime(df_copy["Fecha y hora"], errors='coerce')

        # --- Cálculos de Métricas ---
        pendientes_total = len(df_copy[df_copy["Estado"] == "Pendiente"])
        en_curso_total = len(df_copy[df_copy["Estado"] == "En curso"])
        desconexion_total = len(df_copy[df_copy["Estado"] == "Desconexión"])

        # --- Visualización de Métricas ---
        st.markdown("##### Resumen de Estado General")
        cols = st.columns(3)
        cols[0].metric("⏳ Pendientes (Total)", pendientes_total)
        cols[1].metric("🔧 En Curso (Total)", en_curso_total)
        cols[2].metric("🔌 Desconexión (Total)", desconexion_total)

        st.markdown("---")

        # --- Resumen General de Reclamos en Curso (sin filtro de fecha) ---
        st.markdown("##### 👷 Reclamos en curso (General)")
        df_en_curso = df_copy[df_copy["Estado"] == "En curso"].copy()

        if not df_en_curso.empty:
            if "Técnico" in df_en_curso.columns:
                df_en_curso["Técnico"] = df_en_curso["Técnico"].fillna("Sin asignar").astype(str)
                df_en_curso_asignados = df_en_curso[df_en_curso["Técnico"].str.strip() != "Sin asignar"]

                if not df_en_curso_asignados.empty:
                    df_en_curso_asignados["tecnicos_set"] = df_en_curso_asignados["Técnico"].apply(
                        lambda x: tuple(sorted([t.strip().upper() for t in x.split(",") if t.strip()]))
                    )
                    conteo_grupos = df_en_curso_asignados.groupby("tecnicos_set").size().reset_index(name="Cantidad")

                    st.markdown("###### Distribución de trabajo:")
                    for fila in conteo_grupos.itertuples():
                        tecnicos = ", ".join(fila.tecnicos_set)
                        st.markdown(f"- 👥 **{tecnicos}**: {fila.Cantidad} reclamos")
                else:
                    st.info("No hay técnicos asignados a los reclamos en curso.")

            reclamos_antiguos = df_en_curso.sort_values("Fecha y hora").head(3)
            if not reclamos_antiguos.empty:
                st.markdown("###### ⏳ Reclamos más antiguos aún en curso:")
                for _, row in reclamos_antiguos.iterrows():
                    fecha_formateada = format_fecha(row["Fecha y hora"])
                    st.markdown(
                        f"- **{row['Nombre']}** ({row['Nº Cliente']}) - Desde: {fecha_formateada} - Técnicos: {row['Técnico']}"
                    )
        else:
            st.info("No hay reclamos en curso en este momento.")

    except Exception as e:
        st.error(f"Error al generar resumen: {str(e)}")
        if DEBUG_MODE:
            st.exception(e)
