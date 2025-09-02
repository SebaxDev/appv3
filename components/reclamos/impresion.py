# components/reclamos/impresion.py

import io
import streamlit as st
import pandas as pd
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from utils.date_utils import format_fecha, parse_fecha
from utils.pdf_utils import agregar_pie_pdf
from utils.date_utils import ahora_argentina
from utils.reporte_diario import *


def render_impresion_reclamos(df_reclamos, df_clientes, user):
    """
    Muestra la sección para imprimir reclamos en formato PDF
    """
    result = {'needs_refresh': False, 'message': None, 'data_updated': False}
    
    st.subheader("📨️ Seleccionar reclamos para imprimir (formato técnico compacto)")

    try:
        df_merged = _preparar_datos(df_reclamos, df_clientes, user)
        _mostrar_reclamos_pendientes(df_merged)

        with st.expander("⚙️ Configuración de impresión", expanded=True):
            solo_pendientes = st.checkbox("📜 Mostrar solo reclamos pendientes", value=True)
            incluir_usuario = st.checkbox("👤 Incluir mi nombre en el PDF", value=True)
        
        st.markdown("---")
        st.subheader("Opciones de Impresión")

        # --- Fila 1 ---
        col1, col2 = st.columns(2)
        with col1:
            with st.container(border=True):
                mensaje_todos = _generar_pdf_todos_pendientes(df_merged, user if incluir_usuario else None)
                if mensaje_todos: result['message'] = mensaje_todos
        with col2:
            with st.container(border=True):
                mensaje_tipo = _generar_pdf_por_tipo(df_merged, solo_pendientes, user if incluir_usuario else None)
                if mensaje_tipo: result['message'] = mensaje_tipo

        # --- Fila 2 ---
        col3, col4 = st.columns(2)
        with col3:
            with st.container(border=True):
                mensaje_manual = _generar_pdf_manual(df_merged, solo_pendientes, user if incluir_usuario else None)
                if mensaje_manual: result['message'] = mensaje_manual
        with col4:
            with st.container(border=True):
                mensaje_desconexiones = _generar_pdf_desconexiones(df_merged, user if incluir_usuario else None)
                if mensaje_desconexiones: result['message'] = mensaje_desconexiones

        # --- Fila 3 ---
        col5, col6 = st.columns(2)
        with col5:
            with st.container(border=True):
                mensaje_en_curso = _generar_pdf_en_curso_por_tecnico(df_merged, user if incluir_usuario else None)
                if mensaje_en_curso: result['message'] = mensaje_en_curso
        with col6:
            with st.container(border=True):
                st.markdown("### 📄 Generar Reporte Diario (PNG)")
                if st.button("🖼️ Generar imagen del día", use_container_width=True):
                    img_buffer = generar_reporte_diario_imagen(df_reclamos)
                    fecha_hoy = ahora_argentina().strftime("%Y-%m-%d")
                    st.download_button(
                        label="⬇️ Descargar Reporte Diario",
                        data=img_buffer,
                        file_name=f"reporte_diario_{fecha_hoy}.png",
                        mime="image/png",
                        use_container_width=True
                    )
    except Exception as e:
        st.error(f"❌ Error al generar PDF: {str(e)}")
        if DEBUG_MODE: st.exception(e)

    return result

def _preparar_datos(df_reclamos, df_clientes, user):
    """Prepara y combina los datos para impresión incluyendo info de usuario"""
    df_pdf = df_reclamos.copy()
    df_pdf["Fecha y hora"] = pd.to_datetime(df_pdf["Fecha y hora"], dayfirst=True, errors='coerce')
    df_pdf["Usuario_impresion"] = user.get('nombre', 'Sistema')
    return pd.merge(df_pdf, df_clientes[["Nº Cliente", "N° de Precinto"]].drop_duplicates(), on="Nº Cliente", how="left")

