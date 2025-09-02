# components/reclamos/cierre.py

import time
import pandas as pd
import streamlit as st
import pytz
from datetime import datetime

from utils.date_utils import format_fecha, ahora_argentina, parse_fecha
from utils.api_manager import api_manager
from utils.data_manager import batch_update_sheet
from config.settings import TECNICOS_DISPONIBLES, COLUMNAS_RECLAMOS, DEBUG_MODE

def _excel_col_letter(n: int) -> str:
    letters = ""
    while n:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return letters

def _col_letter(col_name: str) -> str:
    try:
        idx = COLUMNAS_RECLAMOS.index(col_name) + 1
        return _excel_col_letter(idx)
    except (ValueError, IndexError):
        # Fallback por si la columna no está en la lista principal
        st.warning(f"Advertencia: La columna '{col_name}' no se encontró en la configuración. La actualización podría fallar.")
        return None

def render_cierre_reclamos(df_reclamos, df_clientes, sheet_reclamos, sheet_clientes, user):
    st.header("✅ Cierre y Gestión de Reclamos")

    # Preparación de datos una sola vez
    df_reclamos["ID Reclamo"] = df_reclamos["ID Reclamo"].astype(str).str.strip()
    df_reclamos["Nº Cliente"] = df_reclamos["Nº Cliente"].astype(str).str.strip()
    df_reclamos["Técnico"] = df_reclamos["Técnico"].astype(str).fillna("")
    df_reclamos["Fecha y hora"] = df_reclamos["Fecha y hora"].apply(parse_fecha)

    # --- Layout con Pestañas ---
    tab1, tab2, tab3 = st.tabs(["Cerrar Reclamos en Curso", "Reasignar Técnico", "Limpieza de Reclamos Antiguos"])

    with tab1:
        st.subheader("📋 Lista de Reclamos en Curso")
        if _mostrar_reclamos_en_curso(df_reclamos, df_clientes, sheet_reclamos, sheet_clientes):
            st.rerun()

    with tab2:
        st.subheader("🔄 Reasignar Técnico por Nº de Cliente")
        if _mostrar_reasignacion_tecnico(df_reclamos, sheet_reclamos):
            st.rerun()

    with tab3:
        st.subheader("🗑️ Limpieza de Reclamos Antiguos")
        if _mostrar_limpieza_reclamos(df_reclamos, sheet_reclamos):
            st.rerun()

    return {'needs_refresh': False}

def _mostrar_reasignacion_tecnico(df_reclamos, sheet_reclamos):
    with st.container(border=True):
        cliente_busqueda = st.text_input("🔢 Ingresa el N° de Cliente para buscar y reasignar", key="buscar_cliente_tecnico").strip()

        if not cliente_busqueda:
            st.info("Ingresa un número de cliente para comenzar.")
            return False

        reclamos_filtrados = df_reclamos[(df_reclamos["Nº Cliente"] == cliente_busqueda) & (df_reclamos["Estado"].isin(["Pendiente", "En curso"]))]

        if reclamos_filtrados.empty:
            st.warning("⚠️ No se encontró un reclamo activo para ese cliente.")
            return False

        reclamo = reclamos_filtrados.iloc[0]
        st.markdown(f"**Reclamo encontrado:** {reclamo['Tipo de reclamo']} (`{reclamo['Estado']}`)")
        st.caption(f"Técnico actual: **{reclamo['Técnico'] or 'No asignado'}** | Sector: **{reclamo.get('Sector', 'N/A')}**")

        tecnicos_actuales_raw = [t.strip().lower() for t in reclamo["Técnico"].split(",") if t.strip()]
        tecnicos_actuales = [tecnico for tecnico in TECNICOS_DISPONIBLES if tecnico.lower() in tecnicos_actuales_raw]

        nuevo_tecnico_multiselect = st.multiselect("👷 Asignar nuevo(s) técnico(s)", options=TECNICOS_DISPONIBLES, default=tecnicos_actuales, key="nuevo_tecnico_input")

        if st.button("💾 Guardar Nuevo Técnico", key="guardar_tecnico", use_container_width=True):
            with st.spinner("Actualizando técnico..."):
                fila_index = reclamo.name + 2
                nuevo_tecnico = ", ".join(nuevo_tecnico_multiselect).upper()
                updates = [{"range": f"{_col_letter('Técnico')}{fila_index}", "values": [[nuevo_tecnico]]}]
                if reclamo['Estado'] == "Pendiente":
                    updates.append({"range": f"{_col_letter('Estado')}{fila_index}", "values": [["En curso"]]})
                
                success, error = api_manager.safe_sheet_operation(batch_update_sheet, sheet_reclamos, updates, is_batch=True)
                if success:
                    st.success("✅ Técnico actualizado correctamente.")
                    time.sleep(1)
                    return True
                else:
                    st.error(f"❌ Error al actualizar: {error}")
    return False

