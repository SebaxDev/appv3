# components/reclamos/gestion.py

import streamlit as st
import pandas as pd
from datetime import datetime
from utils.date_utils import format_fecha
from utils.api_manager import api_manager, batch_update_sheet
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
        
        # 3. Buscador y editor de reclamos
        st.markdown("---")
        st.subheader("🔍 Buscar y Editar Reclamo")
        _mostrar_buscador_editor(df_preparado, sheet_reclamos, user, df_reclamos)
        
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

def _mostrar_buscador_editor(df, sheet_reclamos, user, df_reclamos_original):
    """Muestra buscador and editor de reclamos individuales."""
    col1, col2 = st.columns([3, 1])
    
    with col1:
        busqueda = st.text_input("Buscar reclamo por ID, N° de Cliente o Nombre:", 
                               placeholder="Ingrese término de búsqueda...")
    
    with col2:
        st.write("")  # Espaciado
        st.write("")  # Espaciado
        buscar_btn = st.button("🔍 Buscar", use_container_width=True)
    
    if buscar_btn and busqueda:
        termino = busqueda.lower().strip()
        
        # Buscar en múltiples campos
        resultados = df[
            df["ID Reclamo"].astype(str).str.lower().str.contains(termino) |
            df["Nº Cliente"].astype(str).str.lower().str.contains(termino) |
            df["Nombre"].str.lower().str.contains(termino)
        ]
        
        if resultados.empty:
            st.warning("No se encontraron reclamos que coincidan con la búsqueda.")
        else:
            st.success(f"Se encontraron {len(resultados)} reclamos.")
            
            # Mostrar selector de reclamo si hay múltiples resultados
            if len(resultados) > 1:
                opciones = [f"{row['ID Reclamo']} - {row['Nombre']} ({row['Nº Cliente']})" 
                           for _, row in resultados.iterrows()]
                seleccion = st.selectbox("Seleccione el reclamo a editar:", opciones)
                
                # Extraer ID del reclamo seleccionado
                reclamo_id = seleccion.split(" - ")[0]
                reclamo = resultados[resultados["ID Reclamo"] == reclamo_id].iloc[0]
            else:
                reclamo = resultados.iloc[0]
                reclamo_id = reclamo["ID Reclamo"]
            
            # Mostrar editor para el reclamo seleccionado
            _mostrar_editor_reclamo(reclamo, reclamo_id, sheet_reclamos, user, df_reclamos_original)

def _mostrar_editor_reclamo(reclamo, reclamo_id, sheet_reclamos, user, df_reclamos):
    """Muestra el formulario de edición para un reclamo específico."""
    with st.expander(f"✏️ Editar Reclamo {reclamo_id}", expanded=True):
        with st.form(key=f"form_edit_{reclamo_id}"):
            col1, col2 = st.columns(2)
            
            with col1:
                nombre = st.text_input("Nombre", value=reclamo.get("Nombre", ""))
                direccion = st.text_input("Dirección", value=reclamo.get("Dirección", ""))
                telefono = st.text_input("Teléfono", value=reclamo.get("Teléfono", ""))
                sector = st.selectbox("Sector", options=SECTORES_DISPONIBLES, 
                                    index=SECTORES_DISPONIBLES.index(reclamo["Sector"]) 
                                    if reclamo["Sector"] in SECTORES_DISPONIBLES else 0)
            
            with col2:
                # Obtener tipos de reclamo únicos y ordenados
                tipos_reclamo_unicos = sorted(df_reclamos["Tipo de reclamo"].unique())
                
                tipo_reclamo = st.selectbox("Tipo de Reclamo", 
                                          options=tipos_reclamo_unicos, 
                                          index=tipos_reclamo_unicos.index(reclamo["Tipo de reclamo"]) 
                                          if reclamo["Tipo de reclamo"] in tipos_reclamo_unicos else 0)
                
                # Manejar técnicos
                tecnico_actual = reclamo.get("Técnico", "")
                index_tecnico = 0
                if tecnico_actual in TECNICOS_DISPONIBLES:
                    index_tecnico = TECNICOS_DISPONIBLES.index(tecnico_actual) + 1
                
                tecnico = st.selectbox("Técnico Asignado", 
                                     options=[""] + TECNICOS_DISPONIBLES, 
                                     index=index_tecnico)
                
                # Manejar estado
                estado_actual = reclamo.get("Estado", "Pendiente")
                estados_opciones = ["Pendiente", "En curso", "Resuelto", "Desconexión"]
                index_estado = estados_opciones.index(estado_actual) if estado_actual in estados_opciones else 0
                
                estado = st.selectbox("Estado", 
                                    options=estados_opciones, 
                                    index=index_estado)
                
                precinto = st.text_input("N° de Precinto", value=reclamo.get("N° de Precinto", ""))
            
            detalles = st.text_area("Detalles", value=reclamo.get("Detalles", ""), height=100)
            
            # Botón de submit para el formulario
            guardar_btn = st.form_submit_button("💾 Guardar Cambios", use_container_width=True)
            
            if guardar_btn:
                updates = {
                    "nombre": nombre,
                    "direccion": direccion,
                    "telefono": telefono,
                    "sector": sector,
                    "tipo_reclamo": tipo_reclamo,
                    "tecnico": tecnico,
                    "detalles": detalles,
                    "precinto": precinto,
                    "estado": estado,
                }
                if _actualizar_reclamo(df_reclamos, sheet_reclamos, reclamo_id, updates, user, full_update=True):
                    st.success("✅ Reclamo actualizado correctamente.")
                    st.rerun()

