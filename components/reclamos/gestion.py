# components/reclamos/gestion.py

import streamlit as st
import pandas as pd
from utils.date_utils import format_fecha
from utils.api_manager import api_manager, batch_update_sheet
from config.settings import SECTORES_DISPONIBLES, TECNICOS_DISPONIBLES, TIPOS_RECLAMO, DEBUG_MODE

def render_gestion_reclamos(df_reclamos, df_clientes, sheet_reclamos, user):
    """
    Renderiza la página de gestión de reclamos con la estructura solicitada.
    """
    st.header("📊 Gestión de Reclamos")

    if df_reclamos.empty:
        st.info("Aún no hay reclamos cargados.")
        return

    # Preparar datos
    df_reclamos["Fecha y hora"] = pd.to_datetime(df_reclamos["Fecha y hora"], errors='coerce')
    df_reclamos["Fecha_formateada"] = df_reclamos["Fecha y hora"].apply(lambda f: format_fecha(f) if pd.notna(f) else "Sin fecha")
    df_merged = pd.merge(df_reclamos, df_clientes[["Nº Cliente", "Teléfono"]], on="Nº Cliente", how="left")
    df_merged.sort_values("Fecha y hora", ascending=False, inplace=True)

    # 1. Mini-Dashboard de conteo de reclamos por tipo
    _render_conteo_dashboard(df_merged)
    st.markdown("---")

    # 2. Filtros y tabla de los últimos 20 reclamos
    _mostrar_filtros_y_tabla(df_merged)
    st.markdown("---")

    # 3. Buscador de reclamo puntual por número de cliente
    _render_buscador_puntual(df_merged, sheet_reclamos)
    st.markdown("---")

    # 4. Lista de desconexiones a pedido (lógica corregida)
    _render_desconexiones(df_merged, sheet_reclamos)

def _render_conteo_dashboard(df_reclamos):
    """Muestra el conteo total de reclamos activos como un mini-dashboard."""
    st.subheader("📈 Conteo de Reclamos Activos por Tipo")

    df_activos = df_reclamos[df_reclamos["Estado"].isin(["Pendiente", "En curso"])]

    if df_activos.empty:
        st.info("No hay reclamos activos (pendientes o en curso).")
        return

    conteo = df_activos.groupby("Tipo de reclamo").size()

    num_tipos = len(conteo)
    if num_tipos == 0: return

    cols = st.columns(num_tipos if num_tipos <= 5 else 5) # Max 5 columnas para legibilidad
    i = 0
    for tipo, total in conteo.items():
        with cols[i % 5]:
            st.metric(label=tipo, value=total)
        i += 1

def _mostrar_filtros_y_tabla(df):
    """Muestra filtros y una tabla con los 20 resultados más recientes."""
    st.subheader("⏳ Últimos Reclamos (hasta 20 resultados)")

    col1, col2, col3 = st.columns(3)
    with col1:
        estado = st.selectbox("Filtrar por Estado", ["Todos"] + sorted(df["Estado"].dropna().unique()))
    with col2:
        sector = st.selectbox("Filtrar por Sector", ["Todos"] + sorted(df["Sector"].dropna().unique()))
    with col3:
        tipo = st.selectbox("Filtrar por Tipo", ["Todos"] + sorted(df["Tipo de reclamo"].dropna().unique()))

    df_filtrado = df.copy()
    if estado != "Todos": df_filtrado = df_filtrado[df_filtrado["Estado"] == estado]
    if sector != "Todos": df_filtrado = df_filtrado[df_filtrado["Sector"] == str(sector)]
    if tipo != "Todos": df_filtrado = df_filtrado[df_filtrado["Tipo de reclamo"] == tipo]

    # Tomar los 20 más recientes DESPUÉS de filtrar
    df_display = df_filtrado.head(20)

    st.markdown(f"**Mostrando {len(df_display)} de {len(df_filtrado)} reclamos encontrados**")

    columnas_a_mostrar = ["Fecha_formateada", "Nº Cliente", "Nombre", "Sector", "Tipo de reclamo", "Teléfono", "Estado"]
    st.dataframe(
        df_display[columnas_a_mostrar].rename(columns={"Fecha_formateada": "Fecha y hora"}),
        use_container_width=True,
        hide_index=True,
        height=400
    )

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
                    _render_edit_form(reclamo, df_reclamos, sheet_reclamos)

def _render_edit_form(reclamo, df_reclamos, sheet_reclamos):
    """Renderiza el formulario de edición para un reclamo."""
    with st.form(key=f"form_edit_{reclamo['ID Reclamo']}"):
        st.markdown(f"**Editando Reclamo de:** {reclamo['Nombre']}")
        c1, c2 = st.columns(2)
        with c1:
            estado_options = ["Pendiente", "En curso", "Resuelto", "Desconexión"]
            estado_idx = estado_options.index(reclamo['Estado']) if reclamo['Estado'] in estado_options else 0
            estado = st.selectbox("Estado", estado_options, index=estado_idx)

            tecnico_options = [""] + TECNICOS_DISPONIBLES
            tecnico_idx = tecnico_options.index(reclamo["Técnico"]) if reclamo.get("Técnico") in tecnico_options else 0
            tecnico = st.selectbox("Técnico Asignado", options=tecnico_options, index=tecnico_idx)
        with c2:
            tipo_idx = TIPOS_RECLAMO.index(reclamo['Tipo de reclamo']) if reclamo['Tipo de reclamo'] in TIPOS_RECLAMO else 0
            tipo_reclamo = st.selectbox("Tipo de Reclamo", options=TIPOS_RECLAMO, index=tipo_idx)

            sector_idx = SECTORES_DISPONIBLES.index(reclamo['Sector']) if reclamo['Sector'] in SECTORES_DISPONIBLES else 0
            sector = st.selectbox("Sector", options=SECTORES_DISPONIBLES, index=sector_idx)

        detalles = st.text_area("Detalles", value=reclamo['Detalles'])

        if st.form_submit_button("💾 Guardar Cambios"):
            updates = {"Estado": estado, "Técnico": tecnico, "Tipo de reclamo": tipo_reclamo, "Sector": sector, "Detalles": detalles}
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
        (df_reclamos["Estado"] == "Desconexión")
    ]
    if df_desconexiones.empty:
        st.info("No hay desconexiones pendientes de resolver.")
        return

    for _, row in df_desconexiones.iterrows():
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1: st.markdown(f"**{row['Nombre']}** (`{row['Nº Cliente']}`)")
        with col2: st.caption(f"ID: {row['ID Reclamo']}")
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
        fila_idx = df_reclamos.index[df_reclamos["ID Reclamo"] == reclamo_id].tolist()[0]
        fila_google_sheets = fila_idx + 2

        column_map = {"Estado": "I", "Técnico": "J", "Tipo de reclamo": "G", "Sector": "C", "Detalles": "H"}
        update_payload = [{"range": f"{column_map[key]}{fila_google_sheets}", "values": [[str(value)]]} for key, value in updates.items() if key in column_map]

        if not update_payload: return False

        success, _ = api_manager.safe_sheet_operation(batch_update_sheet, sheet_reclamos, update_payload, is_batch=True)
        return success
    except Exception as e:
        if DEBUG_MODE: st.error(f"Error al actualizar la fila: {e}")
        return False
