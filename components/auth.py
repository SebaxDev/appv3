"""
Componente de autenticación profesional estilo CRM
Versión mejorada con diseño elegante
"""
"""
Componente de autenticación profesional estilo CRM
Versión mejorada con diseño elegante
"""
import streamlit as st
from utils.data_manager import safe_get_sheet_data
from config.settings import (
    WORKSHEET_USUARIOS,
    COLUMNAS_USUARIOS,
    PERMISOS_POR_ROL
)
import time
from utils.styles import get_loading_spinner
from passlib.context import CryptContext

# Configura el contexto de hasheo de contraseñas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def init_auth_session():
    """Inicializa las variables de sesión"""
    if 'auth' not in st.session_state:
        st.session_state.auth = {
            'logged_in': False,
            'user_info': None
        }

def logout():
    """Cierra la sesión del usuario"""
    st.session_state.auth = {'logged_in': False, 'user_info': None}
    st.cache_data.clear()  # Limpiar caché de datos

def verify_credentials(username, password, sheet_usuarios):
    """Verifica las credenciales del usuario usando password en texto plano (Google Sheets)."""
    try:
        df_usuarios = safe_get_sheet_data(sheet_usuarios, COLUMNAS_USUARIOS)

        # Normalización de datos
        df_usuarios["username"] = df_usuarios["username"].astype(str).str.strip().str.lower()
        df_usuarios["password"] = df_usuarios["password"].astype(str).str.strip()
        df_usuarios["rol"] = df_usuarios["rol"].astype(str).str.strip().str.lower()
        df_usuarios["nombre"] = df_usuarios["nombre"].astype(str).str.strip()

        # Manejo flexible de campo 'activo'
        df_usuarios["activo"] = df_usuarios["activo"].astype(str).str.upper().isin(
            ["SI", "TRUE", "1", "SÍ", "VERDADERO"]
        )

        # Buscar el usuario válido
        usuario = df_usuarios[
            (df_usuarios["username"] == username.strip().lower()) &
            (df_usuarios["password"] == password.strip()) &
            (df_usuarios["activo"])
        ]

        if not usuario.empty:
            u = usuario.iloc[0]
            return {
                "username": u["username"],
                "nombre": u["nombre"],
                "rol": u["rol"],
                "modo_oscuro": u.get("modo_oscuro", "FALSE"),
                "permisos": PERMISOS_POR_ROL.get(u["rol"], {}).get("permisos", [])
            }
    except Exception as e:
        st.error(f"Error en autenticación: {str(e)}")
    return None

