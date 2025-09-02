# components/reclamos/cierre.py

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import pytz

from utils.date_utils import format_fecha, ahora_argentina
from utils.api_manager import api_manager
from utils.data_manager import batch_update_sheet
from config.settings import COLUMNAS_RECLAMOS

# --- Funciones de Lógica de Negocio (Handlers) ---

def _handle_resolver_reclamo(reclamo, sheet_reclamos, sheet_clientes, df_clientes):
    """Marca un reclamo como 'Resuelto' y actualiza la hoja de cálculo."""
    try:
        with st.spinner("Resolviendo reclamo..."):
            id_reclamo = reclamo['ID Reclamo']
            nuevo_precinto = st.session_state.get(f"precinto_{id_reclamo}", "").strip()

            fila_index = reclamo.name + 2

            col_estado = COLUMNAS_RECLAMOS.index("Estado")
            col_fecha_cierre = COLUMNAS_RECLAMOS.index("Fecha_formateada")

            fecha_resolucion = ahora_argentina().strftime('%d/%m/%Y %H:%M')

            updates = [
                {"range": f"R{fila_index}C{col_estado + 1}", "values": [["Resuelto"]]},
                {"range": f"R{fila_index}C{col_fecha_cierre + 1}", "values": [[fecha_resolucion]]},
            ]

            if nuevo_precinto and nuevo_precinto != reclamo.get("N° de Precinto", ""):
                col_precinto_reclamo = COLUMNAS_RECLAMOS.index("N° de Precinto")
                updates.append({"range": f"R{fila_index}C{col_precinto_reclamo + 1}", "values": [[nuevo_precinto]]})

            success, error = api_manager.safe_sheet_operation(
                batch_update_sheet, sheet_reclamos, updates, is_batch=True
            )

            if success:
                if nuevo_precinto:
                    cliente_info = df_clientes[df_clientes["Nº Cliente"] == reclamo["Nº Cliente"]]
                    if not cliente_info.empty:
                        idx_cliente = cliente_info.index[0] + 2
                        col_precinto_cliente = cliente_info.columns.get_loc("N° de Precinto") + 1
                        api_manager.safe_sheet_operation(
                            sheet_clientes.update_cell, idx_cliente, col_precinto_cliente, nuevo_precinto
                        )
                st.toast(f"✅ Reclamo #{reclamo['Nº Cliente']} marcado como Resuelto.", icon="🎉")
                st.rerun()
            else:
                st.error(f"Error al resolver el reclamo: {error}")
    except Exception as e:
        st.error(f"Error inesperado al resolver reclamo: {e}")

def _handle_volver_a_pendiente(reclamo, sheet_reclamos):
    """Devuelve un reclamo al estado 'Pendiente'."""
    try:
        with st.spinner("Devolviendo a pendiente..."):
            fila_index = reclamo.name + 2
            col_estado = COLUMNAS_RECLAMOS.index("Estado")
            col_tecnico = COLUMNAS_RECLAMOS.index("Técnico")
            col_fecha_cierre = COLUMNAS_RECLAMOS.index("Fecha_formateada")
            updates = [
                {"range": f"R{fila_index}C{col_estado + 1}", "values": [["Pendiente"]]},
                {"range": f"R{fila_index}C{col_tecnico + 1}", "values": [[""]]},
                {"range": f"R{fila_index}C{col_fecha_cierre + 1}", "values": [[""]]},
            ]
            success, error = api_manager.safe_sheet_operation(
                batch_update_sheet, sheet_reclamos, updates, is_batch=True
            )
            if success:
                st.toast(f"↩️ Reclamo #{reclamo['Nº Cliente']} devuelto a Pendiente.", icon="🔄")
                st.rerun()
            else:
                st.error(f"Error al devolver a pendiente: {error}")
    except Exception as e:
        st.error(f"Error inesperado al devolver reclamo: {e}")

