# VRP - Registros.py
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import time as t
from zoneinfo import ZoneInfo
import base64
import datetime

# Configuración de página
st.set_page_config(layout="wide", page_title="Gestion VRP's - MIAA", page_icon="https://www.miaa.mx/favicon.ico")

# --- ESTADO DE SESIÓN ---
if 'registro_to_delete' not in st.session_state: st.session_state.registro_to_delete = None
if 'active_tab' not in st.session_state: st.session_state.active_tab = "📍 Registros"
if 'autenticado' not in st.session_state: st.session_state.autenticado = False

zona_mx = ZoneInfo("America/Mexico_City")

OPCIONES_ESTADO_VALVULA = [
    "Abierta",
    "Calibrada",
    "Cerrada",
    "Dañada",
    "Descalibrada",
    "Habilitada",
    "No opera",
    "Pendiente"
]

# --- CONEXIÓN A BASE DE DATOS POSTGRESQL (VPRS) ---
def crear_nuevo_engine():
    pg = st.secrets["postgres"]
    db_url = f"postgresql+psycopg2://{pg['user']}:{pg['password']}@{pg['host']}:{pg['port']}/{pg['database']}"
    return create_engine(
        db_url,
        pool_pre_ping=True, 
        pool_recycle=1800, 
        pool_timeout=60,
        connect_args={'connect_timeout': 60}
    )

if 'db_engine' not in st.session_state:
    st.session_state.db_engine = crear_nuevo_engine()

def obtener_datos(query, params=None):
    for intento in range(2):
        try:
            with st.session_state.db_engine.connect() as conn:
                df = pd.read_sql(text(query) if isinstance(query, str) else query, conn, params=params or {})
                return df, None
        except Exception:
            try:
                st.session_state.db_engine.dispose()
                st.session_state.db_engine = crear_nuevo_engine()
                with st.session_state.db_engine.connect() as conn:
                    df = pd.read_sql(text(query) if isinstance(query, str) else query, conn, params=params or {})
                    return df, None
            except Exception as e2:
                if intento == 1:
                    return pd.DataFrame(), str(e2)
    return pd.DataFrame(), "Error de conexión persistente."

def ejecutar_sql(query, params=None):
    with st.session_state.db_engine.connect() as conn:
        with conn.begin():
            conn.execute(text(query) if isinstance(query, str) else query, params or {})
    return True

# --- CONEXIÓN A MYSQL (USUARIOS / LOGIN) ---
def crear_engine_mysql():
    mysql_sec = st.secrets["mysql_usuarios_vrp"]
    db_url = f"mysql+pymysql://{mysql_sec['user']}:{mysql_sec['password']}@{mysql_sec['host']}:{mysql_sec['port']}/{mysql_sec['database']}"
    return create_engine(
        db_url,
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_timeout=60,
        connect_args={'connect_timeout': 60}
    )

if 'db_mysql_engine' not in st.session_state:
    st.session_state.db_mysql_engine = crear_engine_mysql()

def obtener_datos_mysql(query, params=None):
    for intento in range(2):
        try:
            with st.session_state.db_mysql_engine.connect() as conn:
                df = pd.read_sql(text(query) if isinstance(query, str) else query, conn, params=params or {})
                return df, None
        except Exception:
            try:
                st.session_state.db_mysql_engine.dispose()
                st.session_state.db_mysql_engine = crear_engine_mysql()
                with st.session_state.db_mysql_engine.connect() as conn:
                    df = pd.read_sql(text(query) if isinstance(query, str) else query, conn, params=params or {})
                    return df, None
            except Exception as e2:
                if intento == 1:
                    return pd.DataFrame(), str(e2)
    return pd.DataFrame(), "Error de conexión persistente a MySQL."

def procesar_bytes_foto(foto_data):
    if foto_data is None:
        return None
    if isinstance(foto_data, memoryview):
        return bytes(foto_data)
    if isinstance(foto_data, bytes):
        return foto_data
    if isinstance(foto_data, str) and len(foto_data) > 10:
        try:
            return base64.b64decode(foto_data)
        except:
            return None
    return None

def parsear_fecha_segura(val_fecha):
    if pd.isna(val_fecha) or val_fecha is None or str(val_fecha).strip() in ["", "nan", "None"]:
        return datetime.date.today()
    if isinstance(val_fecha, (datetime.date, datetime.datetime)):
        return val_fecha if isinstance(val_fecha, datetime.date) else val_fecha.date()
    try:
        return pd.to_datetime(val_fecha).date()
    except Exception:
        return datetime.date.today()

