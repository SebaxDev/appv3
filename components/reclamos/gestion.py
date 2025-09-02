# components/reclamos/gestion.py

import streamlit as st
import pandas as pd
from utils.date_utils import format_fecha
from utils.api_manager import api_manager, batch_update_sheet
from config.settings import SECTORES_DISPONIBLES, TECNICOS_DISPONIBLES, TIPOS_RECLAMO, DEBUG_MODE

def render_gestion_reclamos(df_reclamos, df_clientes, sheet_reclamos, user):
    """
    Renderiza la página de gestión de reclamos con la estructura solicitada por el usuario.
    """
    st.header("📊 Gestión de Reclamos")

    if df_reclamos.empty:
        st.info("Aún no hay reclamos cargados.")
        return

    # Preparar datos
    df_reclamos["Fecha y hora"] = pd.to_datetime(df_reclamos["Fecha y hora"], errors='coerce')
    df_reclamos.sort_values("Fecha y hora", ascending=False, inplace=True)

    # 1. Conteo de reclamos por tipo
    _render_conteo_por_tipo(df_reclamos)
    st.markdown("---")

    # 2. Lista de últimos reclamos con filtro
    _render_ultimos_reclamos(df_reclamos.head(20))
    st.markdown("---")

    # 3. Buscador de reclamo puntual por número de cliente
    _render_buscador_puntual(df_reclamos, sheet_reclamos)
    st.markdown("---")

    # 4. Lista de desconexiones a pedido
    _render_desconexiones(df_reclamos, sheet_reclamos)

def _render_conteo_por_tipo(df_reclamos):
    """Muestra el conteo total de reclamos activos (pendientes y en curso), por tipo."""
    st.subheader("📈 Conteo de Reclamos Activos por Tipo")

    df_activos = df_reclamos[df_reclamos["Estado"].isin(["Pendiente", "En curso"])]

    if df_activos.empty:
        st.info("No hay reclamos activos (pendientes o en curso).")
        return

    conteo = df_activos.groupby("Tipo de reclamo").size().reset_index(name="Total Activos")
    conteo.rename(columns={"Tipo de reclamo": "Tipo de Reclamo"}, inplace=True)

    st.dataframe(conteo, use_container_width=True, hide_index=True)

def _render_ultimos_reclamos(df_ultimos):
    """Muestra una lista filtrable de los últimos reclamos."""
    st.subheader("⏳ Últimos 20 Reclamos Cargados")

    busqueda = st.text_input("Buscar en últimos reclamos (por Nombre, Cliente, Dirección...)", key="busqueda_ultimos")

    df_filtrado = df_ultimos
    if busqueda:
        termino = busqueda.lower()
        # Búsqueda simple en varias columnas
        df_filtrado = df_ultimos[
            df_ultimos.apply(lambda row: termino in str(row).lower(), axis=1)
        ]

    if df_filtrado.empty:
        st.warning("No se encontraron reclamos con ese criterio de búsqueda.")
    else:
        # Mostrar resultados en un formato de lista más denso
        for _, row in df_filtrado.iterrows():
            with st.container():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{row['Nombre']}** (`{row['Nº Cliente']}`)")
                    st.caption(f"{row['Dirección']} - {row['Tipo de reclamo']}")
                with col2:
                    st.markdown(f"**{row['Estado']}**")
                    st.caption(f"{format_fecha(row['Fecha y hora'])}")
                st.divider()

def _render_buscador_puntual(df_reclamos, sheet_reclamos):
    """Permite buscar un reclamo por N° de cliente y editarlo."""
    st.subheader("🔍 Búsqueda y Edición por Nº de Cliente")

    n_cliente = st.text_input("Ingrese el número de cliente para buscar su reclamo:", key="n_cliente_busqueda")

    if n_cliente:
        reclamos_cliente = df_reclamos[df_reclamos["Nº Cliente"] == n_cliente]

        if reclamos_cliente.empty:
            st.warning("No se encontraron reclamos para ese número de cliente.")
        else:
            st.info(f"Se encontraron {len(reclamos_cliente)} reclamo(s) para el cliente {n_cliente}.")

            for _, reclamo in reclamos_cliente.iterrows():
                with st.expander(f"Reclamo ID: {reclamo['ID Reclamo']} - {reclamo['Tipo de reclamo']} ({reclamo['Estado']})"):
                    # Reutilizamos la lógica del formulario de edición
                    _render_edit_form(reclamo, df_reclamos, sheet_reclamos)

