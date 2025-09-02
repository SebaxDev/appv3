# components/resumen_jornada.py

import streamlit as st
import pandas as pd
import pytz
from datetime import datetime, timedelta
from utils.date_utils import format_fecha, ahora_argentina
from config.settings import NOTIFICATION_TYPES, DEBUG_MODE

def render_resumen_jornada(df_reclamos):
    """Muestra un resumen de los reclamos del día por estado."""

    if df_reclamos.empty:
        st.info("No hay datos de reclamos para mostrar.")
        return

    try:
        # --- Preparación de Datos ---
        df_copy = df_reclamos.copy()
        df_copy["Fecha y hora"] = pd.to_datetime(df_copy["Fecha y hora"], errors='coerce')

        argentina_tz = pytz.timezone("America/Argentina/Buenos_Aires")

        # Filtrar reclamos de hoy de forma robusta
        df_copy.dropna(subset=["Fecha y hora"], inplace=True)

        now_arg = datetime.now(argentina_tz)
        start_of_day = now_arg.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        # Localiza la columna de fecha a la zona horaria correcta antes de comparar
        localized_dates = df_copy["Fecha y hora"].dt.tz_localize(argentina_tz, ambiguous='infer')

        df_hoy = df_copy[(localized_dates >= start_of_day) & (localized_dates < end_of_day)].copy()

        # --- Cálculos de Métricas ---
        total_hoy = len(df_hoy)
        pendientes_total = len(df_copy[df_copy["Estado"] == "Pendiente"])
        en_curso_total = len(df_copy[df_copy["Estado"] == "En curso"])
        desconexion_total = len(df_copy[df_copy["Estado"] == "Desconexión"])

        # --- Visualización de Métricas ---
        st.markdown("##### Resumen de Estado")
        cols = st.columns(4)
        cols[0].metric("📝 Reclamos de Hoy", total_hoy)
        cols[1].metric("⏳ Pendientes (Total)", pendientes_total)
        cols[2].metric("🔧 En Curso (Total)", en_curso_total)
        cols[3].metric("🔌 Desconexión (Total)", desconexion_total)

        st.markdown("---")

        # --- Resumen General de Reclamos en Curso (sin filtro de fecha) ---
        st.markdown("##### 👷 Reclamos en curso (General)")
        df_en_curso = df_copy[df_copy["Estado"] == "En curso"].copy()

        if not df_en_curso.empty:
            if "Técnico" in df_en_curso.columns:
                df_en_curso["Técnico"] = df_en_curso["Técnico"].fillna("Sin asignar").astype(str)
                df_en_curso_asignados = df_en_curso[df_en_curso["Técnico"].str.strip() != "Sin asignar"]

                if not df_en_curso_asignados.empty:
                    # Agrupar por técnicos
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

            # Reclamos más antiguos en curso
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

        # Notificaciones (función existente)
        _notificar_reclamos_no_asignados(df_copy)

    except Exception as e:
        st.error(f"Error al generar resumen: {str(e)}")
        if DEBUG_MODE:
            st.exception(e)

def _notificar_reclamos_no_asignados(df):
    """
    Detecta reclamos sin técnico hace más de 36 horas y notifica globalmente (una vez).
    """
    if 'notification_manager' not in st.session_state or st.session_state.notification_manager is None:
        return

    ahora = ahora_argentina()
    umbral = ahora - timedelta(hours=36)

    df_filtrado = df[
        (df["Estado"].isin(["Pendiente", "En curso"])) &
        (df["Técnico"].isna() | (df["Técnico"].str.strip() == "")) &
        (pd.to_datetime(df["Fecha y hora"], errors='coerce') < umbral)
    ].copy()

    if df_filtrado.empty:
        return

    try:
        # Evitar notificaciones duplicadas en la misma sesión
        if st.session_state.get("unassigned_claim_notified", False):
            return

        mensaje = f"Hay {len(df_filtrado)} reclamos sin técnico asignado desde hace más de 36 horas."
        st.session_state.notification_manager.add(
            notification_type="unassigned_claim",
            message=mensaje,
            user_target="all" # Notificación global para administradores
        )
        st.session_state.unassigned_claim_notified = True

    except Exception as e:
        if DEBUG_MODE:
            st.warning("⚠️ No se pudo generar la notificación global de reclamos no asignados.")
            st.exception(e)