def render_login(sheet_usuarios):
    """Formulario de login con diseño profesional CRM optimizado para una sola pantalla"""
    
    # CSS personalizado optimizado siguiendo las pautas de styles.py
    login_styles = """
    <style>
    /* Ocultar elementos de Streamlit para diseño limpio */
    .stApp > header { visibility: hidden; }
    .stApp > div:first-child { visibility: hidden; }
    
    /* Contenedor principal optimizado para una sola pantalla */
    .login-container {
        max-width: 420px;
        margin: 0 auto;
        padding: 2rem;
        background: var(--bg-card);
        border-radius: var(--radius-xl);
        border: 1px solid var(--border-color);
        box-shadow: var(--shadow-lg);
        text-align: center;
        position: relative;
        top: 50%;
        transform: translateY(-50%);
        min-height: 500px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    
    /* Header compacto */
    .login-header {
        margin-bottom: 1.5rem;
    }
    
    .login-logo {
        font-size: 2.5rem;
        margin-bottom: 0.5rem;
        background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 50%, var(--info-color) 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        filter: drop-shadow(0 2px 4px rgba(0,0,0,0.1));
    }
    
    .login-title {
        font-size: 1.5rem;
        font-weight: 700;
        margin-bottom: 0.25rem;
        color: var(--text-primary);
        letter-spacing: -0.025em;
    }
    
    .login-subtitle {
        color: var(--text-secondary);
        margin-bottom: 1.5rem;
        font-size: 0.9rem;
        font-weight: 400;
    }
    
    /* Formulario compacto */
    .login-form {
        text-align: left;
        margin-bottom: 1rem;
    }
    
    .login-input {
        margin-bottom: 1rem;
    }
    
    .login-input .stTextInput > div > div > input {
        background-color: var(--bg-surface);
        border: 1px solid var(--border-color);
        border-radius: var(--radius-md);
        padding: 0.75rem;
        color: var(--text-primary);
        font-size: 0.9rem;
        transition: all 0.2s ease;
        height: 44px;
    }
    
    .login-input .stTextInput > div > div > input:focus {
        border-color: var(--primary-color);
        box-shadow: 0 0 0 3px rgba(102, 217, 239, 0.2);
        outline: none;
    }
    
    .login-input .stTextInput > div > div > input::placeholder {
        color: var(--text-muted);
    }
    
    /* Botón optimizado */
    .login-button {
        width: 100%;
        margin-top: 0.5rem;
        padding: 0.875rem;
        font-size: 0.95rem;
        font-weight: 600;
        background: linear-gradient(135deg, var(--primary-color) 0%, var(--primary-light) 100%);
        color: var(--bg-primary);
        border: none;
        border-radius: var(--radius-lg);
        transition: all 0.3s ease;
        cursor: pointer;
        box-shadow: var(--shadow-md);
    }
    
    .login-button:hover {
        background: linear-gradient(135deg, var(--primary-light) 0%, var(--primary-color) 100%);
        transform: translateY(-2px);
        box-shadow: var(--shadow-lg);
    }
    
    /* Footer compacto */
    .login-footer {
        margin-top: 1rem;
        padding-top: 1rem;
        border-top: 1px solid var(--border-light);
        color: var(--text-muted);
        font-size: 0.8rem;
        line-height: 1.4;
    }
    
    /* Mensajes de estado mejorados */
    .login-error {
        background: rgba(255, 97, 136, 0.1);
        border: 1px solid rgba(255, 97, 136, 0.3);
        color: var(--danger-color);
        padding: 0.75rem;
        border-radius: var(--radius-md);
        margin: 0.75rem 0;
        text-align: center;
        font-size: 0.85rem;
        font-weight: 500;
    }
    
    .login-success {
        background: rgba(166, 226, 46, 0.1);
        border: 1px solid rgba(166, 226, 46, 0.3);
        color: var(--success-color);
        padding: 0.75rem;
        border-radius: var(--radius-md);
        margin: 0.75rem 0;
        text-align: center;
        font-size: 0.85rem;
        font-weight: 500;
    }
    
    /* Iconos de input mejorados */
    .input-icon {
        font-size: 1.25rem;
        padding-top: 0.75rem;
        color: var(--text-muted);
        transition: color 0.2s ease;
    }
    
    .input-icon:hover {
        color: var(--primary-color);
    }
    
    /* Responsive design para pantallas pequeñas */
    @media (max-height: 700px) {
        .login-container {
            transform: none;
            top: 0;
            margin: 1rem auto;
            min-height: auto;
            padding: 1.5rem;
        }
        
        .login-logo {
            font-size: 2rem;
        }
        
        .login-title {
            font-size: 1.25rem;
        }
        
        .login-subtitle {
            margin-bottom: 1rem;
        }
    }
    
    @media (max-width: 480px) {
        .login-container {
            margin: 0.5rem;
            padding: 1.25rem;
            max-width: none;
        }
        
        .login-logo {
            font-size: 1.75rem;
        }
        
        .login-title {
            font-size: 1.1rem;
        }
        
        .login-subtitle {
            font-size: 0.85rem;
        }
    }
    
    /* Mejoras para tablets */
    @media (min-width: 768px) and (max-width: 1024px) {
        .login-container {
            max-width: 450px;
            padding: 2.5rem;
        }
    }
    
    /* Mejoras para pantallas muy grandes */
    @media (min-width: 1400px) {
        .login-container {
            max-width: 480px;
            padding: 3rem;
        }
        
        .login-logo {
            font-size: 3rem;
        }
        
        .login-title {
            font-size: 1.75rem;
        }
    }
    
    /* Animación de entrada suave */
    .login-container {
        animation: slideInUp 0.6s ease-out;
    }
    
    @keyframes slideInUp {
        from {
            opacity: 0;
            transform: translateY(30px);
        }
        to {
            opacity: 1;
            transform: translateY(-50%);
        }
    }
    
    @media (max-height: 700px) {
        @keyframes slideInUp {
            from {
                opacity: 0;
                transform: translateY(30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
    }
    </style>
    """
    
    st.markdown(login_styles, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="login-container">
        <div class="login-header">
            <div class="login-logo">⚡</div>
            <h1 class="login-title">Fusion Reclamos</h1>
            <p class="login-subtitle">Sistema de gestión profesional</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Inicializar estado de carga
    if 'login_loading' not in st.session_state:
        st.session_state.login_loading = False
    if 'login_attempt' not in st.session_state:
        st.session_state.login_attempt = False
    if 'login_username' not in st.session_state:
        st.session_state.login_username = ""
    if 'login_password' not in st.session_state:
        st.session_state.login_password = ""
    
    # Mostrar spinner si está cargando
    if st.session_state.login_loading:
        st.markdown(get_loading_spinner(), unsafe_allow_html=True)
        st.markdown("""
        <div style="text-align: center; margin-top: 20px;">
            <p style="color: var(--text-secondary);">Verificando credenciales...</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Procesar la autenticación
        try:
            user_info = verify_credentials(
                st.session_state.login_username, 
                st.session_state.login_password, 
                sheet_usuarios
            )
            
            if user_info:
                st.session_state.auth = {
                    'logged_in': True,
                    'user_info': user_info
                }
                st.session_state.login_loading = False
                st.session_state.login_attempt = False
                st.rerun()
            else:
                st.session_state.login_loading = False
                st.session_state.login_attempt = True
                st.rerun()
                
        except Exception as e:
            st.session_state.login_loading = False
            st.session_state.login_attempt = True
            st.error(f"Error en autenticación: {str(e)}")
            st.rerun()
    
    else:
        # Mostrar mensaje de error si hubo un intento fallido
        if st.session_state.login_attempt:
            st.error("❌ Credenciales incorrectas o usuario inactivo")
            st.session_state.login_attempt = False
        
        # Formulario de login compacto
        with st.form("login_formulario"):
            st.markdown('<div class="login-form">', unsafe_allow_html=True)
            
            # Campo de usuario con icono optimizado
            col1, col2 = st.columns([1, 8])
            with col1:
                st.markdown('<div class="input-icon">👤</div>', unsafe_allow_html=True)
            with col2:
                username = st.text_input("Usuario", placeholder="Usuario", 
                                       value=st.session_state.login_username,
                                       label_visibility="collapsed",
                                       key="username_input").strip()
            
            # Campo de contraseña con icono optimizado
            col1, col2 = st.columns([1, 8])
            with col1:
                st.markdown('<div class="input-icon">🔒</div>', unsafe_allow_html=True)
            with col2:
                password = st.text_input("Contraseña", type="password", 
                                       placeholder="Contraseña", 
                                       value=st.session_state.login_password,
                                       label_visibility="collapsed",
                                       key="password_input")
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Botón de login con estilo personalizado
            if st.form_submit_button("🚀 Ingresar", use_container_width=True, key="login_btn"):
                if not username or not password:
                    st.error("⚠️ Usuario y contraseña son requeridos")
                else:
                    # Guardar credenciales y activar loading
                    st.session_state.login_username = username
                    st.session_state.login_password = password
                    st.session_state.login_loading = True
                    st.rerun()
    
    st.markdown("""
        <div class="login-footer">
            <p>© 2025 Fusion Reclamos • v3.0</p>
            <p>Sistema optimizado para gestión eficiente</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Procesar login después del render
    if st.session_state.login_loading:
        time.sleep(0.5)  # Pequeña pausa para el efecto visual
        user_info = verify_credentials(username, password, sheet_usuarios)
        
        if user_info:
            st.session_state.auth = {
                'logged_in': True,
                'user_info': user_info
            }
            st.session_state.login_loading = False
            st.success(f"✅ Bienvenido, {user_info['nombre']}!")
            time.sleep(1)
            st.rerun()
        else:
            st.session_state.login_loading = False
            st.error("❌ Credenciales incorrectas o usuario inactivo")
            time.sleep(2)
            st.rerun()

def check_authentication():
    """Verifica si el usuario está autenticado"""
    init_auth_session()
    return st.session_state.auth['logged_in']

def has_permission(required_permission):
    """Verifica permisos del usuario"""
    if not check_authentication():
        return False
        
    user_info = st.session_state.auth.get('user_info')
    if not user_info:
        return False
        
    # Admin tiene acceso completo
    if user_info['rol'] == 'admin':
        return True
        
    return required_permission in user_info.get('permisos', [])

def render_user_info():
    """Versión mejorada con iconos y estilo siguiendo las pautas de styles.py"""
    if not check_authentication():
        return
        
    user_info = st.session_state.auth['user_info']
    role_config = {
        'admin': {'icon': '👑', 'color': 'var(--danger-color)', 'badge': 'Administrador'},
        'oficina': {'icon': '💼', 'color': 'var(--info-color)', 'badge': 'Oficina'},
        'tecnico': {'icon': '🔧', 'color': 'var(--success-color)', 'badge': 'Técnico'},
        'supervisor': {'icon': '👔', 'color': 'var(--secondary-color)', 'badge': 'Supervisor'}
    }
    
    config = role_config.get(user_info['rol'].lower(), {'icon': '👤', 'color': 'var(--text-muted)', 'badge': 'Usuario'})
    
    with st.sidebar:
        st.markdown("---")
        st.markdown(f"""
        <div style="text-align: center; margin-bottom: 1.5rem; padding: 1rem; background: var(--bg-card); border-radius: var(--radius-lg); border: 1px solid var(--border-color);">
            <div style="font-size: 2.5rem; margin-bottom: 0.75rem; background: linear-gradient(135deg, {config['color']}, var(--primary-color)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; filter: drop-shadow(0 2px 4px rgba(0,0,0,0.1));">
                {config['icon']}
            </div>
            <h3 style="margin: 0; color: var(--text-primary); font-weight: 600; font-size: 1.1rem; margin-bottom: 0.5rem;">{user_info['nombre']}</h3>
            <div style="background: rgba(102, 217, 239, 0.15); 
                      color: var(--primary-color); 
                      padding: 0.25rem 0.75rem; 
                      border-radius: var(--radius-xl); 
                      font-size: 0.75rem; 
                      font-weight: 600;
                      margin: 0.5rem 0;
                      display: inline-block;
                      border: 1px solid rgba(102, 217, 239, 0.3);">
                {config['badge']}
            </div>
            <p style="color: var(--text-secondary); margin: 0.25rem 0; font-size: 0.8rem; font-weight: 500;">
                @{user_info['username']}
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("🚪 Cerrar sesión", use_container_width=True, key="logout_btn"):
            logout()
            st.rerun()
        st.markdown("---")