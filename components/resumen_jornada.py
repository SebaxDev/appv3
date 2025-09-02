# components/resumen_jornada.py

import streamlit as st
import pandas as pd
import pytz
from datetime import datetime, timedelta
from utils.date_utils import format_fecha, ahora_argentina
from config.settings import DEBUG_MODE

def render_resumen_jornada(df_reclamos):
    """
    Muestra un resumen del estado general de los reclamos, incluyendo los del día actual.
    """

    if df_reclamos.empty:
        st.info("No hay datos de reclamos para mostrar.")
        return

    try:
        # --- Preparación de Datos ---
        df_copy = df_reclamos.copy()
        df_copy["Fecha y hora"] = pd.to_datetime(df_copy["Fecha y hora"], errors='coerce')
        df_copy.dropna(subset=["Fecha y hora"], inplace=True)

        # --- Cálculos de Métricas ---
        argentina_tz = pytz.timezone("America/Argentina/Buenos_Aires")
        now_in_arg = ahora_argentina()
        start_of_today = now_in_arg.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_today = start_of_today + timedelta(days=1)

        # Lógica robusta para manejar zonas horarias
        try:
            dates_aware = df_copy["Fecha y hora"].dt.tz_localize(argentina_tz, ambiguous='infer')
        except TypeError:
            dates_aware = df_copy["Fecha y hora"].dt.tz_convert(argentina_tz)

        df_hoy = df_copy[(dates_aware >= start_of_today) & (dates_aware < end_of_today)]
        total_hoy = len(df_hoy)

        pendientes_total = len(df_copy[df_copy["Estado"] == "Pendiente"])
        en_curso_total = len(df_copy[df_copy["Estado"] == "En curso"])

        # --- Visualización de Métricas ---
        st.markdown("##### Resumen de Estado General")
        cols = st.columns(3)
        cols[0].metric("📝 Reclamos de Hoy", total_hoy)
        cols[1].metric("⏳ Pendientes (Total)", pendientes_total)
        cols[2].metric("🔧 En Curso (Total)", en_curso_total)

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
                        f"- **{row['Nombre']}** ({row['Nº Cliente']}) - Desde: {fecha_formateada} - Técnicos: {row.get('Técnico', 'N/A')}"
                    )
        else:
            st.info("No hay reclamos en curso en este momento.")

    except Exception as e:
        st.error(f"Error al generar resumen: {str(e)}")
        if DEBUG_MODE:
            st.exception(e)