def _mostrar_reclamos_pendientes(df_merged):
    """Muestra tabla de reclamos pendientes con mejor formato"""
    with st.expander("🕒 Reclamos pendientes de resolución", expanded=True):
        df_pendientes = df_merged[df_merged["Estado"].astype(str).str.strip().str.lower() == "pendiente"]
        if not df_pendientes.empty:
            df_pendientes_display = df_pendientes.copy()
            df_pendientes_display["Fecha y hora"] = df_pendientes_display["Fecha y hora"].apply(lambda f: format_fecha(f, '%d/%m/%Y %H:%M') if pd.notna(f) else 'Sin fecha')
            st.dataframe(
                df_pendientes_display[["Fecha y hora", "Nº Cliente", "Nombre", "Dirección", "Sector", "Tipo de reclamo"]],
                use_container_width=True,
                column_config={
                    "Fecha y hora": st.column_config.TextColumn("Fecha y hora"),
                    "Nº Cliente": st.column_config.TextColumn("N° Cliente"),
                    "Sector": st.column_config.NumberColumn("Sector", format="%d")
                },
                height=300
            )
        else:
            st.success("✅ No hay reclamos pendientes actualmente.")

def _generar_pdf_todos_pendientes(df_merged, usuario=None):
    st.markdown("##### 📋 Imprimir TODOS los pendientes")
    orden = st.radio("Ordenar por:", ["Tipo de reclamo", "Sector"], horizontal=True, key="orden_todos_pendientes")
    df_pendientes = df_merged[df_merged["Estado"].astype(str).str.strip().str.lower() == "pendiente"]
    if df_pendientes.empty:
        st.info("✅ No hay reclamos pendientes.")
        return
    df_pendientes = df_pendientes.sort_values(by=orden)
    titulo = f"TODOS LOS RECLAMOS PENDIENTES (POR {orden.upper()})"
    
    if st.button("📄 Generar PDF", key="pdf_todos_pendientes", use_container_width=True):
        buffer = _crear_pdf_reclamos(df_pendientes, titulo, usuario)
        nombre_archivo = f"todos_pendientes_{datetime.now().strftime('%Y%m%d')}.pdf"
        st.download_button(label="⬇️ Descargar", data=buffer, file_name=nombre_archivo, mime="application/pdf", use_container_width=True)

def _generar_pdf_por_tipo(df_merged, solo_pendientes, usuario=None):
    st.markdown("##### 📋 Imprimir por tipo")
    tipos_disponibles = sorted(df_merged["Tipo de reclamo"].dropna().unique())
    tipos_seleccionados = st.multiselect("Seleccionar tipos", tipos_disponibles, default=tipos_disponibles[0] if tipos_disponibles else None)
    if not tipos_seleccionados: return

    df_filtrado = df_merged.copy()
    if solo_pendientes:
        df_filtrado = df_filtrado[df_filtrado["Estado"].str.strip().str.lower() == "pendiente"]
    reclamos_filtrados = df_filtrado[df_filtrado["Tipo de reclamo"].isin(tipos_seleccionados)]

    if reclamos_filtrados.empty:
        st.info("No hay reclamos para los tipos seleccionados.")
        return

    if st.button(f"📄 Generar PDF ({len(reclamos_filtrados)})", key="pdf_tipo", use_container_width=True):
        buffer = _crear_pdf_reclamos(reclamos_filtrados, f"RECLAMOS - {', '.join(tipos_seleccionados)}", usuario)
        nombre_archivo = f"reclamos_{'_'.join(t.lower().replace(' ', '_') for t in tipos_seleccionados)}.pdf"
        st.download_button(label="⬇️ Descargar", data=buffer, file_name=nombre_archivo, mime="application/pdf", use_container_width=True)

def _generar_pdf_manual(df_merged, solo_pendientes, usuario=None):
    st.markdown("##### 📋 Selección manual")
    df_filtrado = df_merged.copy()
    if solo_pendientes:
        df_filtrado = df_filtrado[df_filtrado["Estado"].astype(str).str.strip().str.lower() == "pendiente"]

    selected = st.multiselect("Seleccionar reclamos a imprimir:", df_filtrado.index, format_func=lambda x: f"{df_filtrado.at[x, 'Nº Cliente']} - {df_filtrado.at[x, 'Nombre']} ({df_filtrado.at[x, 'Tipo de reclamo']})")
    if not selected: return

    if st.button(f"📄 Generar PDF ({len(selected)})", key="pdf_manual", use_container_width=True):
        buffer = _crear_pdf_reclamos(df_filtrado.loc[selected], "RECLAMOS SELECCIONADOS", usuario)
        st.download_button(label="⬇️ Descargar", data=buffer, file_name="reclamos_seleccionados.pdf", mime="application/pdf", use_container_width=True)

