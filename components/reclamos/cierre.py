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

# Constantes y helpers comunes
DIAS_ELIMINACION = 30

COLUMN_IDX = {name: i for i, name in enumerate(COLUMNAS_RECLAMOS)}

def _r1c1(row_index_1_based: int, column_name: str) -> str:
    """Construye referencia R1C1 para Google Sheets a partir del nombre de columna."""
    return f"R{row_index_1_based}C{COLUMN_IDX[column_name] + 1}"

def _build_updates(row_index_1_based: int, values_by_column: dict) -> list:
    """Devuelve lista de updates batch dado un mapping {columna: valor}."""
    return [
        {"range": _r1c1(row_index_1_based, col), "values": [[val]]}
        for col, val in values_by_column.items()
    ]

def _parse_tecnicos(cadena: str) -> list:
    """Convierte cadena de técnicos en lista normalizada (upper, sin espacios extra)."""
    return [t.strip().upper() for t in (cadena or "").split(',') if t.strip()]

def _handle_resolver_reclamo(reclamo, sheet_reclamos, sheet_clientes, df_clientes):
    """Marca un reclamo como 'Resuelto' y actualiza la hoja de cálculo con anotaciones."""
    try:
        with st.spinner("Resolviendo reclamo..."):
            id_reclamo = reclamo['ID Reclamo']
            nuevo_precinto = st.session_state.get(f"precinto_{id_reclamo}", "").strip()
            anotaciones = st.session_state.get(f"anotaciones_{id_reclamo}", "").strip()

            fila_index = reclamo.name + 2

            fecha_resolucion = ahora_argentina().strftime('%d/%m/%Y %H:%M')

            updates = _build_updates(
                fila_index,
                {
                    "Estado": "Resuelto",
                    "Fecha_formateada": fecha_resolucion,
                    "Anotaciones": anotaciones  # Guardar anotaciones en el reclamo (Columna N)
                },
            )

            if nuevo_precinto and nuevo_precinto != reclamo.get("N° de Precinto", ""):
                updates += _build_updates(fila_index, {"N° de Precinto": nuevo_precinto})

            success, error = api_manager.safe_sheet_operation(
                batch_update_sheet, sheet_reclamos, updates, is_batch=True
            )

            if success:
                # Actualizar anotaciones en cliente si se proporcionaron (Columna I)
                if anotaciones:
                    cliente_info = df_clientes[df_clientes["Nº Cliente"] == reclamo["Nº Cliente"]]
                    if not cliente_info.empty:
                        idx_cliente = cliente_info.index[0] + 2
                        updates_cliente = [
                            {
                                "range": "I" + str(idx_cliente),  # Columna I: Anotaciones
                                "values": [[anotaciones]],
                            }
                        ]
                        api_manager.safe_sheet_operation(
                            batch_update_sheet, sheet_clientes, updates_cliente, is_batch=True
                        )
                
                # Limpiar campos del session_state
                for key in [f"precinto_{id_reclamo}", f"anotaciones_{id_reclamo}"]:
                    if key in st.session_state:
                        del st.session_state[key]
                
                # ACTUALIZAR LOS DATOS EN SESSION_STATE PARA QUE DESAPAREZCA INMEDIATAMENTE
                if 'df_reclamos' in st.session_state:
                    # Actualizar el estado del reclamo en los datos en memoria
                    st.session_state.df_reclamos.at[reclamo.name, 'Estado'] = 'Resuelto'
                    st.session_state.df_reclamos.at[reclamo.name, 'Fecha_formateada'] = fecha_resolucion
                    st.session_state.df_reclamos.at[reclamo.name, 'Anotaciones'] = anotaciones
                
                # MARCAR QUE NECESITAMOS REFRESCAR (como en cierre2.py)
                st.session_state.force_refresh_cierre = True
                
                st.toast(f"✅ Reclamo #{reclamo['Nº Cliente']} marcado como Resuelto.", icon="🎉")
                
                # Forzar rerun para actualizar la interfaz inmediatamente
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
            updates = _build_updates(
                fila_index,
                {"Estado": "Pendiente", "Técnico": "", "Fecha_formateada": ""},
            )
            success, error = api_manager.safe_sheet_operation(
                batch_update_sheet, sheet_reclamos, updates, is_batch=True
            )
            if success:
                # Limpiar el campo de precinto del session_state si existe
                id_reclamo = reclamo['ID Reclamo']
                if f"precinto_{id_reclamo}" in st.session_state:
                    del st.session_state[f"precinto_{id_reclamo}"]
                
                # ACTUALIZAR LOS DATOS EN SESSION_STATE PARA QUE DESAPAREZCA INMEDIATAMENTE
                if 'df_reclamos' in st.session_state:
                    # Actualizar el estado del reclamo en los datos en memoria
                    st.session_state.df_reclamos.at[reclamo.name, 'Estado'] = 'Pendiente'
                    st.session_state.df_reclamos.at[reclamo.name, 'Técnico'] = ''
                    st.session_state.df_reclamos.at[reclamo.name, 'Fecha_formateada'] = ''
                
                # MARCAR QUE NECESITAMOS REFRESCAR (como en cierre2.py)
                st.session_state.force_refresh_cierre = True
                
                st.toast(f"↩️ Reclamo #{reclamo['Nº Cliente']} devuelto a Pendiente.", icon="🔄")
                
                # Forzar rerun para actualizar la interfaz inmediatamente
                st.rerun()
            else:
                st.error(f"Error al devolver a pendiente: {error}")
    except Exception as e:
        st.error(f"Error inesperado al devolver reclamo: {e}")