# --- ESTILOS CSS CON ANCHO TOTAL Y CORRECCIÓN DE POSICIONAMIENTO EN CÁMARA ---
st.write("""<style>
    /* Ocultar únicamente la cabecera nativa de Streamlit sin afectar los headers del calendario BaseWeb */
    #MainMenu, [data-testid="stHeader"] {visibility: hidden !important; display: none !important;} 
    
    /* REGLA CRÍTICA: Forzar visibilidad del header de mes y año en el calendario */
    div[data-baseweb="calendar"] header,
    div[data-baseweb="popover"] header {
        display: flex !important;
        visibility: visible !important;
        opacity: 1 !important;
        background-color: #0D1424 !important;
        color: #00E5FF !important;
    }
    div[data-baseweb="calendar"] header button,
    div[data-baseweb="calendar"] header div,
    div[data-baseweb="calendar"] header svg {
        color: #00E5FF !important;
        fill: #00E5FF !important;
    }

    .block-container {
        padding-top: 0rem !important; 
        padding-bottom: 2.5rem !important;
        padding-left: 0rem !important;
        padding-right: 0rem !important;
        background: #080C14;
        color: #F8FAFC;
        max-width: 100% !important;
        overflow-x: hidden;
    }
    body, [data-testid="stAppViewContainer"] {
        background: #080C14;
        color: #F8FAFC;
        overflow-x: hidden;
    }
    
    /* REJILLA EXPANDIDA Y FORZADA A BORDE A BORDE */
    .miaa-grid-container {
        display: grid;
        grid-template-columns: repeat(2, 1fr) !important;
        gap: 1px !important;
        width: 100% !important;
        box-sizing: border-box !important;
        margin-bottom: 3px !important;
        padding: 0 !important;
    }

    /* Anular restricciones y paddings de Streamlit en bloques horizontales */
    [data-testid="stHorizontalBlock"] {
        display: grid !important;
        grid-template-columns: repeat(2, 1fr) !important;
        gap: 1px !important;
        width: 100% !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    [data-testid="column"] {
        width: 100% !important;
        flex: unset !important;
        min-width: unset !important;
        max-width: 100% !important;
        padding: 0 2px !important;
        margin: 0 !important;
    }

    /* Tarjetas de registros con ancho total absoluto */
    .user-card {
        background: #0D1424;
        border: 1px solid rgba(0, 229, 255, 0.12);
        border-left: 3px solid #00E5FF;
        border-radius: 2px;
        padding: 6px 4px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
        word-break: break-word;
        box-sizing: border-box;
        width: 100% !important;
        height: 100% !important;
    }

    /* Menú de navegación / Pestañas estilo tarjeta MIAA */
    div.row-widget.stRadio > div {
        display: flex;
        flex-direction: row;
        justify-content: center;
        background: #0D1424;
        border: 1px solid rgba(0, 229, 255, 0.12);
        border-radius: 8px;
        padding: 3px;
        gap: 3px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
    }
    div.row-widget.stRadio > div > label {
        background: #111A30;
        border: 1px solid rgba(0, 229, 255, 0.15) !important;
        border-radius: 6px !important;
        padding: 6px 2px !important;
        flex: 1;
        text-align: center;
        cursor: pointer;
        transition: all 0.2s ease-in-out;
    }
    div.row-widget.stRadio input[type="radio"] { display: none !important; }
    div.row-widget.stRadio div[role="radiogroup"] > label > div:first-child { display: none !important; }
    div.row-widget.stRadio div[role="radiogroup"] label span,
    div.row-widget.stRadio div[role="radiogroup"] label p {
        color: #94A3B8 !important;
        font-weight: 600 !important;
        font-size: 0.75rem;
    }
    div.row-widget.stRadio > div > label[data-checked="true"] {
        background: linear-gradient(135deg, #0A2540 0%, #0077B6 100%) !important;
        border-color: #00E5FF !important;
        box-shadow: 0 0 12px rgba(0, 229, 255, 0.25);
    }
    div.row-widget.stRadio > div > label[data-checked="true"] span,
    div.row-widget.stRadio > div > label[data-checked="true"] p {
        color: #00E5FF !important;
        font-weight: 700 !important;
    }

    /* Etiquetas de los inputs */
    .stTextInput label, .stSelectbox label, .stNumberInput label, .stDateInput label, [data-testid="stWidgetLabel"] p {
        color: #E2E8F0 !important;
        font-weight: 600 !important;
        font-size: 0.75rem !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }

    /* Botones principales */
    .stButton>button {
        background: linear-gradient(135deg, #023e8a 0%, #0077b6 100%) !important;
        color: #FFFFFF !important;
        border: 1px solid rgba(0, 229, 255, 0.3) !important;
        border-radius: 4px;
        font-weight: 700;
        padding: 0.5rem 1rem;
        width: 100%;
        box-shadow: 0 4px 15px rgba(2, 62, 138, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.15);
        transition: all 0.2s ease-in-out;
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #03045e 0%, #023e8a 100%) !important;
        border-color: #00E5FF !important;
        box-shadow: 0 0 15px rgba(0, 229, 255, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.2);
        opacity: 1;
    }

    /* FORZAR ANCHO TOTAL Y MAYOR EXPANSIÓN LATERAL EN TODOS LOS CUADROS DE TEXTO Y ENTRADAS */
    .stTextInput, .stNumberInput, .stSelectbox, .stDateInput, .stTextArea {
        width: 100% !important;
        max-width: 100% !important;
    }
    div[data-baseweb="input"], div[data-baseweb="base-input"], div[data-baseweb="select"], div[data-baseweb="textarea"] {
        width: 100% !important;
        max-width: 100% !important;
    }
    div[data-baseweb="input"] input, div[data-baseweb="base-input"] input, div[data-baseweb="textarea"] textarea {
        background-color: #080C14 !important;
        color: #F8FAFC !important;
        border-color: rgba(0, 229, 255, 0.25) !important;
        border-radius: 4px !important;
        font-size: 0.8rem !important;
        width: 100% !important;
        max-width: 100% !important;
        padding-left: 12px !important;
        padding-right: 12px !important;
    }
    
    .stTextInput > div, .stNumberInput > div, .stSelectbox > div, .stDateInput > div {
        width: 100% !important;
    }

    /* ESTILO PARA EL EXPANDER DENTRO DE LOS REGISTROS */
    [data-testid="stExpander"] {
        background-color: #080C14 !important;
        border: 1px solid rgba(0, 229, 255, 0.15) !important;
        border-radius: 4px !important;
        margin-top: 4px !important;
        margin-bottom: 4px !important;
    }
    [data-testid="stExpander"] summary {
        color: #00E5FF !important;
        font-size: 0.72rem !important;
        font-weight: 600 !important;
    }

    [data-testid="stFileUploader"] {
        display: none !important;
    }
    
    /* CORRECCIÓN DE CÁMARA: ESTRUCTURA FLEX PARA EVITAR SOLAPAMIENTO DEL BOTÓN */
    [data-testid="stCameraInput"] {
        width: 100% !important;
        max-width: 100% !important;
    }
    [data-testid="stCameraInput"] > div {
        width: 100% !important;
        max-width: 100% !important;
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
    }
    /* Contenedor del video/imagen para que no colapse con el botón */
    [data-testid="stCameraInput"] video, 
    [data-testid="stCameraInput"] img {
        width: 100% !important;
        max-width: 100% !important;
        height: auto !important;
        min-height: 350px !important;
        max-height: 450px !important;
        object-fit: contain !important; /* Mantiene la proporción sin recortar de más */
        border-radius: 6px !important;
        position: relative !important;
    }
    /* Estilo del botón de captura para que se ubique ordenadamente debajo de la imagen */
    [data-testid="stCameraInput"] button {
        width: 100% !important;
        margin-top: 8px !important;
        position: relative !important;
        z-index: 5 !important;
    }
</style>""", unsafe_allow_html=True)

