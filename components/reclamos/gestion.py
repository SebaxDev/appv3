# components/reclamos/gestion.py

import streamlit as st
import pandas as pd
from datetime import datetime
from utils.date_utils import format_fecha, parse_fecha
from utils.api_manager import api_manager
from utils.data_manager import batch_update_sheet as dm_batch_update_sheet
from config.settings import SECTORES_DISPONIBLES, DEBUG_MODE, TECNICOS_DISPONIBLES

def render_gestion_reclamos(df_reclamos, df_clientes, sheet_reclamos, user):
    """
    Dashboard de gestión de reclamos con contadores, dataframe compacto y editor.
    """
    st.subheader("📊 Dashboard de Gestión de Reclamos")
    
    try:
        if df_reclamos.empty:
            st.info("No hay reclamos para mostrar.")
            return

        # Prepara los datos
        df_preparado = _preparar_datos(df_reclamos, df_clientes)
        
        # 1. Mostrar contadores por tipo de reclamo
        _mostrar_contadores_reclamos(df_preparado)
        
        # 2. Mostrar dataframe compacto con filtros
        st.markdown("---")
        st.subheader("📋 Lista Compacta de Reclamos")
        df_filtrado = _mostrar_filtros_y_dataframe(df_preparado)
        
        # 3. Buscador y editor de reclamos (USANDO EL EDITOR MEJORADO)
        st.markdown("---")
        st.subheader("🔍 Buscar y Editar Reclamo")
        cambios_edicion = _mostrar_edicion_reclamo_mejorado(df_filtrado, sheet_reclamos, user)
        
        if cambios_edicion:
            st.success("✅ Reclamo actualizado correctamente.")
            st.rerun()
            return
        
        # 4. Lista de reclamos con estado "Desconexión"
        st.markdown("---")
        st.subheader("🔌 Reclamos con Estado 'Desconexión'")
        _mostrar_reclamos_desconexion(df_preparado, sheet_reclamos, user)

    except Exception as e:
        st.error(f"⚠️ Error en la gestión de reclamos: {str(e)}")
        if DEBUG_MODE:
            st.exception(e)

def _preparar_datos(df_reclamos, df_clientes):
    """Prepara y limpia los datos para su visualización."""
    df = df_reclamos.copy()
    df_clientes_norm = df_clientes.copy()

    # Normalización de columnas clave para el merge
    df_clientes_norm["Nº Cliente"] = df_clientes_norm["Nº Cliente"].astype(str).str.strip()
    df["Nº Cliente"] = df["Nº Cliente"].astype(str).str.strip()
    df["ID Reclamo"] = df["ID Reclamo"].astype(str).str.strip()

    # Verificar si la columna Teléfono ya existe en df_reclamos
    if "Teléfono" not in df.columns:
        # Si no existe, hacer el merge con la columna Teléfono de clientes
        df = pd.merge(df, df_clientes_norm[["Nº Cliente", "Teléfono"]], on="Nº Cliente", how="left")
    else:
        # Si ya existe, verificar si hay valores nulos y completar con datos de clientes
        df_telefono_clientes = df_clientes_norm[["Nº Cliente", "Teléfono"]].rename(columns={"Teléfono": "Teléfono_cliente"})
        df = pd.merge(df, df_telefono_clientes, on="Nº Cliente", how="left")
        # Completar teléfonos nulos con los de la base de clientes
        df["Teléfono"] = df["Teléfono"].fillna(df["Teléfono_cliente"])
        df = df.drop(columns=["Teléfono_cliente"])

    # Manejo de fechas
    df["Fecha y hora"] = pd.to_datetime(df["Fecha y hora"], errors='coerce')
    df.sort_values("Fecha y hora", ascending=False, inplace=True)

    return df

def _mostrar_contadores_reclamos(df):
    """Muestra contadores de reclamos por tipo, separando pendientes y en curso."""
    # Filtrar solo reclamos pendientes y en curso
    df_activos = df[df["Estado"].isin(["Pendiente", "En curso"])]
    
    # Obtener tipos de reclamo que tienen al menos un reclamo activo
    tipos_con_reclamos = df_activos["Tipo de reclamo"].value_counts()
    tipos_reclamo = tipos_con_reclamos.index.tolist()
    
    if len(tipos_reclamo) == 0:
        st.info("No hay reclamos pendientes o en curso para mostrar.")
        return
    
    # Crear columnas para los contadores
    cols = st.columns(min(4, len(tipos_reclamo)))
    
    for i, tipo in enumerate(tipos_reclamo):
        col_idx = i % 4
        with cols[col_idx]:
            # Contar reclamos por tipo (solo pendientes y en curso)
            count = len(df_activos[df_activos["Tipo de reclamo"] == tipo])
            
            # Mostrar tarjeta con contador
            st.markdown(f"""
            <div class="card" style="text-align: center; padding: 1rem;">
                <h3 style="margin: 0; color: var(--primary-color);">{count}</h3>
                <p style="margin: 0; color: var(--text-secondary); font-size: 0.9rem;">{tipo}</p>
            </div>
            """, unsafe_allow_html=True)