def _generar_pdf_desconexiones(df_merged, usuario=None):
    st.markdown("##### 🔌 Imprimir Desconexiones")
    df_desconexiones = df_merged[(df_merged["Tipo de reclamo"].str.strip().str.lower() == "desconexion a pedido") & (df_merged["Estado"].str.strip().str.lower() == "desconexión")]
    if df_desconexiones.empty:
        st.info("No hay desconexiones para imprimir.")
        return
    
    if st.button(f"📄 Generar PDF ({len(df_desconexiones)})", key="pdf_desconexiones", use_container_width=True):
        buffer = _crear_pdf_reclamos(df_desconexiones, "LISTADO DE CLIENTES PARA DESCONEXIÓN", usuario)
        nombre_archivo = f"desconexiones_{datetime.now().strftime('%Y%m%d')}.pdf"
        st.download_button(label="⬇️ Descargar", data=buffer, file_name=nombre_archivo, mime="application/pdf", use_container_width=True)

def _generar_pdf_en_curso_por_tecnico(df_merged, usuario=None):
    st.markdown("##### 👷 Imprimir En Curso")
    df_en_curso = df_merged[df_merged["Estado"].astype(str).str.strip().str.lower() == "en curso"].copy()
    if df_en_curso.empty:
        st.info("No hay reclamos en curso.")
        return

    if st.button(f"📄 Generar PDF ({len(df_en_curso)})", key="pdf_en_curso_tecnico", use_container_width=True):
        # Lógica de agrupación por técnico omitida por brevedad en este ejemplo
        buffer = _crear_pdf_reclamos(df_en_curso, "RECLAMOS EN CURSO", usuario)
        st.download_button(label="⬇️ Descargar", data=buffer, file_name="reclamos_en_curso.pdf", mime="application/pdf", use_container_width=True)

def _crear_pdf_reclamos(df_reclamos, titulo, usuario=None):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 40
    hoy = datetime.now().strftime('%d/%m/%Y %H:%M')

    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, y, titulo)
    y -= 20
    c.setFont("Helvetica", 12)
    c.drawString(40, y, f"Generado el: {hoy}")
    if usuario: c.drawString(width - 200, y, f"Por: {usuario.get('nombre', 'Sistema')}")
    y -= 30

    for _, reclamo in df_reclamos.iterrows():
        if y < 120:
            agregar_pie_pdf(c, width, height)
            c.showPage()
            y = height - 40
            c.setFont("Helvetica-Bold", 16)
            c.drawString(40, y, titulo + " (cont.)")
            y -= 30

        c.setFont("Helvetica-Bold", 14)
        c.drawString(40, y, f"{reclamo['Nº Cliente']} - {reclamo['Nombre']}")
        y -= 15
        c.setFont("Helvetica", 11)
        fecha_pdf = reclamo['Fecha y hora'].strftime('%d/%m/%Y %H:%M') if pd.notna(reclamo['Fecha y hora']) else 'Sin fecha'
        lineas = [
            f"Fecha: {fecha_pdf}",
            f"Dirección: {reclamo['Dirección']} - Tel: {reclamo.get('Teléfono', 'N/A')}",
            f"Sector: {reclamo['Sector']} - Precinto: {reclamo.get('N° de Precinto', 'N/A')}",
            f"Tipo: {reclamo['Tipo de reclamo']}",
            f"Detalles: {reclamo['Detalles'][:100]}..." if len(reclamo['Detalles']) > 100 else f"Detalles: {reclamo['Detalles']}"
        ]
        for linea in lineas:
            c.drawString(40, y, linea)
            y -= 12
        y -= 5
        c.line(40, y, width - 40, y)
        y -= 15

    agregar_pie_pdf(c, width, height)
    c.save()
    buffer.seek(0)
    return buffer