def _verificar_y_actualizar_filtro():
    """Verifica si el filtro actual necesita actualizarse y lo resetea si es necesario."""
    if 'cierre_filtro_tecnico' in st.session_state:
        filtro_actual = st.session_state.cierre_filtro_tecnico
        if filtro_actual != "Todos":
            # Marcar que se debe verificar el filtro en el próximo render
            st.session_state.verificar_filtro = True

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
        reclamos_a_eliminar = df_resueltos[df_resueltos["DiasDesdeCierre"] > DIAS_ELIMINACION].copy()

        st.metric(label=f"Reclamos resueltos con más de {DIAS_ELIMINACION} días", value=len(reclamos_a_eliminar))
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
    
    # Manejar el refresh forzado (como en cierre2.py)
    if st.session_state.get('force_refresh_cierre', False):
        st.session_state.force_refresh_cierre = False
        # Limpiar cache y forzar recarga de datos
        if 'df_reclamos' in st.session_state:
            del st.session_state.df_reclamos
        st.rerun()
    
    st.subheader("✅ Gestión y Cierre de Reclamos")
    st.markdown("---")
    
    try:
        # Usar los datos actualizados de session_state si están disponibles
        if 'df_reclamos' in st.session_state:
            df_reclamos_actual = st.session_state.df_reclamos
        else:
            df_reclamos_actual = df_reclamos
            
        df_en_curso = df_reclamos_actual[df_reclamos_actual["Estado"].str.strip().str.lower() == "en curso"].copy()
        df_en_curso["Fecha y hora"] = pd.to_datetime(df_en_curso["Fecha y hora"], dayfirst=True, errors='coerce')
    except Exception as e:
        st.error(f"Error al procesar los datos de reclamos: {e}")
        return

    # --- Reasignación rápida por N° de Cliente ---
    _render_reasignacion_tecnico(df_reclamos, sheet_reclamos)

    # --- Verificación automática del filtro ---
    if st.session_state.get('verificar_filtro', False):
        _verificar_filtro_automaticamente(df_en_curso)
        st.session_state.verificar_filtro = False

    if df_en_curso.empty and st.session_state.get('cierre_filtro_tecnico', "Todos") == "Todos":
        st.info("👍 ¡Excelente! No hay reclamos 'En curso' en este momento.")

    # --- Filtros ---
    st.markdown("#### 🔍 Filtrar Reclamos")
    tecnicos_activos = sorted({t for s in df_en_curso["Técnico"].dropna() for t in _parse_tecnicos(s)})
    opciones_filtro = ["Todos"] + tecnicos_activos
    
    # Inicializar filtro si no existe
    if 'cierre_filtro_tecnico' not in st.session_state:
        st.session_state.cierre_filtro_tecnico = "Todos"
    
    # Verificar si el técnico del filtro actual aún tiene reclamos
    filtro_actual = st.session_state.cierre_filtro_tecnico
    if filtro_actual != "Todos" and filtro_actual not in tecnicos_activos:
        st.toast(f"ℹ️ El técnico {filtro_actual} ya no tiene reclamos. Filtro reseteado a 'Todos'.", icon="ℹ️")
        st.session_state.cierre_filtro_tecnico = "Todos"
        st.rerun()
    
    filtro_tecnico_idx = opciones_filtro.index(st.session_state.cierre_filtro_tecnico)
    
    def on_filter_change():
        st.session_state.cierre_filtro_tecnico = st.session_state.cierre_filtro_selectbox
    
    st.selectbox(
        "Filtrar por técnico:", 
        options=opciones_filtro, 
        index=filtro_tecnico_idx,
        key='cierre_filtro_selectbox', 
        on_change=on_filter_change,
        help="Selecciona un técnico para ver solo sus reclamos."
    )
    
    filtro_tecnico = st.session_state.cierre_filtro_tecnico
    
    # Aplicar filtro
    if filtro_tecnico != "Todos":
        df_filtrado = df_en_curso[df_en_curso["Técnico"].apply(lambda s: filtro_tecnico in _parse_tecnicos(s))].copy()
    else:
        df_filtrado = df_en_curso.copy()

    if not df_en_curso.empty:
        st.markdown(f"**Mostrando {len(df_filtrado)} de {len(df_en_curso)} reclamos en curso.**")
        st.markdown("---")

    if df_filtrado.empty and filtro_tecnico != "Todos":
        st.info(f"El técnico {filtro_tecnico} no tiene reclamos 'En curso'.")
        # Opción para volver a la vista general
        if st.button("🔄 Ver todos los reclamos", key="ver_todos_reclamos"):
            st.session_state.cierre_filtro_tecnico = "Todos"
            st.rerun()
    else:
        df_filtrado = df_filtrado.sort_values(by="Fecha y hora", ascending=False)
        for index, reclamo in df_filtrado.iterrows():
            id_reclamo = reclamo['ID Reclamo']
            with st.expander(f"**#{reclamo['Nº Cliente']} - {reclamo['Nombre']}** | {reclamo['Tipo de reclamo']} | Creado: {format_fecha(reclamo['Fecha y hora'])}"):
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    st.markdown(f"**Dirección:** {reclamo.get('Dirección', 'N/A')}")
                    st.markdown(f"**Técnico(s):** `{reclamo.get('Técnico', 'No asignado')}`")
                
                # Campo de precinto con valor por defecto del reclamo
                precinto_actual = reclamo.get("N° de Precinto", "")
                st.text_input(
                    "N° de Precinto (si aplica)", 
                    value=precinto_actual, 
                    key=f"precinto_{id_reclamo}",
                    help="Deja vacío si no hay precinto o ingresa el nuevo número"
                )

                # Campo para anotaciones (nuevo) - Columna N en Reclamos
                anotaciones_actuales = reclamo.get("Anotaciones", "")
                st.text_area(
                    "📝 Anotaciones (opcional)", 
                    value=anotaciones_actuales,
                    key=f"anotaciones_{id_reclamo}",
                    help="Información adicional sobre el trabajo realizado o observaciones del cliente",
                    height=100
                )
                
                with col2:
                    st.button(
                        "✅ Marcar como Resuelto", 
                        key=f"resolver_{id_reclamo}", 
                        on_click=_handle_resolver_reclamo,
                        args=(reclamo, sheet_reclamos, sheet_clientes, df_clientes), 
                        use_container_width=True, 
                        type="primary"
                    )
                with col3:
                    st.button(
                        "↩️ Devolver a Pendiente", 
                        key=f"pendiente_{id_reclamo}", 
                        on_click=_handle_volver_a_pendiente,
                        args=(reclamo, sheet_reclamos), 
                        use_container_width=True
                    )

    # --- Limpieza de Reclamos Antiguos ---
    _render_limpieza_reclamos(df_reclamos_actual, sheet_reclamos)