def _mostrar_filtros_y_dataframe(df):
    """Muestra filtros y el dataframe compacto de reclamos."""
    # Filtros
    col1, col2, col3 = st.columns(3)
    
    with col1:
        estado = st.selectbox("Filtrar por Estado", 
                             ["Todos"] + sorted(df["Estado"].dropna().unique()),
                             key="filtro_estado")
    
    with col2:
        sector = st.selectbox("Filtrar por Sector", 
                             ["Todos"] + SECTORES_DISPONIBLES,
                             key="filtro_sector")
    
    with col3:
        tipo_reclamo = st.selectbox("Filtrar por Tipo", 
                                   ["Todos"] + sorted(df["Tipo de reclamo"].dropna().unique()),
                                   key="filtro_tipo")
    
    # Aplicar filtros
    df_filtrado = df.copy()
    
    if estado != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Estado"] == estado]
    
    if sector != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Sector"] == sector]
    
    if tipo_reclamo != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Tipo de reclamo"] == tipo_reclamo]
    
    # Limitar a los últimos 100 reclamos
    df_filtrado = df_filtrado.head(100)
    
    # Seleccionar columnas específicas para mostrar
    columnas_mostrar = ["Fecha y hora", "Nº Cliente", "Nombre", "Sector", "Tipo de reclamo", "Teléfono", "Estado"]
    
    # Verificar que todas las columnas existan en el DataFrame
    columnas_disponibles = [col for col in columnas_mostrar if col in df_filtrado.columns]
    
    df_mostrar = df_filtrado[columnas_disponibles].copy()
    
    # Formatear fecha
    if "Fecha y hora" in df_mostrar.columns:
        df_mostrar["Fecha y hora"] = df_mostrar["Fecha y hora"].apply(
            lambda x: format_fecha(x, "%d/%m/%Y %H:%M") if pd.notna(x) else "N/A"
        )
    
    # Mostrar dataframe con estilo
    st.dataframe(
        df_mostrar,
        use_container_width=True,
        height=400,
        hide_index=True,
        column_config={
            "Fecha y hora": st.column_config.TextColumn("Fecha/Hora", width="small"),
            "Nº Cliente": st.column_config.TextColumn("N° Cliente", width="small"),
            "Nombre": st.column_config.TextColumn("Nombre", width="medium"),
            "Sector": st.column_config.TextColumn("Sector", width="small"),
            "Tipo de reclamo": st.column_config.TextColumn("Tipo Reclamo", width="medium"),
            "Teléfono": st.column_config.TextColumn("Teléfono", width="medium"),
            "Estado": st.column_config.TextColumn("Estado", width="small"),
        }
    )
    
    st.caption(f"Mostrando {len(df_mostrar)} de {len(df_filtrado)} reclamos filtrados")
    
    return df_filtrado

