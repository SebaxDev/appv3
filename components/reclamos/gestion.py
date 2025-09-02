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

    # --- Preparación de Datos Robusta ---
    df_reclamos_copy = df_reclamos.copy()
    df_clientes_copy = df_clientes.copy()

    df_reclamos_copy["Nº Cliente"] = df_reclamos_copy["Nº Cliente"].astype(str).str.strip()
    df_clientes_copy["Nº Cliente"] = df_clientes_copy["Nº Cliente"].astype(str).str.strip()

    df_reclamos_copy["Fecha y hora"] = pd.to_datetime(df_reclamos_copy["Fecha y hora"], errors='coerce')
    df_reclamos_copy["Fecha_formateada"] = df_reclamos_copy["Fecha y hora"].apply(lambda f: format_fecha(f) if pd.notna(f) else "Sin fecha")

    # Merge para añadir todas las columnas de clientes necesarias.
    df_merged = pd.merge(df_reclamos_copy, df_clientes_copy, on="Nº Cliente", how="left", suffixes=("", "_cliente"))
    df_merged.sort_values("Fecha y hora", ascending=False, inplace=True)

    # 1. Mini-Dashboard de conteo de reclamos por tipo
    _render_conteo_dashboard(df_merged)
    st.markdown("---")

    # 2. Filtros y tabla de los últimos 100 reclamos
    _mostrar_filtros_y_tabla(df_merged)
    st.markdown("---")

    # 3. Buscador de reclamo puntual por número de cliente
    _render_buscador_puntual(df_merged, sheet_reclamos)
    st.markdown("---")

    # 4. Lista de desconexiones a pedido
    _gestionar_desconexiones(df_merged, sheet_reclamos)

def _render_conteo_dashboard(df_reclamos):
    st.subheader("📈 Conteo de Reclamos Activos por Tipo")
    df_activos = df_reclamos[df_reclamos["Estado"].isin(["Pendiente", "En curso"])]
    if df_activos.empty:
        st.info("No hay reclamos activos.")
        return
    conteo = df_activos.groupby("Tipo de reclamo").size()
    num_tipos = len(conteo)
    if num_tipos == 0: return
    cols = st.columns(num_tipos if num_tipos <= 5 else 5)
    i = 0
    for tipo, total in conteo.items():
        with cols[i % 5]:
            st.metric(label=tipo, value=total)
        i += 1

def _mostrar_filtros_y_tabla(df):
    st.subheader("⏳ Últimos Reclamos (hasta 100 resultados)")

    filters = {}
    col1, col2, col3 = st.columns(3)
    with col1:
        if "Estado" in df.columns:
            filters["Estado"] = st.selectbox("Filtrar por Estado", ["Todos"] + sorted(df["Estado"].dropna().unique()))
    with col2:
        if "Sector" in df.columns:
            filters["Sector"] = st.selectbox("Filtrar por Sector", ["Todos"] + sorted(df["Sector"].dropna().unique()))
    with col3:
        if "Tipo de reclamo" in df.columns:
            filters["Tipo de reclamo"] = st.selectbox("Filtrar por Tipo", ["Todos"] + sorted(df["Tipo de reclamo"].dropna().unique()))

    df_filtrado = df.copy()
    for key, value in filters.items():
        if value != "Todos":
            df_filtrado = df_filtrado[df_filtrado[key] == value]

    df_display = df_filtrado.head(100)
    st.markdown(f"**Mostrando {len(df_display)} de {len(df_filtrado)} reclamos encontrados**")

    columnas_deseadas = ["Fecha_formateada", "Nº Cliente", "Nombre", "Sector", "Tipo de reclamo", "Teléfono", "Estado"]
    columnas_existentes = [col for col in columnas_deseadas if col in df_display.columns]

    st.dataframe(
        df_display[columnas_existentes].rename(columns={"Fecha_formateada": "Fecha y hora"}),
        use_container_width=True, hide_index=True, height=400
    )

def _render_buscador_puntual(df_reclamos, sheet_reclamos):
    st.subheader("🔍 Búsqueda y Edición por Nº de Cliente")
    n_cliente = st.text_input("Ingrese el número de cliente para buscar su reclamo:", key="n_cliente_busqueda")
    if n_cliente:
        reclamos_cliente = df_reclamos[df_reclamos["Nº Cliente"] == n_cliente]
        if reclamos_cliente.empty:
            st.warning("No se encontraron reclamos para ese número de cliente.")
        else:
            st.info(f"Se encontraron {len(reclamos_cliente)} reclamo(s) para el cliente {n_cliente}.")
            for _, reclamo in reclamos_cliente.iterrows():
                with st.expander(f"Reclamo ID: {reclamo['ID Reclamo']}"):
                    _render_edit_form(reclamo, df_reclamos, sheet_reclamos)

def _render_edit_form(reclamo, df_reclamos, sheet_reclamos):
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
                st.success(f"Reclamo {reclamo['ID Reclamo']} actualizado.")
                st.rerun()
            else:
                st.error("No se pudo actualizar el reclamo.")

def _gestionar_desconexiones(df, sheet_reclamos):
    st.markdown("### 🔌 Gestión de Desconexiones a Pedido")
    desconexiones = df[(df["Tipo de reclamo"].str.strip().str.lower() == "desconexion a pedido") & (df["Estado"].str.strip().str.lower() == "desconexión")]
    if desconexiones.empty:
        st.success("✅ No hay desconexiones pendientes de marcar como resueltas.")
        return
    st.info(f"📄 Hay {len(desconexiones)} desconexiones cargadas. Ir a Impresión para imprimir listado.")
    cambios = False
    for i, row in desconexiones.iterrows():
        with st.container():
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"**{row['Nº Cliente']} - {row['Nombre']}**")
                st.markdown(f"📅 {format_fecha(row['Fecha y hora'])} - Sector {row['Sector']}")
            with col2:
                if st.button("✅ Marcar como resuelto", key=f"resuelto_{i}", use_container_width=True):
                    if _marcar_desconexion_como_resuelta(row, sheet_reclamos):
                        cambios = True
            st.divider()
    if cambios:
        st.rerun()

def _marcar_desconexion_como_resuelta(row, sheet_reclamos):
    with st.spinner("Actualizando estado..."):
        try:
            fila = row.name + 2
            success, error = api_manager.safe_sheet_operation(sheet_reclamos.update, f"I{fila}", "Resuelto")
            if success:
                st.toast(f"✅ Desconexión de {row['Nombre']} marcada como resuelta.")
                return True
            else:
                st.error(f"❌ Error al actualizar: {error}")
                return False
        except Exception as e:
            st.error(f"❌ Error inesperado: {str(e)}")
            if DEBUG_MODE: st.exception(e)
            return False

def _actualizar_fila_reclamo(reclamo_id, df_reclamos, sheet_reclamos, updates):
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