def _mostrar_reclamos_desconexion(df, sheet_reclamos, user):
    """Muestra lista de reclamos con estado 'Desconexión' y botón para resolver."""
    df_desconexion = df[df["Estado"] == "Desconexión"]
    
    if df_desconexion.empty:
        st.info("No hay reclamos con estado 'Desconexión'.")
        return
    
    st.write(f"**Total de reclamos con desconexión:** {len(df_desconexion)}")
    
    for _, reclamo in df_desconexion.iterrows():
        card_id = reclamo["ID Reclamo"]
        
        with st.container():
            col1, col2, col3 = st.columns([3, 2, 1])
            
            with col1:
                st.markdown(f"**{reclamo['Nombre']}** (`{reclamo['Nº Cliente']}`)")
                st.caption(f"ID Reclamo: {card_id} | Fecha: {format_fecha(reclamo['Fecha y hora'], '%d/%m/%Y %H:%M')}")
                st.markdown(f"*{reclamo['Tipo de reclamo']}* - Sector {reclamo['Sector']}")
            
            with col2:
                st.markdown(f"**Teléfono:** {reclamo.get('Teléfono', 'N/A')}")
                st.markdown(f"**Detalles:** {reclamo.get('Detalles', 'Sin detalles')[:50]}...")
            
            with col3:
                if st.button("✅ Desc de Caja", key=f"resolve_{card_id}", use_container_width=True):
                    if _actualizar_reclamo(df, sheet_reclamos, card_id, {"estado": "Resuelto"}, user):
                        st.success(f"Reclamo {card_id} marcado como resuelto.")
                        st.rerun()
            
            st.divider()

def _actualizar_reclamo(df, sheet_reclamos, reclamo_id, updates, user, full_update=False):
    """Actualiza un reclamo en la hoja de cálculo."""
    with st.spinner("Actualizando..."):
        try:
            fila_idx = df[df["ID Reclamo"] == reclamo_id].index[0]
            fila_google_sheets = fila_idx + 2  # +2 para la cabecera y el índice 1-based

            updates_list = []
            estado_anterior = df.loc[fila_idx, "Estado"]

            # Mapeo de claves a columnas de la hoja
            column_map = {
                "nombre": "D", "direccion": "E", "telefono": "F", "sector": "C",
                "tipo_reclamo": "G", "tecnico": "J", "detalles": "H", "precinto": "K",
                "estado": "I"
            }

            if full_update:
                for key, value in updates.items():
                    if key in column_map:
                        col = column_map[key]
                        updates_list.append({"range": f"{col}{fila_google_sheets}", "values": [[str(value)]]})
            elif "estado" in updates:
                # Actualización rápida solo para el estado
                col = column_map["estado"]
                updates_list.append({"range": f"{col}{fila_google_sheets}", "values": [[updates["estado"]]]})

            if not updates_list:
                st.toast("No hay cambios que guardar.")
                return False

            success, error = api_manager.safe_sheet_operation(
                batch_update_sheet, sheet_reclamos, updates_list, is_batch=True
            )

            if success:
                st.toast(f"✅ Reclamo {reclamo_id} actualizado.")
                # Notificación de cambio de estado
                if "estado" in updates and updates["estado"] != estado_anterior:
                    if 'notification_manager' in st.session_state:
                        st.session_state.notification_manager.add(
                            notification_type="status_change",
                            message=f"Reclamo {reclamo_id} cambió: {estado_anterior} ➜ {updates['estado']}",
                            user_target="all",
                            claim_id=reclamo_id
                        )
                return True
            else:
                st.error(f"❌ Error al actualizar: {error}")
                return False
        except Exception as e:
            st.error(f"❌ Error inesperado al actualizar: {e}")
            if DEBUG_MODE:
                st.exception(e)
            return False