# --- EDITOR MEJORADO (REEMPLAZANDO EL ANTERIOR) ---
def _mostrar_edicion_reclamo_mejorado(df, sheet_reclamos, user):
    """Muestra la interfaz para editar reclamos (versión mejorada de gestion2.py)"""
    st.markdown("### ✏️ Editar un reclamo puntual")
    
    # Crear selector mejorado (sin UUID visible)
    df["selector"] = df.apply(
        lambda x: f"{x['Nº Cliente']} - {x['Nombre']} ({x['Estado']})", 
        axis=1
    )
    
    # Añadir búsqueda por número de cliente o nombre
    busqueda = st.text_input("🔍 Buscar por número de cliente o nombre")
    
    # Filtrar opciones basadas en la búsqueda
    opciones_filtradas = [""] + df["selector"].tolist()
    if busqueda:
        opciones_filtradas = [""] + [
            opc for opc in df["selector"].tolist() 
            if busqueda.lower() in opc.lower()
        ]
    
    seleccion = st.selectbox(
        "Seleccioná un reclamo para editar", 
        opciones_filtradas,
        index=0
    )

    if not seleccion:
        return False

    # Obtener el ID del reclamo
    numero_cliente = seleccion.split(" - ")[0]
    reclamo_actual = df[df["Nº Cliente"] == numero_cliente].iloc[0]
    reclamo_id = reclamo_actual["ID Reclamo"]

    # Mostrar información del reclamo
    with st.expander("📄 Información del reclamo", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**📅 Fecha:** {format_fecha(reclamo_actual['Fecha y hora'])}")
            st.markdown(f"**👤 Cliente:** {reclamo_actual['Nombre']}")
            st.markdown(f"**📍 Sector:** {reclamo_actual['Sector']}")
        with col2:
            st.markdown(f"**📌 Tipo:** {reclamo_actual['Tipo de reclamo']}")
            st.markdown(f"**⚙️ Estado actual:** {reclamo_actual['Estado']}")
            st.markdown(f"**👷 Técnico:** {reclamo_actual.get('Técnico', 'No asignado')}")

    # Formulario de edición
    with st.form(f"form_editar_{reclamo_id}"):
        col1, col2 = st.columns(2)
        
        with col1:
            direccion = st.text_input(
                "Dirección", 
                value=reclamo_actual.get("Dirección", ""),
                help="Dirección completa del cliente"
            )
            telefono = st.text_input(
                "Teléfono", 
                value=reclamo_actual.get("Teléfono", ""),
                help="Número de contacto del cliente"
            )
        
        with col2:
            tipo_reclamo = st.selectbox(
                "Tipo de reclamo", 
                sorted(df["Tipo de reclamo"].unique()),
                index=sorted(df["Tipo de reclamo"].unique()).index(
                    reclamo_actual["Tipo de reclamo"]
                ) if reclamo_actual["Tipo de reclamo"] in sorted(df["Tipo de reclamo"].unique()) else 0
            )
            
            try:
                sector_normalizado = str(int(str(reclamo_actual.get("Sector", "")).strip()))
                index_sector = SECTORES_DISPONIBLES.index(sector_normalizado) if sector_normalizado in SECTORES_DISPONIBLES else 0
            except Exception:
                index_sector = 0

            sector_edit = st.selectbox(
                "Sector",
                options=SECTORES_DISPONIBLES,
                index=index_sector
            )
        
        detalles = st.text_area(
            "Detalles", 
            value=reclamo_actual.get("Detalles", ""), 
            height=100
        )
        
        precinto = st.text_input(
            "N° de Precinto", 
            value=reclamo_actual.get("N° de Precinto", ""),
            help="Número de precinto del medidor"
        )

        # Estados disponibles (incluyendo "Desconexión")
        estados_disponibles = ["Pendiente", "En curso", "Desconexión", "Resuelto"]
        
        # Determinar índice inicial
        estado_actual = reclamo_actual["Estado"]
        index_estado = estados_disponibles.index(estado_actual) if estado_actual in estados_disponibles else 0

        estado_nuevo = st.selectbox(
            "Nuevo estado", 
            estados_disponibles,
            index=index_estado
        )

        # Botones de acción
        col1, col2 = st.columns(2)
        
        guardar_cambios = col1.form_submit_button(
            "💾 Guardar todos los cambios",
            use_container_width=True
        )
        
        cambiar_estado = col2.form_submit_button(
            "🔄 Cambiar solo estado",
            use_container_width=True
        )

    # Procesar acciones
    if guardar_cambios:
        if not direccion.strip() or not detalles.strip():
            st.warning("⚠️ Dirección y detalles no pueden estar vacíos.")
            return False
        
        return _actualizar_reclamo_mejorado(
            df, sheet_reclamos, reclamo_id,
            {
                "direccion": direccion,
                "telefono": telefono,
                "tipo_reclamo": tipo_reclamo,
                "detalles": detalles,
                "precinto": precinto,
                "sector": sector_edit,
                "estado": estado_nuevo,
                "nombre": reclamo_actual.get("Nombre", "")
            },
            full_update=True
        )

    if cambiar_estado:
        return _actualizar_reclamo_mejorado(
            df, sheet_reclamos, reclamo_id,
            {"estado": estado_nuevo},
            full_update=False
        )
    
    return False

def _actualizar_reclamo_mejorado(df, sheet_reclamos, reclamo_id, updates, full_update=False):
    """Actualiza el reclamo en la hoja de cálculo (versión mejorada)"""
    with st.spinner("Actualizando reclamo..."):
        try:
            fila = df[df["ID Reclamo"] == reclamo_id].index[0] + 2
            updates_list = []
            estado_anterior = df[df["ID Reclamo"] == reclamo_id]["Estado"].values[0]

            if full_update:
                # Mapeo de columnas según la hoja de cálculo
                updates_list.extend([
                    {"range": f"D{fila}", "values": [[updates['nombre'].upper()]]},      # Nombre
                    {"range": f"E{fila}", "values": [[updates['direccion'].upper()]]},   # Dirección
                    {"range": f"F{fila}", "values": [[str(updates['telefono'])]]},       # Teléfono
                    {"range": f"G{fila}", "values": [[updates['tipo_reclamo']]]},        # Tipo reclamo
                    {"range": f"H{fila}", "values": [[updates['detalles']]]},            # Detalles
                    {"range": f"K{fila}", "values": [[updates['precinto']]]},            # Precinto
                    {"range": f"C{fila}", "values": [[str(updates['sector'])]]},         # Sector
                ])

            # Estado (columna I)
            updates_list.append({"range": f"I{fila}", "values": [[updates['estado']]]})

            # Si pasa a pendiente, limpiar columna J (técnico)
            if updates['estado'] == "Pendiente":
                updates_list.append({"range": f"J{fila}", "values": [[""]]})

            # Guardar en Google Sheets
            success, error = api_manager.safe_sheet_operation(
                dm_batch_update_sheet, 
                sheet_reclamos, 
                updates_list, 
                is_batch=True
            )

            if success:
                st.success("✅ Reclamo actualizado correctamente.")
                return True
            else:
                st.error(f"❌ Error al actualizar: {error}")
                return False

        except Exception as e:
            st.error(f"❌ Error inesperado: {str(e)}")
            if DEBUG_MODE:
                st.exception(e)
            return False

def _mostrar_reclamos_desconexion(df, sheet_reclamos, user):
    """
    Muestra los reclamos con estado 'Desconexión' y permite marcarlos como resueltos.
    """

    st.markdown("### 🔌 Desconexiones a Pedido (en estado 'Desconexión')")

    # Filtrar todos los reclamos con estado "Desconexión"
    df_desconexion = df[
        df["Estado"].astype(str).str.strip().str.lower() == "desconexión"
    ]

    if df_desconexion.empty:
        st.info("No hay desconexiones a pedido pendientes.")
        return

    for _, row in df_desconexion.iterrows():
        with st.container(border=True):
            card_id = row.get("ID Reclamo", row.get("ID", ""))
            nombre = row.get("Nombre", "Sin nombre")
            direccion = row.get("Dirección", "Sin dirección")
            fecha = row.get("Fecha y hora", "")
            tecnico = row.get("Técnico", "Sin asignar")

            col1, col2, col3 = st.columns([3, 2, 2])
            with col1:
                st.markdown(f"**👤 Cliente:** {nombre}")
                st.markdown(f"🏠 {direccion}")
                st.markdown(f"📅 {fecha}")
            with col2:
                st.markdown(f"🧰 Técnico: {tecnico}")
                st.markdown(f"📞 Nº Cliente: {row.get('Nº Cliente', '')}")
            with col3:
                st.markdown(f"🆔 ID: `{card_id}`")
                if st.button(f"✅ Marcar Resuelto", key=f"resuelto_{card_id}", use_container_width=True):
                    try:
                        exito = _actualizar_reclamo_mejorado(
                            df,
                            sheet_reclamos,
                            card_id,
                            {"estado": "Resuelto"},
                            full_update=False
                        )

                        if exito:
                            st.success(f"Reclamo {card_id} marcado como resuelto.")
                            st.rerun()
                        else:
                            st.warning(f"No se pudo actualizar el reclamo {card_id}.")
                    except Exception as e:
                        st.error(f"❌ Error al actualizar reclamo {card_id}: {e}")


def _actualizar_reclamo(df, sheet_reclamos, reclamo_id, updates, user, full_update=False):
    """Función original de actualización (mantenida por compatibilidad)"""
    # Esta función se mantiene para compatibilidad con otras partes del código
    # pero ahora usa la versión mejorada internamente
    return _actualizar_reclamo_mejorado(df, sheet_reclamos, reclamo_id, updates, full_update)