# --- SISTEMA DE LOGIN CONECTADO A MYSQL ---
if not st.session_state.autenticado:
    st.markdown("""
        <div style="display: flex; align-items: center; justify-content: center; gap: 8px; width: 100%; margin-bottom: 20px; margin-top: 40px;">
            <img src="https://raw.githubusercontent.com/Miaa-Aguascalientes/Logos/38504978c8f77a4dac38ad476f74dbdee6af2cad/LogoMIAA.svg" style="width: 160px; height: auto;" />
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown('<h3 style="color: #00E5FF; text-align: center; font-size: 1.2rem; font-weight: 800;">Acceso al Sistema - Gestión VRP\'s</h3>', unsafe_allow_html=True)
    
    with st.form("login_form"):
        usuario_input = st.text_input("Usuario")
        password_input = st.text_input("Contraseña", type="password")
        submit_login = st.form_submit_button("Iniciar Sesión", use_container_width=True)
        
        if submit_login:
            if usuario_input and password_input:
                query_login = """
                    SELECT id, usuario, tipo_usuario, departamento 
                    FROM usuarios_vrp 
                    WHERE usuario = :usu AND password = :pas
                """
                df_user, err_login = obtener_datos_mysql(query_login, {"usu": usuario_input.strip(), "pas": password_input.strip()})
                
                if not err_login and not df_user.empty:
                    st.session_state.autenticado = True
                    st.session_state.usuario_actual = df_user.iloc[0]['usuario']
                    st.session_state.tipo_usuario = str(df_user.iloc[0]['tipo_usuario']).strip().lower()
                    st.session_state.departamento = df_user.iloc[0]['departamento']
                    st.success("¡Acceso concedido!")
                    t.sleep(0.5)
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos.")
            else:
                st.warning("Por favor, ingrese usuario y contraseña.")
    st.stop()

# --- CABECERA ---
st.markdown("""
    <div style="display: flex; flex-direction: column; align-items: flex-start; gap: 6px; margin-bottom: 4px; padding: 0 2px;">
        <div style="display: flex; align-items: center; gap: 10px;">
            <img src="https://raw.githubusercontent.com/Miaa-Aguascalientes/Logos/38504978c8f77a4dac38ad476f74dbdee6af2cad/LogoMIAA.svg" style="width: 160px; height: auto; flex-shrink: 0;" />
            <h2 style="color: #00E5FF; margin: 0; font-size: 1.1rem; font-weight: 800; line-height: 1.2;">Gestion VRP's</h2>
        </div>
    </div>
""", unsafe_allow_html=True)

col_cab1, col_cab2 = st.columns([0.45, 0.55])
with col_cab1:
    if st.button("Cerrar Sesión", key="btn_logout", use_container_width=True):
        st.session_state.autenticado = False
        st.rerun()
with col_cab2:
    st.markdown(f"""
        <div style="display: flex; justify-content: flex-start; align-items: center; height: 100%; margin-top: 6px;">
            <span style="color: #00E5FF; font-weight: 700; font-size: 0.8rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">👤 {st.session_state.usuario_actual}</span>
        </div>
    """, unsafe_allow_html=True)

# --- DETERMINAR ROL DEL USUARIO ---
es_operador = (st.session_state.get('tipo_usuario', '') == 'operador')

# --- MENÚ DE NAVEGACIÓN (DINÁMICO SEGÚN ROL) ---
if es_operador:
    opciones_menu = ["📍 Registros", "⚙️ Editar"]
else:
    opciones_menu = ["📍 Registros", "➕ Añadir", "⚙️ Editar"]

if 'active_tab' not in st.session_state or st.session_state.active_tab not in opciones_menu:
    st.session_state.active_tab = opciones_menu[0]

seleccion_tab = st.radio(
    "Navegación", 
    options=opciones_menu, 
    index=opciones_menu.index(st.session_state.active_tab), 
    horizontal=True, 
    label_visibility="collapsed"
)

if seleccion_tab != st.session_state.active_tab:
    st.session_state.active_tab = seleccion_tab
    st.rerun()

st.markdown("<hr style='border: 0.5px solid rgba(0,229,255,0.15); margin: 8px 0;'>", unsafe_allow_html=True)

COLUMNAS_VPRS = """
    fid, id_0, id, serie, diametro, marca_valv, model_valv, marca_trim, domicilio, colonia, 
    cota_terr, sector_hid, cal_ant_d, cal_ant_n, fecha_ult_, cal_act_d, cal_act_n, 
    hora_cal, estat_valv, observ, fotos, fotos_2
"""

# ==========================================
# SECCIÓN 1: VER REGISTROS (VPRS)
# ==========================================
if st.session_state.active_tab == "📍 Registros":
    st.markdown('<h3 style="color: #00E5FF; font-size: 1.05rem; font-weight: 700; margin-bottom: 8px; padding: 0 2px;">📂 Catálogo de Válvulas VPRS</h3>', unsafe_allow_html=True)
    
    busqueda = st.text_input("🔍 Buscar válvula (ID, Serie, Domicilio, Col.):", placeholder="Ej. VF01, Centro...")
    
    if busqueda and busqueda.strip() != "":
        filtro = f"%{busqueda.strip()}%"
        query = f"""
            SELECT {COLUMNAS_VPRS} 
            FROM "Agua_potable"."VPRS" 
            WHERE id ILIKE :filtro 
               OR serie ILIKE :filtro 
               OR domicilio ILIKE :filtro 
               OR colonia ILIKE :filtro 
            ORDER BY fid
        """
        df_vprs, error_db = obtener_datos(query, {"filtro": filtro})
    else:
        query = f'SELECT {COLUMNAS_VPRS} FROM "Agua_potable"."VPRS" ORDER BY fid LIMIT 10'
        df_vprs, error_db = obtener_datos(query)
    
    if error_db:
        st.error(f"❌ Error al consultar PostgreSQL: {error_db}")
    elif not df_vprs.empty:
        if not busqueda or busqueda.strip() == "":
            st.markdown(f"<p style='color: #94A3B8; font-size: 0.78rem; margin-bottom: 4px; padding: 0 2px;'>Mostrando primeros 10 registros.</p>", unsafe_allow_html=True)
        else:
            st.markdown(f"<p style='color: #94A3B8; font-size: 0.78rem; margin-bottom: 4px; padding: 0 2px;'>Se encontraron {len(df_vprs)} registros.</p>", unsafe_allow_html=True)
            
        for idx, row in df_vprs.iterrows():
            serie_val = row['serie']
            serie_texto = "" if (pd.isna(serie_val) or str(serie_val).strip().lower() in ["nan", "none", ""]) else f" | Serie: {serie_val}"
            
            card_html = f"""
                <div class="user-card" style="margin-bottom: 2px;">
                    <span style="font-size: 0.8rem; font-weight: bold; color: #F8FAFC;">ID: {row['id']}{serie_texto}</span><br>
                    <span style="color: #00E5FF; font-size: 0.77rem;">📍 {row['domicilio'] or 'Sin domicilio'}, Col. {row['colonia'] or 'Sin colonia'}</span>
                </div>
            """
            st.markdown(card_html, unsafe_allow_html=True)
            
            with st.expander("🔍 Ver detalles completos"):
                detalle_html = f"""
                    <span style="color: #94A3B8; font-size: 0.68rem; line-height: 1.4;">
                        Diámetro: {row['diametro']} pulgadas | Marca: {row['marca_valv']} | Modelo: {row['model_valv']} | Trim: {row['marca_trim']} | Cota: {row['cota_terr']}<br>
                        Sector: {row['sector_hid']} | Estado de la Válvula: {row['estat_valv']} | Hora Cal: {row['hora_cal']} | Fecha ultima actualización: {row['fecha_ult_']}<br>
                        Cal Anterior Día (kg/cm): {row['cal_ant_d']} | Cal Anterior Noche (kg/cm): {row['cal_ant_n']}<br>
                        Cal Actual Día (kg/cm): {row['cal_act_d']} | Cal Actual Noche (kg/cm): {row['cal_act_n']}<br>
                        Obs: {row['observ']}
                    </span>
                """
                st.markdown(detalle_html, unsafe_allow_html=True)
                
                img_bytes = procesar_bytes_foto(row['fotos'])
                if img_bytes is not None and len(img_bytes) > 0:
                    st.markdown("<p style='color: #00E5FF; font-size: 0.75rem; margin-top: 6px; margin-bottom: 2px;'>📸 Fotografía 1 registrada:</p>", unsafe_allow_html=True)
                    st.image(img_bytes, caption=f"ID: {row['id']} (Foto 1)", use_container_width=True)

                img_bytes_2 = procesar_bytes_foto(row['fotos_2'])
                if img_bytes_2 is not None and len(img_bytes_2) > 0:
                    st.markdown("<p style='color: #00E5FF; font-size: 0.75rem; margin-top: 6px; margin-bottom: 2px;'>📸 Fotografía 2 registrada:</p>", unsafe_allow_html=True)
                    st.image(img_bytes_2, caption=f"ID: {row['id']} (Foto 2)", use_container_width=True)
                        
            st.markdown("<div style='margin-bottom: 8px;'></div>", unsafe_allow_html=True)
    else:
        st.info("No se encontraron registros.")

# ==========================================
# SECCIÓN 2: AÑADIR NUEVA VÁLVULA (SOLO ADMIN / NO OPERADOR)
# ==========================================
elif st.session_state.active_tab == "➕ Añadir":
    if es_operador:
        st.error("⛔ El perfil de operador no tiene permisos para dar de alta nueva infraestructura.")
        st.stop()

    st.markdown('<h3 style="color: #00E5FF; font-size: 1.05rem; font-weight: 700; margin-bottom: 8px; padding: 0 2px;">✨ Registrar nueva VPRS</h3>', unsafe_allow_html=True)
    
    df_max_id0, err_max = obtener_datos('SELECT MAX(id_0) as max_id FROM "Agua_potable"."VPRS"')
    siguiente_id_0 = 1
    if not err_max and not df_max_id0.empty and df_max_id0['max_id'].iloc[0] is not None:
        try:
            siguiente_id_0 = int(df_max_id0['max_id'].iloc[0]) + 1
        except:
            siguiente_id_0 = 1

    r1c1, r1c2 = st.columns(2)
    with r1c1: 
        st.text_input("ID_0 (Automático)", value=str(siguiente_id_0), disabled=True, key="add_id_0_bloq")
        val_id_0 = siguiente_id_0
    with r1c2: val_id = st.text_input("ID (VRP)", key="add_id")

    r2c1, r2c2 = st.columns(2)
    with r2c1: val_serie = st.text_input("Serie", key="add_serie")
    with r2c2: val_diametro = st.number_input("Diámetro", min_value=0, value=0, key="add_diam")

    r3c1, r3c2 = st.columns(2)
    with r3c1: val_cota = st.number_input("Cota Territorio", value=0.0, key="add_cota")
    with r3c2: val_marca = st.text_input("Marca Válvula", key="add_marca")

    r4c1, r4c2 = st.columns(2)
    with r4c1: val_modelo = st.text_input("Modelo Válvula", key="add_modelo")
    with r4c2: val_trim = st.text_input("Marca Trim", key="add_trim")

    r5c1, r5c2 = st.columns(2)
    with r5c1: val_sector = st.text_input("Sector Hidráulico", key="add_sector")
    with r5c2: val_domicilio = st.text_input("Domicilio", key="add_dom")

    r6c1, r6c2 = st.columns(2)
    with r6c1: val_colonia = st.text_input("Colonia", key="add_col")
    with r6c2: val_estat = st.selectbox("Estado de la Válvula", options=OPCIONES_ESTADO_VALVULA, index=0, key="add_estat")

    r7c1, r7c2 = st.columns(2)
    with r7c1: val_hora = st.text_input("Hora Calibración", key="add_hora")
    with r7c2: val_cal_ant_d = st.text_input("Cal Anterior Día (kg/cm)", key="add_cand")

    r8c1, r8c2 = st.columns(2)
    with r8c1: val_cal_ant_n = st.text_input("Cal Anterior Noche (kg/cm)", key="add_cann")
    with r8c2: val_cal_act_d = st.text_input("Cal Actual Día (kg/cm)", key="add_cactd")

    r9c1, r9c2 = st.columns(2)
    with r9c1: val_cal_act_n = st.text_input("Cal Actual Noche (kg/cm)", key="add_cactn")
    with r9c2: 
        val_fecha_obj = st.date_input(
            "Fecha última actualización", 
            value=datetime.date.today(),
            min_value=datetime.date(2000, 1, 1),
            max_value=datetime.date(2035, 12, 31),
            format="DD/MM/YYYY",
            key="add_fecha"
        )
        val_fecha = val_fecha_obj.strftime("%d/%m/%Y")

    val_observ = st.text_input("Observaciones", key="add_obs")

    st.markdown("<hr style='border: 0.3px solid rgba(0,229,255,0.2);'>", unsafe_allow_html=True)
    st.markdown("<p style='color: #00E5FF; font-weight: 600; font-size: 0.8rem; padding: 0 2px;'>📸 Fotografía 1:</p>", unsafe_allow_html=True)
    
    cam_key_nuevo = "cam_open_nuevo"
    if cam_key_nuevo not in st.session_state:
        st.session_state[cam_key_nuevo] = False
        
    if not st.session_state[cam_key_nuevo]:
        if st.button("📷 Activar Cámara 1", key="btn_open_cam_nuevo", use_container_width=True):
            st.session_state[cam_key_nuevo] = True
            st.rerun()
    else:
        if st.button("❌ Cerrar Cámara 1", key="btn_close_cam_nuevo", use_container_width=True):
            st.session_state[cam_key_nuevo] = False
            st.rerun()

    foto_camara = None
    if st.session_state[cam_key_nuevo]:
        foto_camara = st.camera_input("Capturar 1", key="camara_nuevo", label_visibility="collapsed")

    st.markdown("<p style='color: #00E5FF; font-weight: 600; font-size: 0.8rem; padding: 0 2px; margin-top: 10px;'>📸 Fotografía 2:</p>", unsafe_allow_html=True)
    
    cam_key_nuevo_2 = "cam_open_nuevo_2"
    if cam_key_nuevo_2 not in st.session_state:
        st.session_state[cam_key_nuevo_2] = False
        
    if not st.session_state[cam_key_nuevo_2]:
        if st.button("📷 Activar Cámara 2", key="btn_open_cam_nuevo_2", use_container_width=True):
            st.session_state[cam_key_nuevo_2] = True
            st.rerun()
    else:
        if st.button("❌ Cerrar Cámara 2", key="btn_close_cam_nuevo_2", use_container_width=True):
            st.session_state[cam_key_nuevo_2] = False
            st.rerun()

    foto_camara_2 = None
    if st.session_state[cam_key_nuevo_2]:
        foto_camara_2 = st.camera_input("Capturar 2", key="camara_nuevo_2", label_visibility="collapsed")

    if st.button("💾 Guardar Registro", key="btn_guardar_nuevo", use_container_width=True):
        if val_id:
            try:
                foto_bytes = foto_camara.getvalue() if foto_camara is not None else None
                foto_bytes_2 = foto_camara_2.getvalue() if foto_camara_2 is not None else None
                
                sql_insert = """
                    INSERT INTO "Agua_potable"."VPRS" (
                        id_0, id, serie, diametro, marca_valv, model_valv, marca_trim, domicilio, colonia, 
                        cota_terr, sector_hid, cal_ant_d, cal_ant_n, fecha_ult_, cal_act_d, cal_act_n, 
                        hora_cal, estat_valv, observ, fotos, fotos_2
                    ) VALUES (
                        :id_0, :id, :serie, :diametro, :marca_valv, :model_valv, :marca_trim, :domicilio, :colonia, 
                        :cota_terr, :sector_hid, :cal_ant_d, :cal_ant_n, :fecha_ult_, :cal_act_d, :cal_act_n, 
                        :hora_cal, :estat_valv, :observ, :fotos, :fotos_2
                    )
                """
                ejecutar_sql(sql_insert, {
                    "id_0": val_id_0, "id": val_id, "serie": val_serie if val_serie.strip() != "" else None, "diametro": val_diametro, "marca_valv": val_marca,
                    "model_valv": val_modelo, "marca_trim": val_trim, "domicilio": val_domicilio, "colonia": val_colonia,
                    "cota_terr": val_cota, "sector_hid": val_sector, "cal_ant_d": val_cal_ant_d, "cal_ant_n": val_cal_ant_n,
                    "fecha_ult_": val_fecha, "cal_act_d": val_cal_act_d, "cal_act_n": val_cal_act_n, "hora_cal": val_hora,
                    "estat_valv": val_estat, "observ": val_observ, "fotos": foto_bytes, "fotos_2": foto_bytes_2
                })
                st.success("¡Válvula registrada con éxito!")
                t.sleep(1)
                st.rerun()
            except Exception as ex:
                st.error(f"Error al insertar: {ex}")
        else:
            st.warning("El campo ID es obligatorio.")

# ==========================================
# SECCIÓN 3: EDITAR Y ELIMINAR (SOLO 1 REGISTRO A LA VEZ)
# ==========================================
elif st.session_state.active_tab == "⚙️ Editar":
    st.markdown('<h3 style="color: #00E5FF; font-size: 1.05rem; font-weight: 700; margin-bottom: 8px; padding: 0 2px;">🛠️ Modificar o Eliminar Válvula</h3>', unsafe_allow_html=True)
    
    busqueda_edit = st.text_input("🔍 Buscar válvula a editar (ID, Serie, Domicilio, Col.):", placeholder="Ej. VRP-01, Centro...")
    
    if busqueda_edit and busqueda_edit.strip() != "":
        filtro_ed = f"%{busqueda_edit.strip()}%"
        query_edit = f"""
            SELECT {COLUMNAS_VPRS} 
            FROM "Agua_potable"."VPRS" 
            WHERE id ILIKE :filtro 
               OR serie ILIKE :filtro 
               OR domicilio ILIKE :filtro 
               OR colonia ILIKE :filtro 
            ORDER BY fid
            LIMIT 1
        """
        df_vprs, error_db = obtener_datos(query_edit, {"filtro": filtro_ed})
    else:
        query = f'SELECT {COLUMNAS_VPRS} FROM "Agua_potable"."VPRS" ORDER BY fid LIMIT 1'
        df_vprs, error_db = obtener_datos(query)
    
    if error_db:
        st.error(f"Error: {error_db}")
    elif not df_vprs.empty:
        if not busqueda_edit or busqueda_edit.strip() == "":
            st.markdown(f"<p style='color: #94A3B8; font-size: 0.78rem; margin-bottom: 4px; padding: 0 2px;'>Mostrando el primer registro de la base de datos.</p>", unsafe_allow_html=True)
        else:
            st.markdown(f"<p style='color: #94A3B8; font-size: 0.78rem; margin-bottom: 4px; padding: 0 2px;'>Mostrando la primera coincidencia encontrada.</p>", unsafe_allow_html=True)
            
        for idx, row in df_vprs.iterrows():
            st.markdown(f"<div style='padding: 0 2px;'><span style='color: #00E5FF; font-weight: bold;'>FID Registro: {row['fid']}</span> | <span style='color: #F8FAFC;'>ID: {row['id']}</span></div>", unsafe_allow_html=True)

            e_id_0 = row['id_0']

            # Calcular el índice por defecto para Estado de la Válvula
            estado_actual = str(row['estat_valv'] or "").strip()
            idx_estado = 0
            if estado_actual in OPCIONES_ESTADO_VALVULA:
                idx_estado = OPCIONES_ESTADO_VALVULA.index(estado_actual)

            if es_operador:
                # OCULTAR COMPLETAMENTE LOS CAMPOS DE INFRAESTRUCTURA PARA OPERADOR
                e_id = row['id']
                e_diametro = row['diametro']
                e_cota = row['cota_terr']
                e_marca = row['marca_valv']
                e_modelo = row['model_valv']
                e_trim = row['marca_trim']
                e_sector = row['sector_hid']
                e_domicilio = row['domicilio']
                e_colonia = row['colonia']

                e_r1c1, e_r1c2 = st.columns(2)
                e_serie_val = "" if (pd.isna(row['serie']) or str(row['serie']).strip().lower() in ["nan", "none"]) else str(row['serie'])
                with e_r1c1: 
                    e_serie = st.text_input("Serie", value=e_serie_val, key=f"serie_{row['fid']}")
                with e_r1c2: 
                    e_estat = st.selectbox("Estado de la Válvula", options=OPCIONES_ESTADO_VALVULA, index=idx_estado, key=f"est_{row['fid']}")

                e_r2c1, e_r2c2 = st.columns(2)
                with e_r2c1: 
                    e_hora = st.text_input("Hora Cal", value=str(row['hora_cal'] or ""), key=f"hora_{row['fid']}")
                with e_r2c2: 
                    e_cal_ant_d = st.text_input("Cal Anterior Día (kg/cm)", value=str(row['cal_ant_d'] or ""), key=f"cand_{row['fid']}")

                e_r3c1, e_r3c2 = st.columns(2)
                with e_r3c1: 
                    e_cal_ant_n = st.text_input("Cal Anterior Noche (kg/cm)", value=str(row['cal_ant_n'] or ""), key=f"cann_{row['fid']}")
                with e_r3c2: 
                    e_cal_act_d = st.text_input("Cal Actual Día (kg/cm)", value=str(row['cal_act_d'] or ""), key=f"cactd_{row['fid']}")

                e_r4c1, e_r4c2 = st.columns(2)
                with e_r4c1: 
                    e_cal_act_n = st.text_input("Cal Actual Noche (kg/cm)", value=str(row['cal_act_n'] or ""), key=f"cactn_{row['fid']}")
                with e_r4c2: 
                    fecha_def = parsear_fecha_segura(row['fecha_ult_'])
                    e_fecha_obj = st.date_input(
                        "Fecha última actualización", 
                        value=fecha_def,
                        min_value=datetime.date(2000, 1, 1),
                        max_value=datetime.date(2035, 12, 31),
                        format="DD/MM/YYYY",
                        key=f"fec_{row['fid']}"
                    )
                    e_fecha = e_fecha_obj.strftime("%d/%m/%Y")

                e_observ = st.text_input("Observaciones", value=str(row['observ'] or ""), key=f"obs_{row['fid']}")

            else:
                # VISTA COMPLETA (ADMINISTRADOR / OTROS ROLES)
                e_r1c1, e_r1c2 = st.columns(2)
                with e_r1c1: 
                    st.text_input("ID_0 (Bloqueado)", value=str(row['id_0'] or 0), disabled=True, key=f"id0_bloq_{row['fid']}")
                with e_r1c2: 
                    e_id = st.text_input("ID", value=str(row['id'] or ""), key=f"id_{row['fid']}")

                e_r2c1, e_r2c2 = st.columns(2)
                e_serie_val = "" if (pd.isna(row['serie']) or str(row['serie']).strip().lower() in ["nan", "none"]) else str(row['serie'])
                with e_r2c1: 
                    e_serie = st.text_input("Serie", value=e_serie_val, key=f"serie_{row['fid']}")
                with e_r2c2: 
                    e_diametro = st.number_input("Diámetro", value=int(row['diametro'] or 0), key=f"diam_{row['fid']}")

                e_r3c1, e_r3c2 = st.columns(2)
                with e_r3c1: 
                    e_cota = st.number_input("Cota Terr", value=float(row['cota_terr'] or 0.0), key=f"cota_{row['fid']}")
                with e_r3c2: 
                    e_marca = st.text_input("Marca Valv", value=str(row['marca_valv'] or ""), key=f"mar_{row['fid']}")

                e_r4c1, e_r4c2 = st.columns(2)
                with e_r4c1: 
                    e_modelo = st.text_input("Modelo Valv", value=str(row['model_valv'] or ""), key=f"mod_{row['fid']}")
                with e_r4c2: 
                    e_trim = st.text_input("Marca Trim", value=str(row['marca_trim'] or ""), key=f"trim_{row['fid']}")

                e_r5c1, e_r5c2 = st.columns(2)
                with e_r5c1: 
                    e_sector = st.text_input("Sector Hid", value=str(row['sector_hid'] or ""), key=f"sec_{row['fid']}")
                with e_r5c2: 
                    e_domicilio = st.text_input("Domicilio", value=str(row['domicilio'] or ""), key=f"dom_{row['fid']}")

                e_r6c1, e_r6c2 = st.columns(2)
                with e_r6c1: 
                    e_colonia = st.text_input("Colonia", value=str(row['colonia'] or ""), key=f"col_{row['fid']}")
                with e_r6c2: 
                    e_estat = st.selectbox("Estado de la Válvula", options=OPCIONES_ESTADO_VALVULA, index=idx_estado, key=f"est_{row['fid']}")

                e_r7c1, e_r7c2 = st.columns(2)
                with e_r7c1: 
                    e_hora = st.text_input("Hora Cal", value=str(row['hora_cal'] or ""), key=f"hora_{row['fid']}")
                with e_r7c2: 
                    e_cal_ant_d = st.text_input("Cal Anterior Día (kg/cm)", value=str(row['cal_ant_d'] or ""), key=f"cand_{row['fid']}")

                e_r8c1, e_r8c2 = st.columns(2)
                with e_r8c1: 
                    e_cal_ant_n = st.text_input("Cal Anterior Noche (kg/cm)", value=str(row['cal_ant_n'] or ""), key=f"cann_{row['fid']}")
                with e_r8c2: 
                    e_cal_act_d = st.text_input("Cal Actual Día (kg/cm)", value=str(row['cal_act_d'] or ""), key=f"cactd_{row['fid']}")

                e_r9c1, e_r9c2 = st.columns(2)
                with e_r9c1: 
                    e_cal_act_n = st.text_input("Cal Actual Noche (kg/cm)", value=str(row['cal_act_n'] or ""), key=f"cactn_{row['fid']}")
                with e_r9c2: 
                    fecha_def = parsear_fecha_segura(row['fecha_ult_'])
                    e_fecha_obj = st.date_input(
                        "Fecha última actualización", 
                        value=fecha_def,
                        min_value=datetime.date(2000, 1, 1),
                        max_value=datetime.date(2035, 12, 31),
                        format="DD/MM/YYYY",
                        key=f"fec_{row['fid']}"
                    )
                    e_fecha = e_fecha_obj.strftime("%d/%m/%Y")

                e_observ = st.text_input("Observaciones", value=str(row['observ'] or ""), key=f"obs_{row['fid']}")
            
            # --- FOTO 1 ---
            foto_actual_bytes = procesar_bytes_foto(row['fotos'])
            eliminar_foto = False
            
            if foto_actual_bytes is not None and len(foto_actual_bytes) > 0:
                st.markdown("<p style='color: #00E5FF; font-size: 0.75rem; margin-top: 10px; margin-bottom: 2px;'>📸 Fotografía 1 actual:</p>", unsafe_allow_html=True)
                st.image(foto_actual_bytes, caption=f"ID: {row['id']} (Foto 1)", use_container_width=True)
                eliminar_foto = st.checkbox("🗑️ Eliminar la fotografía 1 actual", key=f"del_foto_{row['fid']}")

            st.markdown("<p style='color: #00E5FF; font-weight: 600; font-size: 0.78rem; padding: 0 2px; margin-top: 10px;'>📸 Reemplazar o capturar nueva Foto 1:</p>", unsafe_allow_html=True)
            
            cam_key_edit = f"cam_open_edit_{row['fid']}"
            if cam_key_edit not in st.session_state:
                st.session_state[cam_key_edit] = False

            if not st.session_state[cam_key_edit]:
                if st.button("📷 Activar Cámara 1", key=f"btn_open_cam_edit_{row['fid']}", use_container_width=True):
                    st.session_state[cam_key_edit] = True
                    st.rerun()
            else:
                if st.button("❌ Cerrar Cámara 1", key=f"btn_close_cam_edit_{row['fid']}", use_container_width=True):
                    st.session_state[cam_key_edit] = False
                    st.rerun()

            nueva_foto_camara = None
            if st.session_state.get(f"cam_open_edit_{row['fid']}", False):
                nueva_foto_camara = st.camera_input("Tomar foto 1", key=f"cam_edit_{row['fid']}", label_visibility="collapsed")

            # --- FOTO 2 ---
            foto_actual_bytes_2 = procesar_bytes_foto(row['fotos_2'])
            eliminar_foto_2 = False
            
            if foto_actual_bytes_2 is not None and len(foto_actual_bytes_2) > 0:
                st.markdown("<p style='color: #00E5FF; font-size: 0.75rem; margin-top: 15px; margin-bottom: 2px;'>📸 Fotografía 2 actual:</p>", unsafe_allow_html=True)
                st.image(foto_actual_bytes_2, caption=f"ID: {row['id']} (Foto 2)", use_container_width=True)
                eliminar_foto_2 = st.checkbox("🗑️ Eliminar la fotografía 2 actual", key=f"del_foto_2_{row['fid']}")

            st.markdown("<p style='color: #00E5FF; font-weight: 600; font-size: 0.78rem; padding: 0 2px; margin-top: 10px;'>📸 Reemplazar o capturar nueva Foto 2:</p>", unsafe_allow_html=True)
            
            cam_key_edit_2 = f"cam_open_edit_2_{row['fid']}"
            if cam_key_edit_2 not in st.session_state:
                st.session_state[cam_key_edit_2] = False

            if not st.session_state[cam_key_edit_2]:
                if st.button("📷 Activar Cámara 2", key=f"btn_open_cam_edit_2_{row['fid']}", use_container_width=True):
                    st.session_state[cam_key_edit_2] = True
                    st.rerun()
            else:
                if st.button("❌ Cerrar Cámara 2", key=f"btn_close_cam_edit_2_{row['fid']}", use_container_width=True):
                    st.session_state[cam_key_edit_2] = False
                    st.rerun()

            nueva_foto_camara_2 = None
            if st.session_state.get(f"cam_open_edit_2_{row['fid']}", False):
                nueva_foto_camara_2 = st.camera_input("Tomar foto 2", key=f"cam_edit_2_{row['fid']}", label_visibility="collapsed")

            st.markdown("<br>", unsafe_allow_html=True)
            actualizar_click = st.button("💾 Actualizar Registro", key=f"btn_act_{row['fid']}", use_container_width=True)

            if actualizar_click:
                try:
                    if eliminar_foto:
                        foto_bytes_final = None
                    else:
                        foto_bytes_final = foto_actual_bytes
                        if nueva_foto_camara is not None:
                            foto_bytes_final = nueva_foto_camara.getvalue()

                    if eliminar_foto_2:
                        foto_bytes_final_2 = None
                    else:
                        foto_bytes_final_2 = foto_actual_bytes_2
                        if nueva_foto_camara_2 is not None:
                            foto_bytes_final_2 = nueva_foto_camara_2.getvalue()

                    sql_update = """
                        UPDATE "Agua_potable"."VPRS" 
                        SET id_0 = :id_0, id = :id, serie = :serie, diametro = :diametro, marca_valv = :marca_valv, 
                            model_valv = :model_valv, marca_trim = :marca_trim, domicilio = :domicilio, 
                            colonia = :colonia, cota_terr = :cota_terr, sector_hid = :sector_hid, 
                            cal_ant_d = :cal_ant_d, cal_ant_n = :cal_ant_n, fecha_ult_ = :fecha_ult_, 
                            cal_act_d = :cal_act_d, cal_act_n = :cal_act_n, hora_cal = :hora_cal, 
                            estat_valv = :estat_valv, observ = :observ, fotos = :fotos, fotos_2 = :fotos_2 
                        WHERE fid = :fid
                    """
                    ejecutar_sql(sql_update, {
                        "id_0": e_id_0, "id": e_id, "serie": e_serie if e_serie.strip() != "" else None, "diametro": e_diametro, "marca_valv": e_marca,
                        "model_valv": e_modelo, "marca_trim": e_trim, "domicilio": e_domicilio, "colonia": e_colonia,
                        "cota_terr": e_cota, "sector_hid": e_sector, "cal_ant_d": e_cal_ant_d, "cal_ant_n": e_cal_ant_n,
                        "fecha_ult_": e_fecha, "cal_act_d": e_cal_act_d, "cal_act_n": e_cal_act_n, "hora_cal": e_hora,
                        "estat_valv": e_estat, "observ": e_observ, "fotos": foto_bytes_final, "fotos_2": foto_bytes_final_2, "fid": row['fid']
                    })
                    st.success(f"¡Registro FID {row['fid']} actualizado con éxito!")
                    t.sleep(1)
                    st.rerun()
                except Exception as ex:
                    st.error(f"Error al actualizar: {ex}")

            if not es_operador:
                st.markdown("<hr style='border: 0.5px solid rgba(255,0,0,0.2); margin: 15px 0;'>", unsafe_allow_html=True)
                
                if st.session_state.registro_to_delete == row['fid']:
                    st.markdown(f"<p style='color: #ff4d4d; font-size: 0.8rem; font-weight: bold;'>Para eliminar el registro FID {row['fid']} (ID: {row['id']}), escribe la palabra 'delete':</p>", unsafe_allow_html=True)
                    confirm_text = st.text_input("Confirmación de eliminación", key=f"input_del_text_{row['fid']}")
                    
                    col_y, col_n = st.columns(2)
                    with col_y:
                        if st.button("Sí, eliminar", key=f"confirm_del_{row['fid']}", use_container_width=True):
                            if confirm_text.strip() == "delete":
                                try:
                                    ejecutar_sql('DELETE FROM "Agua_potable"."VPRS" WHERE fid = :fid', {"fid": row['fid']})
                                    st.session_state.registro_to_delete = None
                                    st.success("Registro eliminado correctamente.")
                                    t.sleep(1)
                                    st.rerun()
                                except Exception as ex_del:
                                    st.error(f"Error al eliminar: {ex_del}")
                            else:
                                st.error("Debes escribir exactamente la palabra 'delete' para confirmar.")
                    with col_n:
                        if st.button("Cancelar", key=f"cancel_del_{row['fid']}", use_container_width=True):
                            st.session_state.registro_to_delete = None
                            st.rerun()
                else:
                    if st.button("🗑️ Eliminar este registro", key=f"btn_del_{row['fid']}", use_container_width=True):
                        st.session_state.registro_to_delete = row['fid']
                        st.rerun()

            st.markdown("<hr style='border: 1px solid rgba(0,229,255,0.2); margin: 20px 0;'>", unsafe_allow_html=True)
    else:
        st.info("No se encontró ningún registro para editar.")

# --- PIE DE PÁGINA ---
st.markdown("""
    <div style="text-align: center; color: #94A3B8; font-size: 0.78rem; margin-top: 2rem; border-top: 1px solid rgba(0, 229, 255, 0.12); padding-top: 0.8rem;">
        © 2026 MIAA &bull; Sistema de Gestión PostGIS y MySQL
    </div>
""", unsafe_allow_html=True)