def _handle_eliminar_reclamos(reclamos_a_eliminar, sheet_reclamos):
    """Ejecuta una solicitud batch para eliminar filas de la hoja de cálculo."""
    if reclamos_a_eliminar.empty:
        st.warning("No hay reclamos para eliminar.")
        return
    try:
        with st.spinner(f"Eliminando {len(reclamos_a_eliminar)} reclamos antiguos..."):
            reclamos_a_eliminar = reclamos_a_eliminar.sort_index(ascending=False)
            requests = []
            sheet_id = sheet_reclamos.id
            for index in reclamos_a_eliminar.index:
                row_index_api = index + 1
                requests.append({
                    "deleteDimension": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "ROWS",
                            "startIndex": row_index_api,
                            "endIndex": row_index_api + 1
                        }
                    }
                })
            if requests:
                sheet_reclamos.spreadsheet.batch_update({"requests": requests})
                st.success(f"🎉 ¡Éxito! Se eliminaron {len(reclamos_a_eliminar)} reclamos antiguos.")
                st.rerun()
    except Exception as e:
        st.error(f"Ocurrió un error grave durante la eliminación: {e}")

def _render_limpieza_reclamos(df_reclamos, sheet_reclamos):
    """Renderiza la sección para la limpieza de reclamos antiguos."""
    st.markdown("---")
    st.markdown("### 🗑️ Limpieza de Reclamos Antiguos")
    try:
        df_resueltos = df_reclamos[df_reclamos["Estado"].str.strip().str.lower() == "resuelto"].copy()
        if df_resueltos.empty:
            st.info("No hay reclamos resueltos para analizar.")
            return

        df_resueltos["FechaCierreDT"] = pd.to_datetime(
            df_resueltos["Fecha_formateada"], format='%d/%m/%Y %H:%M', errors='coerce'
        )
        df_resueltos.dropna(subset=["FechaCierreDT"], inplace=True)

        tz_argentina = pytz.timezone("America/Argentina/Buenos_Aires")
        df_resueltos["FechaCierreDT"] = df_resueltos["FechaCierreDT"].apply(
            lambda x: tz_argentina.localize(x) if x.tzinfo is None else x.astimezone(tz_argentina)
        )

        ahora = ahora_argentina()
        df_resueltos["DiasDesdeCierre"] = (ahora - df_resueltos["FechaCierreDT"]).dt.days
        reclamos_a_eliminar = df_resueltos[df_resueltos["DiasDesdeCierre"] > 30].copy()

        st.metric(label="Reclamos resueltos con más de 30 días", value=len(reclamos_a_eliminar))
        if not reclamos_a_eliminar.empty:
            with st.expander("Ver detalles de los reclamos a eliminar"):
                st.dataframe(
                    reclamos_a_eliminar[["Nº Cliente", "Nombre", "Tipo de reclamo", "Fecha_formateada", "DiasDesdeCierre"]],
                    use_container_width=True
                )
            st.warning("🚨 Esta acción es irreversible. Los datos se eliminarán permanentemente.")
            if st.checkbox("Sí, entiendo y deseo continuar.", key="confirm_delete_checkbox"):
                st.button(
                    f"🗑️ Eliminar {len(reclamos_a_eliminar)} Reclamos Ahora",
                    on_click=_handle_eliminar_reclamos,
                    args=(reclamos_a_eliminar, sheet_reclamos),
                    type="primary",
                    use_container_width=True
                )
    except Exception as e:
        st.error(f"Error al procesar la limpieza de reclamos: {e}")

# --- Componente Principal de Renderizado ---