def _mostrar_reclamos_en_curso(df_reclamos, df_clientes, sheet_reclamos, sheet_clientes):
    en_curso = df_reclamos[df_reclamos["Estado"] == "En curso"].copy()
    
    # --- Filtros ---
    tecnicos_unicos = sorted(set(tecnico.strip().upper() for t in en_curso["Técnico"] for tecnico in t.split(",") if tecnico.strip()))
    tecnicos_seleccionados = st.multiselect("👷 Filtrar por técnico asignado", tecnicos_unicos, key="filtro_tecnicos_cierre")

    if tecnicos_seleccionados:
        en_curso = en_curso[en_curso["Técnico"].apply(lambda t: any(tecnico.strip().upper() in t.upper() for tecnico in tecnicos_seleccionados))]

    if en_curso.empty:
        st.info("📭 No hay reclamos en curso que coincidan con el filtro.")
        return False

    st.caption(f"Mostrando {len(en_curso)} reclamos en curso.")
    
    # --- Tarjetas de Reclamo ---
    for i, row in en_curso.iterrows():
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**{row['Nombre']}** (`#{row['Nº Cliente']}`)")
                st.markdown(f"**{row['Tipo de reclamo']}** - Sector {row.get('Sector', 'N/A')}")
                st.caption(f"Ingreso: {format_fecha(row['Fecha y hora'])} | Asignado a: {row['Técnico']}")

            with col2:
                cliente_id = str(row["Nº Cliente"]).strip()
                cliente_info = df_clientes[df_clientes["Nº Cliente"] == cliente_id]
                precinto_actual = cliente_info["N° de Precinto"].values[0] if not cliente_info.empty else ""
                nuevo_precinto = st.text_input("🔒 Precinto", value=precinto_actual, key=f"precinto_{i}")

            btn_cols = st.columns(2)
            if btn_cols[0].button("✅ Marcar como Resuelto", key=f"resolver_{row['ID Reclamo']}", use_container_width=True):
                if _cerrar_reclamo(row, nuevo_precinto, precinto_actual, cliente_info, sheet_reclamos, sheet_clientes):
                    return True

            if btn_cols[1].button("↩️ Devolver a Pendiente", key=f"volver_{row['ID Reclamo']}", use_container_width=True):
                if _volver_a_pendiente(row, sheet_reclamos):
                    return True
    return False

def _cerrar_reclamo(row, nuevo_precinto, precinto_actual, cliente_info, sheet_reclamos, sheet_clientes):
    with st.spinner("Cerrando reclamo..."):
        fila_index = row.name + 2
        fecha_resolucion = ahora_argentina().strftime('%d/%m/%Y %H:%M')
        updates = [
            {"range": f"{_col_letter('Estado')}{fila_index}", "values": [["Resuelto"]]},
            {"range": f"{_col_letter('Fecha_formateada')}{fila_index}", "values": [[fecha_resolucion]]},
        ]
        if nuevo_precinto.strip() and nuevo_precinto != precinto_actual:
            updates.append({"range": f"{_col_letter('N° de Precinto')}{fila_index}", "values": [[nuevo_precinto.strip()]]})

        success, error = api_manager.safe_sheet_operation(batch_update_sheet, sheet_reclamos, updates, is_batch=True)
        if success:
            if nuevo_precinto.strip() and nuevo_precinto != precinto_actual and not cliente_info.empty:
                index_cliente_en_clientes = cliente_info.index[0] + 2
                api_manager.safe_sheet_operation(sheet_clientes.update, f"F{index_cliente_en_clientes}", [[nuevo_precinto.strip()]])
            st.toast(f"Reclamo de {row['Nombre']} cerrado.")
            return True
        else:
            st.error(f"Error al cerrar: {error}")
    return False

def _volver_a_pendiente(row, sheet_reclamos):
    with st.spinner("Cambiando estado..."):
        fila_index = row.name + 2
        updates = [
            {"range": f"{_col_letter('Estado')}{fila_index}", "values": [["Pendiente"]]},
            {"range": f"{_col_letter('Técnico')}{fila_index}", "values": [[""]]},
            {"range": f"{_col_letter('Fecha_formateada')}{fila_index}", "values": [[""]]},
        ]
        success, error = api_manager.safe_sheet_operation(batch_update_sheet, sheet_reclamos, updates, is_batch=True)
        if success:
            st.toast(f"Reclamo de {row['Nombre']} devuelto a pendiente.")
            return True
        else:
            st.error(f"Error al actualizar: {error}")
    return False

def _mostrar_limpieza_reclamos(df_reclamos, sheet_reclamos):
    with st.container(border=True):
        st.markdown("##### Eliminar reclamos resueltos con más de 10 días de antigüedad")
        tz_argentina = pytz.timezone("America/Argentina/Buenos_Aires")
        df_resueltos = df_reclamos[df_reclamos["Estado"] == "Resuelto"].copy()

        # Asegurar que la columna de fecha sea datetime
        df_resueltos["Fecha y hora"] = pd.to_datetime(df_resueltos["Fecha y hora"], errors='coerce')
        df_resueltos.dropna(subset=["Fecha y hora"], inplace=True)

        # Manejo de zona horaria
        if df_resueltos["Fecha y hora"].dt.tz is None:
            df_resueltos["Fecha y hora"] = df_resueltos["Fecha y hora"].dt.tz_localize(tz_argentina)
        else:
            df_resueltos["Fecha y hora"] = df_resueltos["Fecha y hora"].dt.tz_convert(tz_argentina)

        df_resueltos["Dias_resuelto"] = (datetime.now(tz_argentina) - df_resueltos["Fecha y hora"]).dt.days
        df_antiguos = df_resueltos[df_resueltos["Dias_resuelto"] > 10]

        st.metric(label="Reclamos antiguos para eliminar", value=len(df_antiguos))

        if not df_antiguos.empty:
            if st.button("🗑️ Eliminar reclamos antiguos ahora", use_container_width=True):
                with st.spinner("Eliminando..."):
                    # Implementar lógica de eliminación
                    st.warning("La lógica de eliminación aún no está implementada.")
                return True # Simula cambio para refresh
    return False