def _verificar_filtro_automaticamente(df_en_curso):
    """Verifica automáticamente si el filtro actual necesita actualizarse."""
    filtro_actual = st.session_state.get('cierre_filtro_tecnico', "Todos")
    if filtro_actual != "Todos":
        tecnicos_activos = {t for s in df_en_curso["Técnico"].dropna() for t in _parse_tecnicos(s)}
        if filtro_actual not in tecnicos_activos:
            st.session_state.cierre_filtro_tecnico = "Todos"

def _render_reasignacion_tecnico(df_reclamos, sheet_reclamos):
    """Sección superior para reasignar técnico por N° de Cliente."""
    st.markdown("### 🔄 Reasignar técnico por N° de cliente")
    cliente_busqueda = st.text_input(
        "🔢 Ingresá el N° de Cliente para buscar",
        key="buscar_cliente_tecnico",
        help="Busca un reclamo Pendiente o En curso para reasignar técnico.",
    ).strip()

    if not cliente_busqueda:
        return False

    estados_validos = {"pendiente", "en curso"}
    df_filtrados = df_reclamos[
        (df_reclamos["Nº Cliente"].astype(str) == cliente_busqueda)
        & (df_reclamos["Estado"].str.strip().str.lower().isin(estados_validos))
    ]

    if df_filtrados.empty:
        st.warning("⚠️ No se encontró un reclamo pendiente o en curso para ese cliente.")
        return False

    reclamo = df_filtrados.iloc[0]
    st.markdown(f"📌 **Reclamo:** {reclamo['Tipo de reclamo']} - Estado: {reclamo['Estado']}")
    st.markdown(f"👷 Técnico actual: `{reclamo.get('Técnico') or 'No asignado'}`")
    st.markdown(f"📅 Fecha del reclamo: `{format_fecha(pd.to_datetime(reclamo['Fecha y hora'], dayfirst=True, errors='coerce'))}`")
    st.markdown(f"📍 Sector: `{reclamo.get('Sector', 'No especificado')}`")

    # Opciones de técnicos disponibles desde datos actuales
    tecnicos_disponibles = sorted({t for s in df_reclamos["Técnico"].dropna() for t in _parse_tecnicos(s)})
    actuales = [t for t in _parse_tecnicos(reclamo.get("Técnico", "")) if t in tecnicos_disponibles]

    nuevo_tecnico_multiselect = st.multiselect(
        "👷 Nuevo técnico asignado",
        options=tecnicos_disponibles,
        default=actuales,
        key="nuevo_tecnico_input",
        help="Seleccioná uno o más técnicos.",
    )

    if st.button("💾 Guardar nuevo técnico", key="guardar_tecnico"):
        with st.spinner("Actualizando técnico..."):
            try:
                fila_index = reclamo.name + 2
                nuevo_tecnico_valor = ", ".join(nuevo_tecnico_multiselect).upper()

                values = {"Técnico": nuevo_tecnico_valor}
                if str(reclamo['Estado']).strip().lower() == "pendiente" and nuevo_tecnico_valor:
                    values["Estado"] = "En curso"

                updates = _build_updates(fila_index, values)
                success, error = api_manager.safe_sheet_operation(
                    batch_update_sheet, sheet_reclamos, updates, is_batch=True
                )

                if success:
                    st.success("✅ Técnico actualizado correctamente.")
                    if 'notification_manager' in st.session_state and nuevo_tecnico_valor:
                        mensaje = f"📌 El cliente N° {reclamo['Nº Cliente']} fue asignado al técnico {nuevo_tecnico_valor}."
                        st.session_state.notification_manager.add(
                            notification_type="reclamo_asignado",
                            message=mensaje,
                            user_target="all",
                            claim_id=reclamo["ID Reclamo"],
                        )
                    
                    # Limpiar el campo de búsqueda
                    if "buscar_cliente_tecnico" in st.session_state:
                        del st.session_state.buscar_cliente_tecnico
                    
                    st.rerun()
                else:
                    st.error(f"❌ Error al actualizar: {error}")
            except Exception as e:
                st.error(f"❌ Error inesperado: {str(e)}")
        return True

    return False
