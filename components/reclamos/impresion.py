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
from config.settings import DEBUG_MODE


def render_impresion_reclamos(df_reclamos, df_clientes, user):
    """
    Muestra la sección para imprimir reclamos en formato PDF

    Args:
        df_reclamos (pd.DataFrame): DataFrame con los reclamos
        df_clientes (pd.DataFrame): DataFrame con los clientes
        user (dict): Información del usuario actual

    Returns:
        dict: {
            'needs_refresh': bool,  # Siempre False para este módulo
            'message': str,         # Mensaje sobre la operación realizada
            'data_updated': bool    # Siempre False para este módulo
        }
    """
    result = {
        'needs_refresh': False,
        'message': None,
        'data_updated': False
    }
    
    st.subheader("📨️ Seleccionar reclamos para imprimir (formato técnico compacto)")

    try:
        # Preparar datos con información del usuario
        df_merged = _preparar_datos(df_reclamos, df_clientes, user)

        # Mostrar reclamos pendientes
        _mostrar_reclamos_pendientes(df_merged)

        # Configuración de impresión
        with st.expander("⚙️ Configuración de impresión", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                solo_pendientes = st.checkbox(
                    "📜 Mostrar solo reclamos pendientes",
                    value=True
                )
            with col2:
                incluir_usuario = st.checkbox(
                    "👤 Incluir mi nombre en el PDF",
                    value=True
                )

        # === REORGANIZACIÓN EN GRID 2x3 ===
        st.markdown("### 🖨️ Opciones de Impresión")
        
        # Fila 1: Dos opciones
        col1, col2 = st.columns(2)
        
        with col1:
            mensaje_todos = _generar_pdf_todos_pendientes(df_merged, user if incluir_usuario else None)
            if mensaje_todos:
                result['message'] = mensaje_todos
        
        with col2:
            mensaje_tipo = _generar_pdf_por_tipo(df_merged, solo_pendientes, user if incluir_usuario else None)
            if mensaje_tipo:
                result['message'] = mensaje_tipo
        
        # Fila 2: Dos opciones
        col3, col4 = st.columns(2)
        
        with col3:
            mensaje_manual = _generar_pdf_manual(df_merged, solo_pendientes, user if incluir_usuario else None)
            if mensaje_manual:
                result['message'] = mensaje_manual
        
        with col4:
            mensaje_desconexiones = _generar_pdf_desconexiones(df_merged, user if incluir_usuario else None)
            if mensaje_desconexiones:
                result['message'] = mensaje_desconexiones
        
        # Fila 3: Dos opciones
        col5, col6 = st.columns(2)
        
        with col5:
            mensaje_en_curso = _generar_pdf_en_curso_por_tecnico(df_merged, user if incluir_usuario else None)
            if mensaje_en_curso:
                result['message'] = mensaje_en_curso
        
        with col6:
            # Nueva opción: Reporte Diario en el grid
            st.markdown("#### 📄 Reporte Diario")
            if st.button("🖼️ Generar imagen del día", use_container_width=True):
                img_buffer = generar_reporte_diario_imagen(df_reclamos)
                fecha_hoy = ahora_argentina().strftime("%Y-%m-%d")
                
                st.download_button(
                    label="⬇️ Descargar Reporte",
                    data=img_buffer,
                    file_name=f"reporte_diario_{fecha_hoy}.png",
                    mime="image/png",
                    use_container_width=True
                )

    except Exception as e:
        st.error(f"❌ Error al generar PDF: {str(e)}")
        result['message'] = f"Error al generar PDF: {str(e)}"
        if DEBUG_MODE:
            st.exception(e)
    finally:
        st.markdown('</div>', unsafe_allow_html=True)

    return result

def _preparar_datos(df_reclamos, df_clientes, user):
    """Prepara y combina los datos para impresión incluyendo info de usuario"""
    df_pdf = df_reclamos.copy()

    # Procesamiento de fechas
    df_pdf["Fecha y hora"] = pd.to_datetime(
        df_pdf["Fecha y hora"],
        dayfirst=True,
        errors='coerce'
    )

    # Agregar información del usuario a los datos
    df_pdf["Usuario_impresion"] = user.get('nombre', 'Sistema')

    # Merge con clientes (optimizado)
    return pd.merge(
        df_pdf,
        df_clientes[["Nº Cliente", "N° de Precinto"]].drop_duplicates(),
        on="Nº Cliente",
        how="left",
        suffixes=("", "_cliente")
    )

def _mostrar_reclamos_pendientes(df_merged):
    """Muestra tabla de reclamos pendientes con mejor formato"""
    with st.expander("🕒 Reclamos pendientes de resolución", expanded=True):
        df_pendientes = df_merged[
            df_merged["Estado"].astype(str).str.strip().str.lower() == "pendiente"
        ]

        if not df_pendientes.empty:
            # Formatear datos para visualización
            df_pendientes_display = df_pendientes.copy()
            df_pendientes_display["Fecha y hora"] = df_pendientes_display["Fecha y hora"].apply(
                lambda f: format_fecha(f, '%d/%m/%Y %H:%M') if not pd.isna(f) else 'Sin fecha'
            )

            # Mostrar tabla con configuración mejorada
            st.dataframe(
                df_pendientes_display[[
                    "Fecha y hora", "Nº Cliente", "Nombre",
                    "Dirección", "Sector", "Tipo de reclamo"
                ]],
                use_container_width=True,
                column_config={
                    "Fecha y hora": st.column_config.DatetimeColumn(
                        "Fecha y hora",
                        format="DD/MM/YYYY HH:mm"
                    ),
                    "Nº Cliente": st.column_config.TextColumn(
                        "N° Cliente",
                        help="Número de cliente"
                    ),
                    "Sector": st.column_config.NumberColumn(
                        "Sector",
                        format="%d"
                    )
                },
                height=400
            )
        else:
            st.success("✅ No hay reclamos pendientes actualmente.")

def _generar_pdf_todos_pendientes(df_merged, usuario=None):
    """Genera PDF con todos los reclamos pendientes, ordenados por tipo o sector"""
    st.markdown("#### 📋 Todos los pendientes")
    
    # Filtrar solo pendientes
    df_pendientes = df_merged[
        df_merged["Estado"].astype(str).str.strip().str.lower() == "pendiente"
    ]

    if df_pendientes.empty:
        st.info("✅ No hay reclamos pendientes.")
        return None

    # Opciones de ordenamiento
    orden = st.radio(
        "Ordenar por:",
        ["Tipo", "Sector"],
        horizontal=True,
        key="orden_todos_pendientes"
    )

    # Ordenar según selección
    if orden == "Tipo":
        df_pendientes = df_pendientes.sort_values("Tipo de reclamo")
        titulo = "TODOS LOS RECLAMOS PENDIENTES (ORDENADOS POR TIPO)"
    else:
        df_pendientes = df_pendientes.sort_values("Sector")
        titulo = "TODOS LOS RECLAMOS PENDIENTES (ORDENADOS POR SECTOR)"

    st.info(f"📋 {len(df_pendientes)} reclamos pendientes")

    if st.button("📄 Generar PDF", key="pdf_todos_pendientes", use_container_width=True):
        buffer = _crear_pdf_reclamos(
            df_pendientes,
            titulo,
            usuario
        )

        nombre_archivo = f"todos_reclamos_pendientes_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"

        st.download_button(
            label="⬇️ Descargar PDF",
            data=buffer,
            file_name=nombre_archivo,
            mime="application/pdf",
            use_container_width=True,
            help=f"Descargar {len(df_pendientes)} reclamos pendientes"
        )

        return f"PDF generado con {len(df_pendientes)} reclamos pendientes (ordenados por {orden.lower()})"
    
    return None

def _generar_pdf_por_tipo(df_merged, solo_pendientes, usuario=None):
    """Genera PDF filtrado por tipos de reclamo"""
    st.markdown("#### 📋 Por tipo de reclamo")

    tipos_disponibles = sorted(df_merged["Tipo de reclamo"].dropna().unique())
    tipos_seleccionados = st.multiselect(
        "Seleccionar tipos:",
        tipos_disponibles,
        default=tipos_disponibles[0] if tipos_disponibles else None,
        key="select_tipos_pdf"
    )

    if not tipos_seleccionados:
        return None

    # Aplicar filtros
    df_filtrado = df_merged.copy()
    if solo_pendientes:
        df_filtrado = df_filtrado[
            df_filtrado["Estado"].str.strip().str.lower() == "pendiente"
        ]

    reclamos_filtrados = df_filtrado[
        df_filtrado["Tipo de reclamo"].isin(tipos_seleccionados)
    ]

    if reclamos_filtrados.empty:
        st.info("No hay reclamos para los tipos seleccionados.")
        return None

    st.info(f"📋 {len(reclamos_filtrados)} reclamos encontrados")

    if st.button("📄 Generar PDF", key="pdf_tipo", use_container_width=True):
        buffer = _crear_pdf_reclamos(
            reclamos_filtrados,
            f"RECLAMOS - {', '.join(tipos_seleccionados)}",
            usuario
        )

        nombre_archivo = f"reclamos_{'_'.join(t.lower().replace(' ', '_') for t in tipos_seleccionados)}.pdf"

        st.download_button(
            label="⬇️ Descargar PDF",
            data=buffer,
            file_name=nombre_archivo,
            mime="application/pdf",
            use_container_width=True,
            help=f"Descargar {len(reclamos_filtrados)} reclamos"
        )

        return f"PDF generado con {len(reclamos_filtrados)} reclamos de tipo {', '.join(tipos_seleccionados)}"

    return None

def _generar_pdf_manual(df_merged, solo_pendientes, usuario=None):
    """Genera PDF con selección manual de reclamos"""
    st.markdown("#### 📋 Selección manual")

    df_filtrado = df_merged.copy()
    if solo_pendientes:
        df_filtrado = df_filtrado[
            df_filtrado["Estado"].astype(str).str.strip().str.lower() == "pendiente"
        ]

    # Selector mejorado con más información
    selected = st.multiselect(
        "Seleccionar reclamos:",
        df_filtrado.index,
        format_func=lambda x: (
            f"{df_filtrado.at[x, 'Nº Cliente']} - "
            f"{df_filtrado.at[x, 'Nombre']} - "
            f"Sector {df_filtrado.at[x, 'Sector']} - "
            f"{df_filtrado.at[x, 'Tipo de reclamo']}"
        ),
        key="multiselect_reclamos"
    )

    if not selected:
        st.info("ℹ️ Seleccionar al menos un reclamo")
        return None

    st.info(f"📋 {len(selected)} reclamos seleccionados")

    if st.button("📄 Generar PDF", key="pdf_manual", use_container_width=True):
        buffer = _crear_pdf_reclamos(
            df_filtrado.loc[selected],
            f"RECLAMOS SELECCIONADOS",
            usuario
        )

        st.download_button(
            label="⬇️ Descargar PDF",
            data=buffer,
            file_name="reclamos_seleccionados.pdf",
            mime="application/pdf",
            use_container_width=True,
            help=f"Descargar {len(selected)} reclamos seleccionados"
        )

        return f"PDF generado con {len(selected)} reclamos seleccionados"
    
    return None

def _generar_pdf_desconexiones(df_merged, usuario=None):
    """Genera un PDF con desconexiones a pedido (estado = desconexión)"""
    st.markdown("#### 🔌 Desconexiones a pedido")

    df_desconexiones = df_merged[
        (df_merged["Tipo de reclamo"].str.strip().str.lower() == "desconexion a pedido") &
        (df_merged["Estado"].str.strip().str.lower() == "desconexión")
    ]

    if df_desconexiones.empty:
        st.info("✅ No hay desconexiones pendientes")
        return None

    st.info(f"📋 {len(df_desconexiones)} desconexiones encontradas")

    if st.button("📄 Generar PDF", key="pdf_desconexiones", use_container_width=True):
        buffer = _crear_pdf_reclamos(
            df_desconexiones,
            "LISTADO DE CLIENTES PARA DESCONEXIÓN",
            usuario
        )
        nombre_archivo = f"desconexiones_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"

        st.download_button(
            label="⬇️ Descargar PDF",
            data=buffer,
            file_name=nombre_archivo,
            mime="application/pdf",
            use_container_width=True,
            help=f"Descargar {len(df_desconexiones)} desconexiones"
        )

        return f"PDF generado con {len(df_desconexiones)} desconexiones pendientes"

    return None

def _generar_pdf_en_curso_por_tecnico(df_merged, usuario=None):
    """Genera un PDF con reclamos en curso agrupados por técnico"""
    st.markdown("#### 👷 En curso por técnico")

    df_en_curso = df_merged[
        df_merged["Estado"].astype(str).str.strip().str.lower() == "en curso"
    ].copy()

    if df_en_curso.empty:
        st.info("✅ No hay reclamos en curso")
        return None

    st.info(f"📋 {len(df_en_curso)} reclamos en curso")

    if st.button("📄 Generar PDF", key="pdf_en_curso_tecnico", use_container_width=True):
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        import io

        df_en_curso["Técnico"] = df_en_curso["Técnico"].fillna("Sin técnico").str.upper()
        reclamos_por_tecnico = df_en_curso.groupby("Técnico")

        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        y = height - 40
        hoy = datetime.now().strftime('%d/%m/%Y')

        c.setFont("Helvetica-Bold", 16)
        c.drawString(40, y, f"RECLAMOS EN CURSO - {hoy}")
        if usuario:
            c.setFont("Helvetica", 10)
            c.drawString(width - 200, y, f"Por: {usuario.get('nombre', 'Sistema')}")
        y -= 30

        for tecnico, reclamos in reclamos_por_tecnico:
            if y < 100:
                agregar_pie_pdf(c, width, height)
                c.showPage()
                y = height - 40
                c.setFont("Helvetica-Bold", 16)
                c.drawString(40, y, f"RECLAMOS EN CURSO - {hoy}")
                y -= 30

            c.setFont("Helvetica-Bold", 13)
            c.drawString(40, y, f"👷 Técnico: {tecnico} ({len(reclamos)})")
            y -= 20

            c.setFont("Helvetica", 11)
            for _, row in reclamos.iterrows():
                texto = f"{row['Nº Cliente']} - {row['Tipo de reclamo']} - Sector {row['Sector']}"
                c.drawString(50, y, texto)
                y -= 15
                if y < 60:
                    agregar_pie_pdf(c, width, height)
                    c.showPage()
                    y = height - 40

            # Línea divisoria después de los reclamos de cada técnico
            c.setFont("Helvetica", 10)
            c.drawString(40, y, "-" * 80)
            y -= 20

        agregar_pie_pdf(c, width, height)
        c.save()
        buffer.seek(0)

        st.download_button(
            label="⬇️ Descargar PDF",
            data=buffer,
            file_name=f"reclamos_en_curso_tecnicos_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf",
            use_container_width=True,
            help="Reclamos agrupados por técnico"
        )

        return "PDF generado con reclamos en curso por técnico"

    return None

# ==============================
# Utilidad central para crear PDF
# ==============================
def _crear_pdf_reclamos(df, titulo, usuario=None):
    """Crea un PDF compacto con filas del DataFrame `df`.

    Columnas esperadas en `df` (no estrictas, se ignoran si faltan):
    - "Fecha y hora" (datetime o str)
    - "Nº Cliente"
    - "Nombre"
    - "Dirección"
    - "Sector"
    - "Tipo de reclamo"
    - "Detalles"
    - "Técnico"
    - "N° de Precinto"
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Márgenes y medidas
    margen_izq = 40
    margen_der = 40
    y = height - 40

    hoy = ahora_argentina().strftime('%d/%m/%Y')

    def iniciar_pagina():
        nonlocal y
        c.setFont("Helvetica-Bold", 15)
        c.drawString(margen_izq, y, titulo)
        c.setFont("Helvetica", 10)
        c.drawString(width - 150, y, f"Fecha: {hoy}")
        if usuario:
            c.drawString(width - 150, y - 12, f"Por: {usuario.get('nombre', 'Sistema')}")
        y -= 28

        # Encabezados de columnas
        c.setFont("Helvetica-Bold", 10)
        c.drawString(margen_izq, y, "Cliente")
        c.drawString(margen_izq + 90, y, "Nombre")
        c.drawString(margen_izq + 260, y, "Dirección")
        c.drawString(margen_izq + 430, y, "Sector")
        c.drawString(margen_izq + 480, y, "Tipo")
        y -= 14
        c.setFont("Helvetica", 10)

    def salto_pagina_si_necesario(min_y=60):
        nonlocal y
        if y < min_y:
            agregar_pie_pdf(c, width, height)
            c.showPage()
            y = height - 40
            iniciar_pagina()

    iniciar_pagina()

    # Normalizar columnas existentes
    columnas = df.columns

    for _, row in df.iterrows():
        salto_pagina_si_necesario()

        # Fecha formateada si existe
        fecha_val = row.get("Fecha y hora") if "Fecha y hora" in columnas else None
        try:
            if pd.notna(fecha_val):
                if not isinstance(fecha_val, pd.Timestamp):
                    fecha_val = pd.to_datetime(fecha_val, dayfirst=True, errors='coerce')
        except Exception:
            fecha_val = None
        fecha_txt = format_fecha(fecha_val, '%d/%m %H:%M') if pd.notna(fecha_val) else ""

        num_cliente = str(row.get("Nº Cliente", "")).strip()
        nombre = str(row.get("Nombre", "")).strip()
        direccion = str(row.get("Dirección", "")).strip()
        sector = str(row.get("Sector", "")).strip()
        tipo = str(row.get("Tipo de reclamo", "")).strip()
        detalles = str(row.get("Detalles", "")).strip()
        tecnico = str(row.get("Técnico", "")).strip()
        precinto = str(row.get("N° de Precinto", row.get("N° de Precinto", ""))).strip()

        # Línea principal compacta
        linea_cliente = f"{fecha_txt} {num_cliente}"
        c.drawString(margen_izq, y, linea_cliente[:18])
        c.drawString(margen_izq + 90, y, nombre[:22])
        c.drawString(margen_izq + 260, y, direccion[:28])
        c.drawString(margen_izq + 430, y, sector[:6])
        c.drawString(margen_izq + 480, y, tipo[:18])
        y -= 12

        # Segunda línea con más info si hay
        extra = []
        if detalles:
            extra.append(detalles)
        if tecnico:
            extra.append(f"Tec: {tecnico}")
        if precinto:
            extra.append(f"Prec: {precinto}")
        if extra:
            salto_pagina_si_necesario()
            c.setFont("Helvetica", 9)
            c.drawString(margen_izq + 20, y, " | ".join(extra)[:95])
            c.setFont("Helvetica", 10)
            y -= 10

        # Separador suave
        c.setFont("Helvetica", 8)
        c.drawString(margen_izq, y, "-" * 105)
        c.setFont("Helvetica", 10)
        y -= 8

    agregar_pie_pdf(c, width, height)
    c.save()
    buffer.seek(0)
    return buffer