def render_cierre_reclamos(df_reclamos, df_clientes, sheet_reclamos, sheet_clientes, user):
    """Renderiza la interfaz para el cierre y gestión de reclamos 'En curso'."""
    st.subheader("✅ Gestión y Cierre de Reclamos")
    st.markdown("---")
    try:
        df_en_curso = df_reclamos[df_reclamos["Estado"].str.strip().str.lower() == "en curso"].copy()
        df_en_curso["Fecha y hora"] = pd.to_datetime(df_en_curso["Fecha y hora"], dayfirst=True, errors='coerce')
    except Exception as e:
        st.error(f"Error al procesar los datos de reclamos: {e}")
        return

    if df_en_curso.empty and 'cierre_filtro_tecnico' in st.session_state and st.session_state.cierre_filtro_tecnico == "Todos":
        st.info("👍 ¡Excelente! No hay reclamos 'En curso' en este momento.")

    # --- Filtros ---
    st.markdown("#### 🔍 Filtrar Reclamos")
    tecnicos_activos = sorted(list(set(
        t.strip().upper() for tecnicos_list in df_en_curso["Técnico"].dropna()
        for t in tecnicos_list.split(',') if t.strip()
    )))
    opciones_filtro = ["Todos"] + tecnicos_activos
    if 'cierre_filtro_tecnico' not in st.session_state:
        st.session_state.cierre_filtro_tecnico = "Todos"
    if st.session_state.cierre_filtro_tecnico not in opciones_filtro:
        st.toast("Filtro reiniciado: el técnico ya no tiene reclamos.", icon="ℹ️")
        st.session_state.cierre_filtro_tecnico = "Todos"
        st.rerun()
    filtro_tecnico_idx = opciones_filtro.index(st.session_state.cierre_filtro_tecnico)
    def on_filter_change():
        st.session_state.cierre_filtro_tecnico = st.session_state.cierre_filtro_selectbox
    st.selectbox(
        "Filtrar por técnico:", options=opciones_filtro, index=filtro_tecnico_idx,
        key='cierre_filtro_selectbox', on_change=on_filter_change,
        help="Selecciona un técnico para ver solo sus reclamos."
    )
    filtro_tecnico = st.session_state.cierre_filtro_tecnico
    if filtro_tecnico != "Todos":
        df_filtrado = df_en_curso[df_en_curso["Técnico"].str.contains(filtro_tecnico, case=False, na=False)].copy()
    else:
        df_filtrado = df_en_curso.copy()

    if not df_en_curso.empty:
        st.markdown(f"**Mostrando {len(df_filtrado)} de {len(df_en_curso)} reclamos en curso.**")
        st.markdown("---")

    if df_filtrado.empty and filtro_tecnico != "Todos":
        st.info(f"El técnico {filtro_tecnico} no tiene reclamos 'En curso'.")
    else:
        df_filtrado = df_filtrado.sort_values(by="Fecha y hora", ascending=True)
        for index, reclamo in df_filtrado.iterrows():
            id_reclamo = reclamo['ID Reclamo']
            with st.expander(f"**#{reclamo['Nº Cliente']} - {reclamo['Nombre']}** | {reclamo['Tipo de reclamo']} | Creado: {format_fecha(reclamo['Fecha y hora'])}"):
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    st.markdown(f"**Dirección:** {reclamo.get('Dirección', 'N/A')}")
                    st.markdown(f"**Técnico(s):** `{reclamo.get('Técnico', 'No asignado')}`")
                    st.markdown(f"**Detalles:**"); st.info(f"{reclamo.get('Detalles', 'Sin detalles.')}")
                st.text_input("N° de Precinto (si aplica)", value=reclamo.get("N° de Precinto", ""), key=f"precinto_{id_reclamo}")
                with col2:
                    st.button("✅ Marcar como Resuelto", key=f"resolver_{id_reclamo}", on_click=_handle_resolver_reclamo,
                              args=(reclamo, sheet_reclamos, sheet_clientes, df_clientes), use_container_width=True, type="primary")
                with col3:
                    st.button("↩️ Devolver a Pendiente", key=f"pendiente_{id_reclamo}", on_click=_handle_volver_a_pendiente,
                              args=(reclamo, sheet_reclamos), use_container_width=True)

    # --- Limpieza de Reclamos Antiguos ---
    _render_limpieza_reclamos(df_reclamos, sheet_reclamos)