def _render_edit_form(reclamo, df_reclamos, sheet_reclamos):
    """Renderiza el formulario de edición para un reclamo."""
    with st.form(key=f"form_edit_{reclamo['ID Reclamo']}"):
        st.markdown(f"**Editando Reclamo de:** {reclamo['Nombre']}")

        c1, c2 = st.columns(2)
        with c1:
            estado = st.selectbox("Estado", ["Pendiente", "En curso", "Resuelto", "Desconexión"], index=["Pendiente", "En curso", "Resuelto", "Desconexión"].index(reclamo['Estado']))
            tecnico = st.selectbox("Técnico Asignado", options=[""] + TECNICOS_DISPONIBLES, index=TECNICOS_DISPONIBLES.index(reclamo["Técnico"]) + 1 if reclamo.get("Técnico") in TECNICOS_DISPONIBLES else 0)
        with c2:
            tipo_reclamo = st.selectbox("Tipo de Reclamo", options=TIPOS_RECLAMO, index=TIPOS_RECLAMO.index(reclamo['Tipo de reclamo']) if reclamo['Tipo de reclamo'] in TIPOS_RECLAMO else 0)
            sector = st.selectbox("Sector", options=SECTORES_DISPONIBLES, index=SECTORES_DISPONIBLES.index(reclamo['Sector']) if reclamo['Sector'] in SECTORES_DISPONIBLES else 0)

        detalles = st.text_area("Detalles", value=reclamo['Detalles'])

        submitted = st.form_submit_button("💾 Guardar Cambios")
        if submitted:
            updates = {
                "Estado": estado,
                "Técnico": tecnico,
                "Tipo de reclamo": tipo_reclamo,
                "Sector": sector,
                "Detalles": detalles
            }
            if _actualizar_fila_reclamo(reclamo['ID Reclamo'], df_reclamos, sheet_reclamos, updates):
                st.success(f"Reclamo {reclamo['ID Reclamo']} actualizado con éxito.")
                st.rerun()
            else:
                st.error("No se pudo actualizar el reclamo.")

def _render_desconexiones(df_reclamos, sheet_reclamos):
    """Muestra la lista de desconexiones a pedido para marcarlas como resueltas."""
    st.subheader("🔌 Desconexiones a Pedido")

    df_desconexiones = df_reclamos[
        (df_reclamos["Tipo de reclamo"] == "Desconexión a Pedido") &
        (df_reclamos["Estado"] != "Resuelto")
    ]

    if df_desconexiones.empty:
        st.info("No hay desconexiones pendientes.")
        return

    for _, row in df_desconexiones.iterrows():
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            st.markdown(f"**{row['Nombre']}** (`{row['Nº Cliente']}`)")
        with col2:
            st.caption(f"ID: {row['ID Reclamo']}")
        with col3:
            if st.button("Marcar como Resuelto", key=f"resolver_{row['ID Reclamo']}", use_container_width=True):
                if _actualizar_fila_reclamo(row['ID Reclamo'], df_reclamos, sheet_reclamos, {"Estado": "Resuelto"}):
                    st.success(f"Desconexión {row['ID Reclamo']} marcada como resuelta.")
                    st.rerun()
                else:
                    st.error("No se pudo actualizar la desconexión.")
        st.divider()

def _actualizar_fila_reclamo(reclamo_id, df_reclamos, sheet_reclamos, updates):
    """Función genérica para actualizar una fila de reclamo en Google Sheets."""
    try:
        # Encontrar el índice de la fila en el DataFrame original
        fila_idx = df_reclamos[df_reclamos["ID Reclamo"] == reclamo_id].index[0]
        fila_google_sheets = fila_idx + 2  # +1 por header, +1 por índice base 1

        # Mapeo de nombres de campo a letras de columna
        column_map = {
            "Estado": "I",
            "Técnico": "J",
            "Tipo de reclamo": "G",
            "Sector": "C",
            "Detalles": "H"
        }

        update_payload = []
        for key, value in updates.items():
            if key in column_map:
                col_letter = column_map[key]
                update_payload.append({
                    "range": f"{col_letter}{fila_google_sheets}",
                    "values": [[str(value)]]
                })

        if not update_payload:
            return False

        success, error = api_manager.safe_sheet_operation(
            batch_update_sheet, sheet_reclamos, update_payload, is_batch=True
        )
        return success
    except Exception as e:
        if DEBUG_MODE:
            st.error(f"Error al actualizar la fila: {e}")
        return False
