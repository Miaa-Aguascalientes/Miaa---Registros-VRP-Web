# VRP - Registros.py
import base64
import datetime
import time as t
from zoneinfo import ZoneInfo
import folium
from folium.plugins import Fullscreen, MarkerCluster
import pandas as pd
from pyproj import Transformer
from sqlalchemy import create_engine, text
import streamlit as st
from streamlit_folium import st_folium

# Configuración de página
st.set_page_config(
    layout="wide",
    page_title="Gestión Válvulas Reductoras de Presión - MIAA",
    page_icon="https://www.miaa.mx/favicon.ico",
)

# 01 SECCION ----------------------------------------------------------------------------------------------- ESTADO DE SESIÓN ----------------------------------------------------------------------------------------
if "registro_to_delete" not in st.session_state:
  st.session_state.registro_to_delete = None
if "active_tab" not in st.session_state:
  st.session_state.active_tab = "📍 Registros"
if "autenticado" not in st.session_state:
  st.session_state.autenticado = False

zona_mx = ZoneInfo("America/Mexico_City")
API_KEY_CARTO = "cb1_26ji_1_864817f3cb73c0bdbe0daccd"

# Transformadores de coordenadas (UTM Zona 13N <-> Lat/Lon WGS84)
transformer_to_latlon = Transformer.from_crs(
    "EPSG:32613", "EPSG:4326", always_xy=True
)
transformer_to_utm = Transformer.from_crs(
    "EPSG:4326", "EPSG:32613", always_xy=True
)

OPCIONES_ESTADO_VALVULA = [
    "Abierta",
    "Calibrada",
    "Cerrada",
    "Dañada",
    "Descalibrada",
    "Habilitada",
    "No opera",
    "Pendiente",
]

# 02 SECCION -------------------------------------------------------------------------- CONEXIÓN A BASE DE DATOS POSTGRESQL (VPRS) --------------------------------------------------------------------------------------


def crear_nuevo_engine():
  pg = st.secrets["postgres"]
  db_url = f"postgresql+psycopg2://{pg['user']}:{pg['password']}@{pg['host']}:{pg['port']}/{pg['database']}"
  return create_engine(
      db_url,
      pool_pre_ping=True,
      pool_recycle=1800,
      pool_timeout=60,
      connect_args={"connect_timeout": 60},
  )


if "db_engine" not in st.session_state:
  st.session_state.db_engine = crear_nuevo_engine()


def obtener_datos(query, params=None):
  for intento in range(2):
    try:
      with st.session_state.db_engine.connect() as conn:
        df = pd.read_sql(
            text(query) if isinstance(query, str) else query,
            conn,
            params=params or {},
        )
        return df, None
    except Exception:
      try:
        st.session_state.db_engine.dispose()
        st.session_state.db_engine = crear_nuevo_engine()
        with st.session_state.db_engine.connect() as conn:
          df = pd.read_sql(
              text(query) if isinstance(query, str) else query,
              conn,
              params=params or {},
          )
          return df, None
      except Exception as e2:
        if intento == 1:
          return pd.DataFrame(), str(e2)
  return pd.DataFrame(), "Error de conexión persistente."


def ejecutar_sql(query, params=None):
  with st.session_state.db_engine.connect() as conn:
    with conn.begin():
      conn.execute(
          text(query) if isinstance(query, str) else query, params or {}
      )
  return True


# 03 SECCION ------------------------------------------------------------------- CONEXIÓN A MYSQL (USUARIOS / LOGIN) --------------------------------------------------------------------------------------------------
def crear_engine_mysql():
  mysql_sec = st.secrets["mysql_usuarios_vrp"]
  db_url = f"mysql+pymysql://{mysql_sec['user']}:{mysql_sec['password']}@{mysql_sec['host']}:{mysql_sec['port']}/{mysql_sec['database']}"
  return create_engine(
      db_url,
      pool_pre_ping=True,
      pool_recycle=1800,
      pool_timeout=60,
      connect_args={"connect_timeout": 60},
  )


if "db_mysql_engine" not in st.session_state:
  st.session_state.db_mysql_engine = crear_engine_mysql()


def obtener_datos_mysql(query, params=None):
  for intento in range(2):
    try:
      with st.session_state.db_mysql_engine.connect() as conn:
        df = pd.read_sql(
            text(query) if isinstance(query, str) else query,
            conn,
            params=params or {},
        )
        return df, None
    except Exception:
      try:
        st.session_state.db_mysql_engine.dispose()
        st.session_state.db_mysql_engine = crear_engine_mysql()
        with st.session_state.db_mysql_engine.connect() as conn:
          df = pd.read_sql(
              text(query) if isinstance(query, str) else query,
              conn,
              params=params or {},
          )
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
  if (
      pd.isna(val_fecha)
      or val_fecha is None
      or str(val_fecha).strip() in ["", "nan", "None"]
  ):
    return datetime.date.today()
  if isinstance(val_fecha, (datetime.date, datetime.datetime)):
    return val_fecha if isinstance(val_fecha, datetime.date) else val_fecha.date()
  try:
    return pd.to_datetime(val_fecha).date()
  except Exception:
    return datetime.date.today()


def agregar_capas_base_mapa(m):
  """Función auxiliar para inyectar todas las capas base en cualquier mapa de Folium."""
  folium.TileLayer(
      tiles="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
      name="Vista Satélite",
      attr="Google",
      max_zoom=20,
      overlay=False,
      control=True,
  ).add_to(m)

  folium.TileLayer(
      tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      name="Satélite (Esri)",
      attr="Esri",
      max_zoom=20,
      overlay=False,
      control=True,
  ).add_to(m)

  folium.TileLayer(
      tiles=f"https://{{s}}.basemaps.cartocdn.com/rastertiles/dark_all/{{z}}/{{x}}/{{y}}.png?key={API_KEY_CARTO}",
      name="Vista Nocturna",
      attr=(
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          ' contributors &copy; <a'
          ' href="https://carto.com/attributions">CARTO</a>'
      ),
      subdomains="abcd",
      max_zoom=20,
      overlay=False,
      control=True,
  ).add_to(m)


# 04 SECCION ------------------------------------------------------------- ESTILOS CSS CON BARRA LATERAL FIJA Y LOGOTIPO MÁS ARRIBA --------------------------------------------------------------------------------
st.write(
    """<style>
    #MainMenu, [data-testid="stHeader"] {visibility: hidden !important; display: none !important;} 
    
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
        padding-top: 0.5rem !important; 
        padding-bottom: 3rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        background: #080C14;
        color: #F8FAFC;
        max-width: 1650px !important;
    }
    body, [data-testid="stAppViewContainer"] {
        background: #080C14;
        color: #F8FAFC;
    }

    [data-testid="stSidebar"] {
        background-color: #0A0F1D !important;
        border-right: 1px solid rgba(0, 229, 255, 0.15) !important;
        padding-top: 0rem !important;
        min-width: 280px !important;
        max-width: 320px !important;
        transform: none !important;
        visibility: visible !important;
        display: block !important;
    }
    
    [data-testid="stSidebarNavSeparator"], button[kind="header"], [data-testid="collapsedControl"] {
        display: none !important;
        visibility: hidden !important;
    }

    [data-testid="stSidebar"] .block-container {
        padding-top: 0rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }

    /* --- NAVEGACIÓN TIPO TARJETAS / TABS (SIN CÍRCULOS DE RADIO) --- */
    div.row-widget.stRadio > div {
        display: flex;
        flex-direction: column;
        gap: 8px !important;
    }

    /* Ocultar círculo nativo de radio button */
    div.row-widget.stRadio input[type="radio"],
    div.row-widget.stRadio div[role="radiogroup"] > label > div:first-child {
        display: none !important;
    }

    /* Estilo base de los botones de navegación */
    div.row-widget.stRadio div[role="radiogroup"] > label {
        background: #0D1424 !important;
        border: 1px solid rgba(0, 229, 255, 0.15) !important;
        border-radius: 8px !important;
        padding: 10px 14px !important;
        margin: 0 !important;
        cursor: pointer !important;
        transition: all 0.2s ease-in-out !important;
        width: 100% !important;
    }

    /* Texto e iconos */
    div.row-widget.stRadio div[role="radiogroup"] label p,
    div.row-widget.stRadio div[role="radiogroup"] label span {
        color: #94A3B8 !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
    }

    /* Hover (Efecto al pasar el mouse) */
    div.row-widget.stRadio div[role="radiogroup"] > label:hover {
        background: #152035 !important;
        border-color: rgba(0, 229, 255, 0.4) !important;
        transform: translateX(4px) !important;
    }

    /* Opción Seleccionada (Activa) */
    div.row-widget.stRadio div[role="radiogroup"] > label[data-checked="true"] {
        background: linear-gradient(90deg, #0A2540 0%, #0D1424 100%) !important;
        border-left: 4px solid #00E5FF !important;
        border-color: rgba(0, 229, 255, 0.5) !important;
        box-shadow: 0 2px 10px rgba(0, 229, 255, 0.15) !important;
    }

    div.row-widget.stRadio div[role="radiogroup"] > label[data-checked="true"] p,
    div.row-widget.stRadio div[role="radiogroup"] > label[data-checked="true"] span {
        color: #00E5FF !important;
        font-weight: 700 !important;
    }

    .user-card {
        background: #0D1424;
        border: 1px solid rgba(0, 229, 255, 0.15);
        border-left: 4px solid #00E5FF;
        border-radius: 6px;
        padding: 12px 16px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
        margin-bottom: 10px;
    }

    .stTextInput label, .stSelectbox label, .stNumberInput label, .stDateInput label, [data-testid="stWidgetLabel"] p {
        color: #E2E8F0 !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
    }

    /* 1. ESTILO BASE PARA TODOS LOS BOTONES (Neutros / Secundarios) */
    .stButton>button {
        background: #1E293B !important;
        color: #F8FAFC !important;
        border: 1px solid rgba(0, 229, 255, 0.25) !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 0.55rem 1.2rem !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3) !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    .stButton>button:hover {
        background: #334155 !important;
        border-color: #00E5FF !important;
        color: #00E5FF !important;
        box-shadow: 0 0 12px rgba(0, 229, 255, 0.3) !important;
        transform: translateY(-1px) !important;
    }

    /* 2. BOTÓN PRINCIPAL:💾 Actualizar / Guardar Registro (Resalta en Azul Cyan Neón) */
    .stButton>button:has(p:contains("Actualizar")), 
    .stButton>button:has(span:contains("Actualizar")),
    .stButton>button:has(p:contains("Guardar")), 
    .stButton>button:has(span:contains("Guardar")),
    div[data-testid="stFormSubmitButton"]>button {
        background: linear-gradient(135deg, #0284C7 0%, #00B4D8 100%) !important;
        color: #FFFFFF !important;
        border: 1px solid #00E5FF !important;
        font-weight: 700 !important;
        box-shadow: 0 4px 15px rgba(0, 180, 216, 0.35) !important;
    }
    .stButton>button:has(p:contains("Actualizar")):hover,
    .stButton>button:has(span:contains("Actualizar")):hover,
    .stButton>button:has(p:contains("Guardar")):hover,
    .stButton>button:has(span:contains("Guardar")):hover {
        background: linear-gradient(135deg, #0369A1 0%, #0096C7 100%) !important;
        box-shadow: 0 0 20px rgba(0, 229, 255, 0.6) !important;
        color: #FFFFFF !important;
    }

    /* 3. BOTÓN PELIGROSO: 🗑️ Eliminar Registro (Tono Rojo Advertencia) */
    .stButton>button:has(p:contains("Eliminar")), 
    .stButton>button:has(span:contains("Eliminar")) {
        background: rgba(153, 27, 27, 0.25) !important;
        color: #FCA5A5 !important;
        border: 1px solid rgba(239, 68, 68, 0.5) !important;
    }
    .stButton>button:has(p:contains("Eliminar")):hover,
    .stButton>button:has(span:contains("Eliminar")):hover {
        background: #991B1B !important;
        color: #FFFFFF !important;
        border-color: #EF4444 !important;
        box-shadow: 0 0 15px rgba(239, 68, 68, 0.5) !important;
    }
    div[data-baseweb="input"] input, div[data-baseweb="base-input"] input, div[data-baseweb="textarea"] textarea {
        background-color: #080C14 !important;
        color: #F8FAFC !important;
        border-color: rgba(0, 229, 255, 0.25) !important;
        border-radius: 6px !important;
        font-size: 0.9rem !important;
    } 
    
    /* REGLA BALANCEADA PARA LOS EXPANDERS (CUADROS DE ESTADO) */
    [data-testid="stExpander"] {
        background-color: #080C14 !important;
        border: 1px solid rgba(0, 229, 255, 0.15) !important;
        border-radius: 6px !important;
        margin-top: 3px !important;
        margin-bottom: 3px !important;
    }

    /* REDUCCIÓN CONTROLADA DE ESPACIO EN SIDEBAR */
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        gap: 0.2rem !important;
    }

    [data-testid="stExpander"] summary {
        color: #00E5FF !important;
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        padding-top: 6px !important;
        padding-bottom: 6px !important;
    }

    [data-testid="stCameraInput"] video, 
    [data-testid="stCameraInput"] img {
        width: 100% !important;
        max-width: 640px !important;
        height: auto !important;
        border-radius: 8px !important;
    }
</style>""",
    unsafe_allow_html=True,
)

# 05 SECCION ------------------------------------------------------------------- SISTEMA DE LOGIN CONECTADO A MYSQL -----------------------------------------------------------------------------------------------
if not st.session_state.autenticado:
  st.markdown(
      """
        <div style="display: flex; align-items: center; justify-content: flex-start; gap: 12px; width: 100%; margin-bottom: 20px; margin-top: 0px;">
            <img src="https://raw.githubusercontent.com/Miaa-Aguascalientes/Logos/38504978c8f77a4dac38ad476f74dbdee6af2cad/LogoMIAA.svg" style="width: 180px; height: auto;" />
        </div>
    """,
      unsafe_allow_html=True,
  )

  st.markdown(
      '<h3 style="color: #00E5FF; font-size: 1.4rem; font-weight: 800; margin-bottom: 20px;">Acceso al Sistema - Gestión de Válvulas Reductoras de Presión</h3>',
      unsafe_allow_html=True,
  )

  col_login1, col_login2 = st.columns([1, 2])
  with col_login1:
    with st.form("login_form"):
      usuario_input = st.text_input("Usuario")
      password_input = st.text_input("Contraseña", type="password")
      submit_login = st.form_submit_button(
          "Iniciar Sesión", use_container_width=True
      )

      if submit_login:
        if usuario_input and password_input:
          query_login = """
                        SELECT id, usuario, tipo_usuario, departamento 
                        FROM usuarios_vrp 
                        WHERE usuario = :usu AND password = :pas
                    """
          df_user, err_login = obtener_datos_mysql(
              query_login,
              {"usu": usuario_input.strip(), "pas": password_input.strip()},
          )

          if not err_login and not df_user.empty:
            st.session_state.autenticado = True
            st.session_state.usuario_actual = df_user.iloc[0]["usuario"]
            st.session_state.tipo_usuario = (
                str(df_user.iloc[0]["tipo_usuario"]).strip().lower()
            )
            st.session_state.departamento = df_user.iloc[0]["departamento"]
            st.success("¡Acceso concedido!")
            t.sleep(0.5)
            st.rerun()
          else:
            st.error("Usuario o contraseña incorrectos.")
        else:
          st.warning("Por favor, ingrese usuario y contraseña.")
  st.stop()

# 05.1. SECCION ------------------------------------------------------------- DETERMINAR ROL DEL USUARIO -----------------------------------------------------------------------------------------------------------
es_operador = st.session_state.get("tipo_usuario", "") == "operador"

# 06 SECCION ------------------------------------------------------------ BARRA LATERAL IZQUIERDA (SIDEBAR) --------------------------------------------------------------------------------------------------------
with st.sidebar:

  st.markdown(
      """
        <div style="text-align: center; margin-top: -35px; padding-top: 0px; padding-bottom: 8px; border-bottom: 1px solid rgba(0, 229, 255, 0.15); margin-bottom: 12px;">
            <img src="https://raw.githubusercontent.com/Miaa-Aguascalientes/Logos/38504978c8f77a4dac38ad476f74dbdee6af2cad/LogoMIAA.svg" style="width: 140px; margin-bottom: 0px;" />
        </div>
    """,
      unsafe_allow_html=True,
  )

  st.markdown(
      f"""
        <div style="background: #111A30; border: 1px solid rgba(0, 229, 255, 0.15); border-radius: 8px; padding: 12px; text-align: center; margin-bottom: 15px;">
            <div style="color: #00E5FF; font-weight: 700; font-size: 0.9rem; margin-bottom: 4px;">👤 {st.session_state.usuario_actual}</div>
            <div style="color: #94A3B8; font-size: 0.75rem; text-transform: uppercase;">{st.session_state.get('tipo_usuario', 'usuario')}</div>
        </div>
    """,
      unsafe_allow_html=True,
  )

  # --- MENÚ DE NAVEGACIÓN PROFESIONAL (REEMPLAZO DE ST.RADIO POR BOTONES ACTIVOS) ---
  if es_operador:
    opciones_menu = ["📍 Registros", "🗺️ Mapa", "⚙️ Editar"]
  else:
    opciones_menu = ["📍 Registros", "🗺️ Mapa", "➕ Añadir", "⚙️ Editar"]

  if (
      "active_tab" not in st.session_state
      or st.session_state.active_tab not in opciones_menu
  ):
    st.session_state.active_tab = opciones_menu[0]

  st.markdown(
      "<p style='color: #64748B; font-size: 0.75rem; font-weight: 700;"
      " text-transform: uppercase; margin-bottom: 8px;'>Navegación</p>",
      unsafe_allow_html=True,
  )

  # Renderizar botones limpios sin círculos de radio
  for opcion in opciones_menu:
    es_activa = st.session_state.active_tab == opcion
    # Aplica clase o estilo activo si la pestaña seleccionada coincide
    tipo_btn = "primary" if es_activa else "secondary"

    if st.button(
        opcion,
        key=f"nav_{opcion}",
        use_container_width=True,
        type=tipo_btn,
    ):
      if st.session_state.active_tab != opcion:
        st.session_state.active_tab = opcion
        st.rerun()

  st.markdown(
      "<hr style='border: 0.5px solid rgba(0,229,255,0.2); margin: 15px 0;'>",
      unsafe_allow_html=True,
  )

  # --- DESPLEGABLES DE VÁLVULAS ---
  df_sidebar_valvulas, _ = obtener_datos(
      'SELECT id, estat_valv, domicilio, colonia FROM "Agua_potable"."VPRS"'
  )

  if not df_sidebar_valvulas.empty:
    st.markdown(
        "<p style='color: #00E5FF; font-size: 0.85rem; font-weight: 700;"
        " margin-bottom: 16px; margin-top: 8px;'>📊 Estado de Válvulas</p>",
        unsafe_allow_html=True,
    )

    ICONOS_ESTADO = {
        "Calibrada": "🟢",
        "Abierta": "🔵",
        "Cerrada": "🔴",
        "Dañada": "⛔",
        "Descalibrada": "🟠",
        "Habilitada": "🔷",
        "No opera": "⚫",
        "Pendiente": "⚠️",
    }

    for estado in OPCIONES_ESTADO_VALVULA:
      df_filtro = df_sidebar_valvulas[
          df_sidebar_valvulas["estat_valv"].str.strip().str.lower()
          == estado.lower()
      ]
      conteo = len(df_filtro)
      icono = ICONOS_ESTADO.get(estado, "⚪")

      with st.expander(f"{icono} {estado} ({conteo})"):
        if conteo > 0:
          for _, v_row in df_filtro.iterrows():
            st.markdown(
                f"""
                            <div style="padding: 4px 0; border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 0.78rem;">
                                <strong style="color: #00E5FF;">{v_row['id']}</strong><br>
                                <span style="color: #94A3B8;">📍 {v_row['domicilio'] or 'Sin dom.'}</span>
                            </div>
                            """,
                unsafe_allow_html=True,
            )
        else:
          st.markdown(
              "<span style='color: #64748B; font-size: 0.75rem;'>Sin"
              " registros</span>",
              unsafe_allow_html=True,
          )

  st.markdown("<br>", unsafe_allow_html=True)

  if st.button("Cerrar Sesión", key="btn_logout", use_container_width=True):
    st.session_state.autenticado = False
    st.rerun()

# 07 SECCION ------------------------------------------------------------------------ CABECERA PRINCIPAL ---------------------------------------------------------------------------------------------------------
st.markdown(
    """
    <div style="text-align: center; margin-bottom: 10px; margin-top: 0px;">
        <h1 style="color: #00E5FF; font-size: 1.8rem; font-weight: 800; margin: 0; letter-spacing: -0.5px;">Gestion valvular reductoras de presión</h1>
    </div>
""",
    unsafe_allow_html=True,
)

st.markdown(
    "<hr style='border: 0.5px solid rgba(0,229,255,0.2); margin: 10px 0;'>",
    unsafe_allow_html=True,
)

COLUMNAS_VPRS = """
    fid, id_0, id, serie, diametro, marca_valv, model_valv, marca_trim, domicilio, colonia, 
    cota_terr, sector_hid, cal_ant_d, cal_ant_n, fecha_ult_, cal_act_d, cal_act_n, 
    hora_cal, estat_valv, observ, fotos, fotos_2,
    ST_X(geom) as coord_x, ST_Y(geom) as coord_y
"""

# 08 SECCION ---------------------------------------------------------------------------- VER REGISTROS (VPRS) ------------------------------------------------------------------------------------------------

if st.session_state.active_tab == "📍 Registros":

  # 1. INYECCIÓN CSS PARA DISEÑO DE PESTAÑAS TIPO FOLDER/FICHA
  st.markdown(
      """
        <style>
        div[data-baseweb="tab-list"] {
            gap: 2px;
            background-color: #5B63B7;
            padding: 4px 4px 0px 4px;
            border-radius: 6px 6px 0px 0px;
        }

        div[data-baseweb="tab-list"] button {
            background-color: #8C93D3 !important;
            color: #FFFFFF !important;
            font-weight: bold !important;
            border-radius: 6px 6px 0px 0px !important;
            padding: 10px 20px !important;
            border: none !important;
            margin-right: 2px !important;
        }

        div[data-baseweb="tab-list"] button[aria-selected="true"] {
            background-color: #FFFFFF !important;
            color: #4A52A0 !important;
            border-top: 3px solid #3F468F !important;
        }

        div[data-baseweb="tab-highlight"] {
            background-color: transparent !important;
        }
        </style>
        """,
      unsafe_allow_html=True,
  )

  # 2. DEFINICIÓN DE LAS 4 PESTAÑAS
  tab_registros, tab_bd_completa, tab_sheets, tab_comparativa = st.tabs([
      "📍 Registros",
      "🗄️ Tabla Base de Datos Completa",
      "📊 2.Informe visitas a VRP´s (Sheets)",
      "🔍 Comparativa (BD vs Sheets)",
  ])

  # =========================================================================
  # PESTAÑA 1: VISTA DE REGISTROS (Búsqueda y Tarjetas con fotos)
  # =========================================================================
  with tab_registros:
    busqueda = st.text_input(
        "🔍 Buscar válvula (ID, Serie, Domicilio, Col.):",
        placeholder="Ej. VF01, Centro...",
    )

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
      query = (
          f'SELECT {COLUMNAS_VPRS} FROM "Agua_potable"."VPRS" ORDER BY fid'
          " LIMIT 15"
      )
      df_vprs, error_db = obtener_datos(query)

    if error_db:
      st.error(f"❌ Error al consultar PostgreSQL: {error_db}")
    elif not df_vprs.empty:
      if not busqueda or busqueda.strip() == "":
        st.markdown(
            "<p style='color: #94A3B8; font-size: 0.85rem; margin-bottom:"
            " 10px;'>Mostrando primeros 15 registros.</p>",
            unsafe_allow_html=True,
        )
      else:
        st.markdown(
            f"<p style='color: #94A3B8; font-size: 0.85rem; margin-bottom:"
            f" 10px;'>Se encontraron {len(df_vprs)} registros.</p>",
            unsafe_allow_html=True,
        )

      for idx, row in df_vprs.iterrows():
        serie_val = row["serie"]
        serie_texto = (
            ""
            if (
                pd.isna(serie_val)
                or str(serie_val).strip().lower() in ["nan", "none", ""]
            )
            else f" | Serie: {serie_val}"
        )

        card_html = f"""
                    <div class="user-card">
                        <span style="font-size: 0.95rem; font-weight: bold; color: #F8FAFC;">ID: {row['id']}{serie_texto}</span><br>
                        <span style="color: #00E5FF; font-size: 0.85rem;">📍 {row['domicilio'] or 'Sin domicilio'}, Col. {row['colonia'] or 'Sin colonia'}</span>
                    </div>
                """
        st.markdown(card_html, unsafe_allow_html=True)

        with st.expander("🔍 Ver detalles completos y fotografías"):
          geom_str = (
              f"POINT ({row['coord_x']} {row['coord_y']})"
              if pd.notna(row["coord_x"]) and pd.notna(row["coord_y"])
              else "Sin geometría"
          )
          detalle_html = f"""
                        <span style="color: #94A3B8; font-size: 0.8rem; line-height: 1.6;">
                            <b>Diámetro:</b> {row['diametro']} pulgadas &nbsp;|&nbsp; <b>Marca:</b> {row['marca_valv']} &nbsp;|&nbsp; <b>Modelo:</b> {row['model_valv']} &nbsp;|&nbsp; <b>Trim:</b> {row['marca_trim']} &nbsp;|&nbsp; <b>Cota:</b> {row['cota_terr']}<br>
                            <b>Sector:</b> {row['sector_hid']} &nbsp;|&nbsp; <b>Estado:</b> {row['estat_valv']} &nbsp;|&nbsp; <b>Hora Cal:</b> {row['hora_cal']} &nbsp;|&nbsp; <b>Última Actualización:</b> {row['fecha_ult_']}<br>
                            <b>Geom:</b> {geom_str}<br>
                            <b>Cal Anterior Día:</b> {row['cal_ant_d']} kg/cm &nbsp;|&nbsp; <b>Cal Anterior Noche:</b> {row['cal_ant_n']} kg/cm<br>
                            <b>Cal Actual Día:</b> {row['cal_act_d']} kg/cm &nbsp;|&nbsp; <b>Cal Actual Noche:</b> {row['cal_act_n']} kg/cm<br>
                            <b>Observaciones:</b> {row['observ']}
                        </span>
                    """
          st.markdown(detalle_html, unsafe_allow_html=True)

          col_img1, col_img2 = st.columns(2)
          with col_img1:
            img_bytes = procesar_bytes_foto(row["fotos"])
            if img_bytes is not None and len(img_bytes) > 0:
              st.markdown(
                  "<p style='color: #00E5FF; font-size: 0.85rem; margin-top:"
                  " 10px; margin-bottom: 5px;'>📸 Fotografía 1:</p>",
                  unsafe_allow_html=True,
              )
              st.image(
                  img_bytes,
                  caption=f"ID: {row['id']} (Foto 1)",
                  use_container_width=True,
              )

          with col_img2:
            img_bytes_2 = procesar_bytes_foto(row["fotos_2"])
            if img_bytes_2 is not None and len(img_bytes_2) > 0:
              st.markdown(
                  "<p style='color: #00E5FF; font-size: 0.85rem; margin-top:"
                  " 10px; margin-bottom: 5px;'>📸 Fotografía 2:</p>",
                  unsafe_allow_html=True,
              )
              st.image(
                  img_bytes_2,
                  caption=f"ID: {row['id']} (Foto 2)",
                  use_container_width=True,
              )
    else:
      st.info("No se encontraron registros.")

  # =========================================================================
  # PESTAÑA 2: TABLA BASE DE DATOS COMPLETA (PostgreSQL)
  # =========================================================================
  with tab_bd_completa:
    st.markdown("### Tabla Completa de VPRS (Base de Datos)")

    query_completa = (
        f'SELECT {COLUMNAS_VPRS} FROM "Agua_potable"."VPRS" ORDER BY fid ASC;'
    )
    df_completo, err_bd_comp = obtener_datos(query_completa)

    if err_bd_comp:
      st.error(f"❌ Error al consultar la base de datos: {err_bd_comp}")
    elif not df_completo.empty:
      st.dataframe(
          df_completo, use_container_width=True, hide_index=True, height=650
      )
      st.caption(f"Total de registros en base de datos: {len(df_completo)}")
    else:
      st.warning("⚠️ No se encontraron registros en la base de datos.")

  # =========================================================================
  # PESTAÑA 3: GOOGLE SHEETS EN VIVO Y EDITABLE EN LA PESTAÑA ESPECÍFICA
  # =========================================================================
  with tab_sheets:
    st.markdown("### Hoja de Cálculo: 2.Informe visitas a VRP´s")

    sheet_url_editable = "https://docs.google.com/spreadsheets/d/1am_DvVrUYPYqXnH8Pt3xoeMuG6BFr4z2x8PBRNskB-M/edit?rm=embedded&gid=769091515#gid=769091515"

    st.markdown(
        f"""
        <iframe 
            src="{sheet_url_editable}" 
            style="width: 100%; height: 80vh; border: 1px solid #334155; border-radius: 0px 0px 8px 8px;" 
            allowfullscreen>
        </iframe>
        """,
        unsafe_allow_html=True,
    )

    st.link_button(
        "🔗 Abrir hoja directamente en pestaña de Google Sheets",
        "https://docs.google.com/spreadsheets/d/1am_DvVrUYPYqXnH8Pt3xoeMuG6BFr4z2x8PBRNskB-M/edit#gid=769091515",
    )

  # =========================================================================
  # PESTAÑA 4: COMPARATIVA Y AUDITORÍA DE DATOS (BD vs CSV DE PESTAÑA 769091515)
  # =========================================================================
  with tab_comparativa:
    st.markdown(
        "### 🔍 Auditoría y Comparativa: BD vs Hoja '2.Informe visitas a VRP´s'"
    )
    st.info(
        "📌 **Prioridad:** Base de Datos. Esta herramienta evalúa la pestaña"
        " específica de Sheets frente a PostgreSQL independientemente de"
        " mayúsculas o minúsculas en 'ID'."
    )

    if st.button("🔄 Ejecutar Comparación de Datos"):
      with st.spinner("Procesando datos de la pestaña especificada..."):
        # 1. Obtener datos de la Base de Datos (PostgreSQL)
        query_audit = f'SELECT {COLUMNAS_VPRS} FROM "Agua_potable"."VPRS";'
        df_bd, err_audit_bd = obtener_datos(query_audit)

        # 2. Descargar en formato CSV forzando la GID exacta (769091515)
        csv_sheets_url = "https://docs.google.com/spreadsheets/d/1am_DvVrUYPYqXnH8Pt3xoeMuG6BFr4z2x8PBRNskB-M/gviz/tq?tqx=out:csv&gid=769091515"

        try:
          df_sheets = pd.read_csv(csv_sheets_url)
          err_sheets = None
        except Exception as e:
          err_sheets = str(e)
          df_sheets = pd.DataFrame()

        if err_audit_bd:
          st.error(f"❌ Error al consultar la Base de Datos: {err_audit_bd}")
        elif err_sheets:
          st.error(
              f"❌ Error al descargar datos de la pestaña de Sheets:"
              f" {err_sheets}."
          )
        else:
          # --- A. BÚSQUEDA INSENSIBLE A MAYÚSCULAS DE LA COLUMNA DE IDENTIFICADORES ---
          col_id_sheets = [
              c for c in df_sheets.columns if str(c).strip().lower() == "id"
          ]
          col_id_bd = [
              c for c in df_bd.columns if str(c).strip().lower() == "id"
          ]

          if not col_id_sheets:
            st.error(
                "❌ No se encontró la columna 'ID' o 'id' en la pestaña de"
                " Sheets."
                f" Columnas detectadas: {list(df_sheets.columns)}"
            )
          elif not col_id_bd:
            st.error(
                "❌ No se encontró la columna 'id' en la consulta de la Base de"
                " Datos."
            )
          else:
            name_id_sheets = col_id_sheets[0]
            name_id_bd = col_id_bd[0]

            # --- B. NORMALIZACIÓN DE REGISTROS (Limpieza de espacios y estandarización a Mayúsculas) ---
            df_bd["id_clean"] = (
                df_bd[name_id_bd].astype(str).str.strip().str.upper()
            )
            df_sheets["id_clean"] = (
                df_sheets[name_id_sheets].astype(str).str.strip().str.upper()
            )

            # Eliminar posibles filas completamente vacías o IDs nulos ('NAN', 'NONE', '')
            df_bd = df_bd[~df_bd["id_clean"].isin(["NAN", "NONE", ""])]
            df_sheets = df_sheets[~df_sheets["id_clean"].isin(["NAN", "NONE", ""])]

            ids_bd = set(df_bd["id_clean"].unique())
            ids_sheets = set(df_sheets["id_clean"].unique())

            # --- C. DETECCIÓN DE REGISTROS ---
            ids_solo_sheets = ids_sheets - ids_bd
            df_solo_sheets = df_sheets[
                df_sheets["id_clean"].isin(ids_solo_sheets)
            ]

            ids_solo_bd = ids_bd - ids_sheets
            df_solo_bd = df_bd[df_bd["id_clean"].isin(ids_solo_bd)]

            ids_comunes = ids_bd.intersection(ids_sheets)

            # --- D. MÉTRICAS GENERALES ---
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            col_m1.metric("Registros BD", len(ids_bd))
            col_m2.metric("Registros en Pestaña Sheets", len(ids_sheets))
            col_m3.metric(
                "⚠️ En Sheets y NO en BD",
                len(ids_solo_sheets),
                delta_color="inverse",
            )
            col_m4.metric("Coinciden en ID", len(ids_comunes))

            st.markdown("---")

            # --- SECCIÓN A: REGISTROS EN SHEETS QUE FALTAN EN LA BD ---
            st.markdown(
                "#### 🚨 1. Registros presentes en '2.Informe visitas a VRP´s'"
                " que NO existen en la Base de Datos"
            )
            if not df_solo_sheets.empty:
              st.warning(
                  f"Se encontraron **{len(df_solo_sheets)}** registros en la"
                  " pestaña de Sheets que no están registrados en PostgreSQL:"
              )
              cols_mostrar_sheets = [
                  c for c in df_solo_sheets.columns if c != "id_clean"
              ]
              st.dataframe(
                  df_solo_sheets[cols_mostrar_sheets],
                  use_container_width=True,
                  hide_index=True,
              )
            else:
              st.success(
                  "✅ Todos los registros de la pestaña de Sheets existen en la"
                  " Base de Datos."
              )

            # --- SECCIÓN B: REGISTROS EN LA BD QUE NO ESTÁN EN SHEETS ---
            with st.expander("ℹ️ 2. Registros en Base de Datos que FALTAN en Sheets"):
              if not df_solo_bd.empty:
                st.info(
                    f"Hay **{len(df_solo_bd)}** registros de PostgreSQL que no"
                    " se encuentran en la pestaña de Sheets:"
                )
                cols_mostrar_bd = [
                    c for c in df_bd.columns if c != "id_clean"
                ]
                st.dataframe(
                    df_solo_bd[cols_mostrar_bd],
                    use_container_width=True,
                    hide_index=True,
                )
              else:
                st.success(
                    "✅ Todos los registros de la Base de Datos están"
                    " presentes en la pestaña de Sheets."
                )

            # --- SECCIÓN C: COMPARACIÓN DE VALORES EN COLUMNAS COINCIDENTES ---
            with st.expander("🔍 3. Diferencias de atributos en IDs comunes"):
              # Mapeo de nombres de columnas en minúsculas para compararlos sin importar mayúsculas/minúsculas
              cols_map_bd = {
                  str(c).strip().lower(): c
                  for c in df_bd.columns
                  if c not in ["id_clean", name_id_bd]
              }
              cols_map_sh = {
                  str(c).strip().lower(): c
                  for c in df_sheets.columns
                  if c not in ["id_clean", name_id_sheets]
              }

              columnas_comunes_keys = list(
                  set(cols_map_bd.keys()).intersection(set(cols_map_sh.keys()))
              )

              if not columnas_comunes_keys:
                st.caption(
                    "No se detectaron nombres de columnas adicionales coincidentes"
                    " entre ambas fuentes para comparar contenido campo a"
                    " campo."
                )
              else:
                df_merged = pd.merge(
                    df_bd,
                    df_sheets,
                    on="id_clean",
                    suffixes=("_BD", "_Sheets"),
                )
                diferencias_list = []

                for key_col in columnas_comunes_keys:
                  col_bd_real = cols_map_bd[key_col]
                  col_sh_real = cols_map_sh[key_col]

                  # Ajuste de sufijos tras el merge
                  col_bd_name = (
                      f"{col_bd_real}_BD"
                      if col_bd_real in df_sheets.columns
                      else col_bd_real
                  )
                  col_sh_name = (
                      f"{col_sh_real}_Sheets"
                      if col_sh_real in df_bd.columns
                      else col_sh_real
                  )

                  if (
                      col_bd_name in df_merged.columns
                      and col_sh_name in df_merged.columns
                  ):
                    mask_diff = (
                        df_merged[col_bd_name]
                        .fillna("")
                        .astype(str)
                        .str.strip()
                        .str.lower()
                        != df_merged[col_sh_name]
                        .fillna("")
                        .astype(str)
                        .str.strip()
                        .str.lower()
                    )
                    df_diff = df_merged[mask_diff]

                    if not df_diff.empty:
                      for _, row_d in df_diff.iterrows():
                        diferencias_list.append({
                            "ID Válvula": row_d["id_clean"],
                            "Campo": col_bd_real,
                            "Valor en BD (Prioritario)": row_d[col_bd_name],
                            "Valor en Sheets": row_d[col_sh_name],
                        })

                if diferencias_list:
                  df_diff_final = pd.DataFrame(diferencias_list)
                  st.warning(
                      f"Se detectaron **{len(df_diff_final)}** diferencias en"
                      " campos para registros con el mismo ID:"
                  )
                  st.dataframe(
                      df_diff_final,
                      use_container_width=True,
                      hide_index=True,
                  )
                else:
                  st.success(
                      "✅ Los valores en las columnas coincidentes son"
                      " idénticos para todos los IDs en común."
                  )

# 09 SECCION ------------------------------------------------------------ MAPA DE VRPs Y SECTORES HIDRÁULICOS (POSTGIS) -----------------------------------------------------------------------------------------

elif st.session_state.active_tab == "🗺️ Mapa":
  # 9.1. CONSULTA DE VÁLVULAS (VPRs)
  query_mapa = """
        SELECT 
            id,
            estat_valv,
            domicilio,
            colonia,
            ST_X(geom) as x,
            ST_Y(geom) as y
        FROM "Agua_potable"."VPRS"
        WHERE geom IS NOT NULL;
    """
  df_mapa, err_mapa = obtener_datos(query_mapa)

  # 9.2. CONSULTA DE SECTORES HIDRÁULICOS
  query_sectores = """
        SELECT 
            fid,
            sector,
            ST_AsGeoJSON(ST_Transform(geom, 4326)) as geojson
        FROM "Sectorizacion"."Sectores_hidr"
        WHERE geom IS NOT NULL;
    """
  df_sectores, err_sectores = obtener_datos(query_sectores)

  if err_mapa:
    st.error(f"❌ Error al cargar datos espaciales de VPRs: {err_mapa}")
  else:
    CONFIG_ESTADOS = {
        "calibrada": {"color": "#2ECC71", "emoji": "🟢", "forma": "circulo"},
        "abierta": {"color": "#3498DB", "emoji": "🔵", "forma": "circulo"},
        "cerrada": {"color": "#E74C3C", "emoji": "🔴", "forma": "circulo"},
        "dañada": {"color": "#E84393", "emoji": "⛔", "forma": "circulo"},
        "descalibrada": {"color": "#F1C40F", "emoji": "⚠️", "forma": "triangulo"},
        "habilitada": {"color": "#38B6FF", "emoji": "🔷", "forma": "rombo"},
        "no opera": {"color": "#A0A0A0", "emoji": "⚫", "forma": "circulo"},
        "pendiente": {"color": "#F1C40F", "emoji": "⚠️", "forma": "triangulo"},
        "amarillo": {"color": "#F1C40F", "emoji": "🟡", "forma": "circulo"},
    }

    m = folium.Map(
        location=[21.8853, -102.2916], zoom_start=13, control_scale=True
    )

    agregar_capas_base_mapa(m)
    Fullscreen().add_to(m)

    # 9.3. --- DIBUJAR SECTORES HIDRÁULICOS ---
    fg_sectores = folium.FeatureGroup(
        name="📐 Sectores Hidráulicos", show=True
    )

    if not err_sectores and not df_sectores.empty:
      import json

      def estilo_final_sector(feature):
        props = feature.get("properties", {})
        nombre_actual = props.get("sector")
        sec_sel = st.session_state.get("sector_resaltado")

        es_match = (
            sec_sel is not None and nombre_actual == sec_sel.get("sector")
        )
        afectacion_val = props.get("afectacion", 0)
        color_dinamico = props.get("color_dinamico", "#2980B9")

        fill_color_final = "#F1C40F" if es_match else color_dinamico

        if es_match:
          border_color_final = "#F39C12"
          weight_final = 3
          opacity_final = 0.5
        elif afectacion_val > 0:
          border_color_final = color_dinamico
          weight_final = 2.5
          opacity_final = 0.25
        else:
          border_color_final = "#2980B9"
          weight_final = 1
          opacity_final = 0.08

        return {
            "fillColor": fill_color_final,
            "color": border_color_final,
            "weight": weight_final,
            "fillOpacity": opacity_final,
        }

      def estilo_hover_sector(feature):
        return {"fillOpacity": 0.12, "weight": 2, "color": "#FFFFFF"}

      for _, sec_row in df_sectores.iterrows():
        try:
          geom_json = json.loads(sec_row["geojson"])

          feature_estructurado = {
              "type": "Feature",
              "geometry": geom_json,
              "properties": {
                  "sector": str(sec_row.get("sector", "Sin Nombre")),
                  "fid": sec_row.get("fid"),
                  "afectacion": 0,
                  "color_dinamico": "#2980B9",
              },
          }

          folium.GeoJson(
              feature_estructurado,
              style_function=estilo_final_sector,
              highlight_function=estilo_hover_sector,
              tooltip=folium.GeoJsonTooltip(
                  fields=["sector"],
                  aliases=["Sector:"],
                  localize=True,
                  sticky=True,
              ),
          ).add_to(fg_sectores)
        except Exception:
          continue

    fg_sectores.add_to(m)

    # 9.4. --- DIBUJAR VÁLVULAS (VRPs) ---
    grupos_capas = {}
    success_count = 0

    if not df_mapa.empty:
      for estado_opc in OPCIONES_ESTADO_VALVULA:
        count_est = len(
            df_mapa[
                df_mapa["estat_valv"].str.strip().str.lower()
                == estado_opc.lower()
            ]
        )
        conf = CONFIG_ESTADOS.get(
            estado_opc.lower(),
            {"color": "#95A5A6", "emoji": "⚪", "forma": "circulo"},
        )

        fg = folium.FeatureGroup(
            name=f"{conf['emoji']} {estado_opc} ({count_est})", show=True
        )
        fg.add_to(m)
        grupos_capas[estado_opc.lower()] = fg

      fg_otros = folium.FeatureGroup(name="⚪ Otros / Sin Estado", show=True)
      fg_otros.add_to(m)

      for _, row in df_mapa.iterrows():
        try:
          lon, lat = transformer_to_latlon.transform(row["x"], row["y"])
          estado_raw = str(row["estat_valv"] or "Desconocido").strip()
          estado_key = estado_raw.lower()
          id_vrp = str(row["id"])

          conf_punto = CONFIG_ESTADOS.get(
              estado_key, {"color": "#95A5A6", "emoji": "⚪", "forma": "circulo"}
          )
          color_hex = conf_punto["color"]
          emoji_punto = conf_punto["emoji"]
          tipo_forma = conf_punto["forma"]

          grupo_destino = grupos_capas.get(estado_key, fg_otros)

          if tipo_forma == "triangulo":
            simbolo_html = f'<span style="font-size: 13px; line-height: 1; filter: drop-shadow(0 0 3px {color_hex});">⚠️</span>'
          elif tipo_forma == "rombo":
            simbolo_html = f"""
                        <span style="
                            height: 10px; 
                            width: 10px; 
                            background-color: {color_hex}; 
                            transform: rotate(45deg); 
                            display: inline-block;
                            box-shadow: 0 0 5px {color_hex};
                        "></span>"""
          else:
            simbolo_html = f"""
                        <span style="
                            height: 10px; 
                            width: 10px; 
                            background-color: {color_hex}; 
                            border-radius: 50%; 
                            display: inline-block;
                            box-shadow: 0 0 5px {color_hex};
                        "></span>"""

          popup_html = f"""
                    <div style="font-size: 0.85rem; color: #000; font-family: sans-serif;">
                        <b>ID:</b> {id_vrp}<br>
                        <b>Estado:</b> {emoji_punto} {estado_raw}<br>
                        <b>Ubicación:</b> {row['domicilio'] or 'Sin domicilio'}, Col. {row['colonia'] or 'Sin colonia'}
                    </div>
                    """

          icon_html = f"""
                    <div style="display: flex; align-items: center; white-space: nowrap;">
                        {simbolo_html}
                        <span style="
                            color: {color_hex}; 
                            font-size: 11px; 
                            font-weight: bold; 
                            font-family: monospace, sans-serif;
                            margin-left: 6px; 
                            text-shadow: 1px 1px 2px #000, -1px -1px 2px #000, 1px -1px 2px #000, -1px 1px 2px #000;
                        ">{id_vrp}</span>
                    </div>
                    """

          folium.Marker(
              location=[lat, lon],
              icon=folium.DivIcon(
                  html=icon_html, icon_size=(150, 16), icon_anchor=(5, 8)
              ),
              popup=folium.Popup(popup_html, max_width=300),
          ).add_to(grupo_destino)

          success_count += 1
        except Exception:
          continue

    folium.LayerControl(collapsed=False).add_to(m)

    # 9.5. --- INYECCIÓN CSS Y RENDERIZADO DEL MAPA ---
    # Inyectamos el estilo para forzar al iframe de streamlit_folium a tomar el 85% del alto de la ventana
    st.markdown(
        """
        <style>
        iframe[title="streamlit_folium.st_folium"] {
            height: 85vh !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Se conserva el height alto en px como fallback
    st_folium(m, width="100%", height=800, returned_objects=[])

    total_sectores = len(df_sectores) if not df_sectores.empty else 0
    st.markdown(
        f"<p style='color: #94A3B8; font-size: 0.85rem; margin-top: 10px;'>Se"
        f" renderizaron {total_sectores} sectores hidráulicos y"
        f" {success_count} VRPs georreferenciadas.</p>",
        unsafe_allow_html=True,
    )
# 10 SECCION --------------------------------------------------------------------- AÑADIR NUEVA VÁLVULA (ACOMODO IDÉNTICO A EDITAR) -----------------------------------------------------------------------

elif st.session_state.active_tab == "➕ Añadir":
    if es_operador:
        st.error(
            "⛔ El perfil de operador no tiene permisos para dar de alta nueva"
            " infraestructura."
        )
        st.stop()

    df_max_id0, err_max = obtener_datos(
        'SELECT MAX(id_0) as max_id FROM "Agua_potable"."VPRS"'
    )
    siguiente_id_0 = 1
    if (
        not err_max
        and not df_max_id0.empty
        and df_max_id0["max_id"].iloc[0] is not None
    ):
        try:
            siguiente_id_0 = int(df_max_id0["max_id"].iloc[0]) + 1
        except Exception:
            siguiente_id_0 = 1

    # Inicialización segura de coordenadas en session_state
    if "add_coord_x_input" not in st.session_state:
        st.session_state["add_coord_x_input"] = 0.0
    if "add_coord_y_input" not in st.session_state:
        st.session_state["add_coord_y_input"] = 0.0

    # FILA 1 (4 columnas)
    a_c1, a_c2, a_c3, a_c4 = st.columns(4)
    with a_c1:
        st.text_input(
            "ID_0 (Registro)",
            value=str(siguiente_id_0),
            disabled=True,
            key="add_id_0_bloq",
        )
        val_id_0 = siguiente_id_0
    with a_c2:
        val_id = st.text_input("ID VRP *Obligatorio", key="add_id")
    with a_c3:
        val_cota = st.number_input("Cota Terreno", value=0.0, key="add_cota")
    with a_c4:
        val_marca = st.text_input("Marca Valvula", key="add_marca")

    # FILA 2 (4 columnas)
    a_c5, a_c6, a_c7, a_c8 = st.columns(4)
    with a_c5:
        val_serie = st.text_input("Serie de la Valvula", key="add_serie")
    with a_c6:
        val_diametro = st.number_input(
            "Diámetro", min_value=0, value=0, key="add_diam"
        )
    with a_c7:
        val_modelo = st.text_input("Modelo Valvula", key="add_modelo")
    with a_c8:
        val_trim = st.text_input("Marca Trim", key="add_trim")

    # FILA 3 (4 columnas)
    a_c9, a_c10, a_c11, a_c12 = st.columns(4)
    with a_c9:
        val_domicilio = st.text_input("Domicilio", key="add_dom")
    with a_c10:
        val_colonia = st.text_input("Colonia", key="add_col")
    with a_c11:
        val_estat = st.selectbox(
            "Estado de la Válvula",
            options=OPCIONES_ESTADO_VALVULA,
            index=0,
            key="add_estat",
        )
    with a_c12:
        val_sector = st.text_input("Sector Hidráulico", key="add_sector")

    # FILA 4 (Coordenadas y Calibraciones | Mapa)
    col_coord_left, col_map_right = st.columns([1, 1])

    with col_map_right:
        st.markdown(
            "<p style='color: #00E5FF; font-size: 0.8rem; font-weight: 700;"
            " margin-top: 0px;'>🗺️ Ubicación Geográfica (geom) - Haga clic en el"
            " mapa para establecer coordenadas automáticamente</p>",
            unsafe_allow_html=True,
        )
        try:
            if (
                st.session_state["add_coord_x_input"] != 0.0
                and st.session_state["add_coord_y_input"] != 0.0
            ):
                lon_add, lat_add = transformer_to_latlon.transform(
                    st.session_state["add_coord_x_input"],
                    st.session_state["add_coord_y_input"],
                )
                m_add = folium.Map(
                    location=[lat_add, lon_add], zoom_start=16, control_scale=True
                )
            else:
                m_add = folium.Map(
                    location=[21.8853, -102.2916], zoom_start=12, control_scale=True
                )

            agregar_capas_base_mapa(m_add)
            Fullscreen().add_to(m_add)

            if (
                st.session_state["add_coord_x_input"] != 0.0
                and st.session_state["add_coord_y_input"] != 0.0
            ):
                folium.Marker(
                    location=[lat_add, lon_add],
                    popup="Nueva VRP",
                    icon=folium.Icon(color="cyan", icon="info-sign"),
                ).add_to(m_add)

            folium.LayerControl(collapsed=False).add_to(m_add)
            map_data_add = st_folium(
                m_add,
                width="100%",
                height=325,
                key="map_add_preview",
                returned_objects=["last_clicked"],
            )

            if map_data_add and map_data_add.get("last_clicked"):
                lat_c = map_data_add["last_clicked"]["lat"]
                lon_c = map_data_add["last_clicked"]["lng"]
                utm_x, utm_y = transformer_to_utm.transform(lon_c, lat_c)
                new_x = round(utm_x, 2)
                new_y = round(utm_y, 3)
                if (
                    st.session_state["add_coord_x_input"] != new_x
                    or st.session_state["add_coord_y_input"] != new_y
                ):
                    st.session_state["add_coord_x_input"] = new_x
                    st.session_state["add_coord_y_input"] = new_y
                    st.rerun()

        except Exception as e_map_add:
            st.info(
                "Haga clic en el mapa para establecer la posición geográfica."
                f" ({e_map_add})"
            )

    with col_coord_left:
        cx1, cx2 = st.columns(2)
        with cx1:
            val_coord_x = st.number_input(
                "Coordenada X",
                format="%.2f",
                key="add_coord_x_input",
            )
        with cx2:
            val_coord_y = st.number_input(
                "Coordenada Y",
                format="%.3f",
                key="add_coord_y_input",
            )

        # Hora Cal, Cal Anterior Noche
        cc1, cc2 = st.columns(2)
        with cc1:
            val_hora = st.text_input("Hora de Calibración", key="add_hora")
        with cc2:
            val_cal_ant_n = st.text_input(
                "Calibración Anterior Noche (kg/cm)", key="add_cann"
            )

        # Cal Anterior Día, Cal Actual Día
        cc3, cc4 = st.columns(2)
        with cc3:
            val_cal_ant_d = st.text_input("Calibración Anterior Día (kg/cm)", key="add_cand")
        with cc4:
            val_cal_act_d = st.text_input("Calibración Actual Día (kg/cm)", key="add_cactd")

        # Cal Actual Noche, Fecha última actualización
        cc5, cc6 = st.columns(2)
        with cc5:
            val_cal_act_n = st.text_input("Calibración Actual Noche (kg/cm)", key="add_cactn")
        with cc6:
            val_fecha_obj = st.date_input(
                "Fecha última actualización",
                value=datetime.date.today(),
                format="DD/MM/YYYY",
                key="add_fecha",
            )
            val_fecha = val_fecha_obj.strftime("%d/%m/%Y")

    # FILA 5: Observaciones
    val_observ = st.text_area("Observaciones", key="add_obs")

    st.markdown(
        "<hr style='border: 0.3px solid rgba(0,229,255,0.2); margin: 15px 0;'>",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<h4 style="color: #00E5FF; font-size: 1rem; font-weight: 700;">📸'
        " Registro de Fotografías</h4>",
        unsafe_allow_html=True,
    )

    col_foto1, col_foto2 = st.columns(2)

    with col_foto1:
        st.markdown(
            "<p style='font-weight: 600; font-size: 0.85rem;'>Fotografía 1</p>",
            unsafe_allow_html=True,
        )
        origen_foto_1 = st.radio(
            "Origen Foto 1",
            ["📁 Seleccionar Archivo", "📷 Usar Cámara"],
            key="origen_foto_1",
            horizontal=True,
            label_visibility="collapsed"
        )
        
        foto_input_1 = None
        if origen_foto_1 == "📁 Seleccionar Archivo":
            foto_input_1 = st.file_uploader(
                "Subir Fotografía 1",
                type=["png", "jpg", "jpeg"],
                key="file_uploader_1"
            )
        else:
            foto_input_1 = st.camera_input(
                "Capturar Fotografía 1",
                key="camara_nuevo_1",
                label_visibility="collapsed"
            )

    with col_foto2:
        st.markdown(
            "<p style='font-weight: 600; font-size: 0.85rem;'>Fotografía 2</p>",
            unsafe_allow_html=True,
        )
        origen_foto_2 = st.radio(
            "Origen Foto 2",
            ["📁 Seleccionar Archivo", "📷 Usar Cámara"],
            key="origen_foto_2",
            horizontal=True,
            label_visibility="collapsed"
        )
        
        foto_input_2 = None
        if origen_foto_2 == "📁 Seleccionar Archivo":
            foto_input_2 = st.file_uploader(
                "Subir Fotografía 2",
                type=["png", "jpg", "jpeg"],
                key="file_uploader_2"
            )
        else:
            foto_input_2 = st.camera_input(
                "Capturar Fotografía 2",
                key="camara_nuevo_2",
                label_visibility="collapsed"
            )

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button(
        "💾 Guardar Nuevo Registro VPRS",
        key="btn_guardar_nuevo",
        use_container_width=True,
    ):
        if val_id:
            try:
                foto_bytes = (
                    foto_input_1.getvalue() if foto_input_1 is not None else None
                )
                foto_bytes_2 = (
                    foto_input_2.getvalue() if foto_input_2 is not None else None
                )

                sql_insert = """
                    INSERT INTO "Agua_potable"."VPRS" (
                        id_0, id, serie, diametro, marca_valv, model_valv, marca_trim, domicilio, colonia, 
                        cota_terr, sector_hid, cal_ant_d, cal_ant_n, fecha_ult_, cal_act_d, cal_act_n, 
                        hora_cal, estat_valv, observ, fotos, fotos_2, geom
                    ) VALUES (
                        :id_0, :id, :serie, :diametro, :marca_valv, :model_valv, :marca_trim, :domicilio, :colonia, 
                        :cota_terr, :sector_hid, :cal_ant_d, :cal_ant_n, :fecha_ult_, :cal_act_d, :cal_act_n, 
                        :hora_cal, :estat_valv, :observ, :fotos, :fotos_2, 
                        ST_SetSRID(ST_MakePoint(:coord_x, :coord_y), 32613)
                    )
                """
                ejecutar_sql(
                    sql_insert,
                    {
                        "id_0": val_id_0,
                        "id": val_id,
                        "serie": val_serie if val_serie.strip() != "" else None,
                        "diametro": val_diametro,
                        "marca_valv": val_marca,
                        "model_valv": val_modelo,
                        "marca_trim": val_trim,
                        "domicilio": val_domicilio,
                        "colonia": val_colonia,
                        "cota_terr": val_cota,
                        "sector_hid": val_sector,
                        "cal_ant_d": val_cal_ant_d,
                        "cal_ant_n": val_cal_ant_n,
                        "fecha_ult_": val_fecha,
                        "cal_act_d": val_cal_act_d,
                        "cal_act_n": val_cal_act_n,
                        "hora_cal": val_hora,
                        "estat_valv": val_estat,
                        "observ": val_observ,
                        "fotos": foto_bytes,
                        "fotos_2": foto_bytes_2,
                        "coord_x": val_coord_x,
                        "coord_y": val_coord_y,
                    },
                )
                st.success("¡Válvula registrada con éxito!")
                t.sleep(1)
                st.rerun()
            except Exception as ex:
                st.error(f"Error al insertar: {ex}")
        else:
            st.warning("El campo ID es obligatorio.")

# 11 -----------------------------------------------------------------  EDITAR Y ELIMINAR (LAYOUT EXACTO SOLICITADO) ----------------------------------------------------------------------------------------------

elif st.session_state.active_tab == "⚙️ Editar":
    # 1. Definimos una columna para el buscador y procesamos la consulta antes de dibujar
    busqueda_edit = st.session_state.get("busqueda_edit_val", "")

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
        query = (
            f'SELECT {COLUMNAS_VPRS} FROM "Agua_potable"."VPRS" ORDER BY fid LIMIT 1'
        )
        df_vprs, error_db = obtener_datos(query)

    # 2. FILA CABECERA: Buscador, Info Registro y Mensaje alineados horizontalmente
    col_search, col_info, col_msg = st.columns([2.5, 1.5, 2], vertical_alignment="center")

    with col_search:
        st.text_input(
            "🔍 Buscar válvula a editar (ID, Serie, Domicilio, Colonia.):",
            placeholder="Ej. VRP-01, Centro...",
            key="busqueda_edit_val",
        )

    if error_db:
        st.error(f"Error: {error_db}")
    elif not df_vprs.empty:
        row_first = df_vprs.iloc[0]

        with col_info:
            st.markdown(
                f"<div style='margin-top: 15px;'><span style='color: #00E5FF; font-weight: bold;'>FID Registro: {row_first['fid']}</span> | "
                f"<span style='color: #F8FAFC; font-weight: bold;'>ID: {row_first['id']}</span></div>",
                unsafe_allow_html=True,
            )

        with col_msg:
            msg_texto = (
                "Mostrando la primera coincidencia encontrada."
                if (busqueda_edit and busqueda_edit.strip() != "")
                else "Mostrando el primer registro de la base de datos."
            )
            st.markdown(
                f"<p style='color: #94A3B8; font-size: 0.85rem; margin-top: 20px; margin-bottom: 0px;'>{msg_texto}</p>",
                unsafe_allow_html=True,
            )

        for idx, row in df_vprs.iterrows():
            e_id_0 = row["id_0"]
            default_x = float(row["coord_x"]) if pd.notna(row["coord_x"]) else 0.0
            default_y = float(row["coord_y"]) if pd.notna(row["coord_y"]) else 0.0

            x_key = f"coord_x_input_{row['fid']}"
            y_key = f"coord_y_input_{row['fid']}"
            if x_key not in st.session_state:
                st.session_state[x_key] = default_x
            if y_key not in st.session_state:
                st.session_state[y_key] = default_y

            estado_actual = str(row["estat_valv"] or "").strip()
            idx_estado = 0
            if estado_actual in OPCIONES_ESTADO_VALVULA:
                idx_estado = OPCIONES_ESTADO_VALVULA.index(estado_actual)

            e_serie_val = (
                ""
                if (
                    pd.isna(row["serie"])
                    or str(row["serie"]).strip().lower() in ["nan", "none"]
                )
                else str(row["serie"])
            )

            # 11.1 -------------------------------------- ORDEN EXACTO DE CAMPOS SOLICITADO EN LA IMAGEN 
            # FILA 1
            e_c1, e_c2, e_c3, e_c4 = st.columns(4)
            with e_c1:
                st.text_input(
                    "ID_0 (Registro)",
                    value=str(row["id_0"] or 0),
                    disabled=True,
                    key=f"id0_bloq_{row['fid']}",
                )
            with e_c2:
                e_id = st.text_input(
                    "ID VRP", value=str(row["id"] or ""), key=f"id_{row['fid']}"
                )
            with e_c3:
                e_cota = st.number_input(
                    "Cota Terreno",
                    value=float(row["cota_terr"] or 0.0),
                    key=f"cota_{row['fid']}",
                )
            with e_c4:
                e_marca = st.text_input(
                    "Marca Valvula",
                    value=str(row["marca_valv"] or ""),
                    key=f"mar_{row['fid']}",
                )

            # FILA 2
            e_c5, e_c6, e_c7, e_c8 = st.columns(4)
            with e_c5:
                e_serie = st.text_input(
                    "Serie", value=e_serie_val, key=f"serie_{row['fid']}"
                )
            with e_c6:
                e_diametro = st.number_input(
                    "Diámetro",
                    value=int(row["diametro"] or 0),
                    key=f"diam_{row['fid']}",
                )
            with e_c7:
                e_modelo = st.text_input(
                    "Modelo Valvula",
                    value=str(row["model_valv"] or ""),
                    key=f"mod_{row['fid']}",
                )
            with e_c8:
                e_trim = st.text_input(
                    "Marca Trim",
                    value=str(row["marca_trim"] or ""),
                    key=f"trim_{row['fid']}",
                )

            # FILA 3
            e_c9, e_c10, e_c11, e_c12 = st.columns(4)
            with e_c9:
                e_domicilio = st.text_input(
                    "Domicilio",
                    value=str(row["domicilio"] or ""),
                    key=f"dom_{row['fid']}",
                )
            with e_c10:
                e_colonia = st.text_input(
                    "Colonia",
                    value=str(row["colonia"] or ""),
                    key=f"col_{row['fid']}",
                )
            with e_c11:
                e_estat = st.selectbox(
                    "Estado de la Válvula",
                    options=OPCIONES_ESTADO_VALVULA,
                    index=idx_estado,
                    key=f"est_{row['fid']}",
                )
            with e_c12:
                e_sector = st.text_input(
                    "Sector Hidráulico",
                    value=str(row["sector_hid"] or ""),
                    key=f"sec_{row['fid']}",
                )

            # ------------------------------------------------- FILA 4 (Mapa + Coordenadas y Calibraciones)
            col_coord_left, col_map_right = st.columns([1, 1])

            with col_map_right:
                st.markdown(
                    "<p style='color: #00E5FF; font-size: 0.8rem; font-weight: 700;"
                    " margin-top: 0px;'>🗺️ Ubicación Geográfica (geom) - Haga clic en el"
                    " mapa para actualizar coordenadas automáticamente</p>",
                    unsafe_allow_html=True,
                )
                try:
                    if (
                        st.session_state[x_key] != 0.0
                        and st.session_state[y_key] != 0.0
                    ):
                        lon_ed, lat_ed = transformer_to_latlon.transform(
                            st.session_state[x_key], st.session_state[y_key]
                        )
                        m_ed = folium.Map(
                            location=[lat_ed, lon_ed], zoom_start=16, control_scale=True
                        )
                    else:
                        m_ed = folium.Map(
                            location=[21.8853, -102.2916], zoom_start=12, control_scale=True
                        )

                    agregar_capas_base_mapa(m_ed)
                    Fullscreen().add_to(m_ed)

                    if (
                        st.session_state[x_key] != 0.0
                        and st.session_state[y_key] != 0.0
                    ):
                        folium.Marker(
                            location=[lat_ed, lon_ed],
                            popup=f"VRP: {row['id']}",
                            icon=folium.Icon(color="cyan", icon="info-sign"),
                        ).add_to(m_ed)

                    folium.LayerControl(collapsed=False).add_to(m_ed)
                    map_data_ed = st_folium(
                        m_ed,
                        width="100%",
                        height=325,
                        key=f"map_edit_preview_{row['fid']}",
                        returned_objects=["last_clicked"],
                    )

                    if map_data_ed and map_data_ed.get("last_clicked"):
                        lat_c = map_data_ed["last_clicked"]["lat"]
                        lon_c = map_data_ed["last_clicked"]["lng"]
                        utm_x, utm_y = transformer_to_utm.transform(lon_c, lat_c)
                        new_x = round(utm_x, 2)
                        new_y = round(utm_y, 3)
                        if (
                            st.session_state[x_key] != new_x
                            or st.session_state[y_key] != new_y
                        ):
                            st.session_state[x_key] = new_x
                            st.session_state[y_key] = new_y
                            st.rerun()

                except Exception as e_map_ed:
                    st.info(
                        "Haga clic en el mapa para actualizar la posición geográfica."
                        f" ({e_map_ed})"
                    )

            with col_coord_left:
                cx1, cx2 = st.columns(2)
                with cx1:
                    e_coord_x = st.number_input(
                        "Coordenada X",
                        format="%.2f",
                        key=x_key,
                    )
                with cx2:
                    e_coord_y = st.number_input(
                        "Coordenada Y",
                        format="%.3f",
                        key=y_key,
                    )

                # FILA 5 (Hora Cal, Cal Anterior Noche)
                cc1, cc2 = st.columns(2)
                with cc1:
                    e_hora = st.text_input(
                        "Hora de Calibración",
                        value=str(row["hora_cal"] or ""),
                        key=f"hora_{row['fid']}",
                    )
                with cc2:
                    e_cal_ant_n = st.text_input(
                        "Calibración Anterior Noche (kg/cm)",
                        value=str(row["cal_ant_n"] or ""),
                        key=f"cann_{row['fid']}",
                    )

                # FILA 6 (Cal Anterior Día, Cal Actual Día)
                cc3, cc4 = st.columns(2)
                with cc3:
                    e_cal_ant_d = st.text_input(
                        "Calibración Anterior Día (kg/cm)",
                        value=str(row["cal_ant_d"] or ""),
                        key=f"cand_{row['fid']}",
                    )
                with cc4:
                    e_cal_act_d = st.text_input(
                        "Calibración Actual Día (kg/cm)",
                        value=str(row["cal_act_d"] or ""),
                        key=f"cactd_{row['fid']}",
                    )

                # FILA 7 (Cal Actual Noche, Fecha última actualización)
                cc5, cc6 = st.columns(2)
                with cc5:
                    e_cal_act_n = st.text_input(
                        "Calibración Actual Noche (kg/cm)",
                        value=str(row["cal_act_n"] or ""),
                        key=f"cactn_{row['fid']}",
                    )
                with cc6:
                    fecha_def = parsear_fecha_segura(row["fecha_ult_"])
                    e_fecha_obj = st.date_input(
                        "Fecha última actualización",
                        value=fecha_def,
                        format="DD/MM/YYYY",
                        key=f"fec_{row['fid']}",
                    )
                    e_fecha = e_fecha_obj.strftime("%d/%m/%Y")

            # FILA 8: Observaciones
            e_observ = st.text_area(
                "Observaciones",
                value=str(row["observ"] or ""),
                key=f"obs_{row['fid']}",
            )

            st.markdown(
                "<hr style='border: 0.3px solid rgba(0,229,255,0.2); margin: 15px 0;'>",
                unsafe_allow_html=True,
            )
            st.markdown(
                '<h4 style="color: #00E5FF; font-size: 1rem; font-weight: 700;">📸'
                " Gestión de Fotografías</h4>",
                unsafe_allow_html=True,
            )

# ------------------------------------------------- GESTIÓN DE FOTOGRAFÍAS (FILE UPLOADER CON RESET)
            
            # Inicializamos contadores para controlar la versión de la key de los uploaders
            key_ver_1 = f"uploader_ver_1_{row['fid']}"
            key_ver_2 = f"uploader_ver_2_{row['fid']}"
            
            if key_ver_1 not in st.session_state:
                st.session_state[key_ver_1] = 0
            if key_ver_2 not in st.session_state:
                st.session_state[key_ver_2] = 0

            col_edit_f1, col_edit_f2 = st.columns(2)

            # --- FOTO 1 ---
            with col_edit_f1:
                foto_actual_bytes = procesar_bytes_foto(row["fotos"])
                eliminar_foto = False

                if foto_actual_bytes is not None and len(foto_actual_bytes) > 0:
                    st.image(
                        foto_actual_bytes,
                        caption=f"ID: {row['id']} (Foto 1 Actual)",
                        use_container_width=True,
                    )
                    eliminar_foto = st.checkbox(
                        "🗑️ Eliminar fotografía 1", key=f"del_foto_{row['fid']}"
                    )

                # Generamos una key dinámica que cambia cuando guardamos
                nueva_foto_archivo = st.file_uploader(
                    "📁 Cargar/Reemplazar Foto 1 desde PC",
                    type=["png", "jpg", "jpeg", "webp"],
                    key=f"file_edit_1_{row['fid']}_{st.session_state[key_ver_1]}",
                )

            # --- FOTO 2 ---
            with col_edit_f2:
                foto_actual_bytes_2 = procesar_bytes_foto(row["fotos_2"])
                eliminar_foto_2 = False

                if foto_actual_bytes_2 is not None and len(foto_actual_bytes_2) > 0:
                    st.image(
                        foto_actual_bytes_2,
                        caption=f"ID: {row['id']} (Foto 2 Actual)",
                        use_container_width=True,
                    )
                    eliminar_foto_2 = st.checkbox(
                        "🗑️ Eliminar fotografía 2", key=f"del_foto_2_{row['fid']}"
                    )

                # Generamos una key dinámica que cambia cuando guardamos
                nueva_foto_archivo_2 = st.file_uploader(
                    "📁 Cargar/Reemplazar Foto 2 desde PC",
                    type=["png", "jpg", "jpeg", "webp"],
                    key=f"file_edit_2_{row['fid']}_{st.session_state[key_ver_2]}",
                )

            st.markdown("<br>", unsafe_allow_html=True)
            actualizar_click = st.button(
                "💾 Actualizar Registro en Base de Datos",
                key=f"btn_act_{row['fid']}",
                use_container_width=True,
            )

            if actualizar_click:
                try:
                    # Lógica de guardado Foto 1
                    if eliminar_foto:
                        foto_bytes_final = None
                    else:
                        foto_bytes_final = foto_actual_bytes
                        if nueva_foto_archivo is not None:
                            foto_bytes_final = nueva_foto_archivo.getvalue()

                    # Lógica de guardado Foto 2
                    if eliminar_foto_2:
                        foto_bytes_final_2 = None
                    else:
                        foto_bytes_final_2 = foto_actual_bytes_2
                        if nueva_foto_archivo_2 is not None:
                            foto_bytes_final_2 = nueva_foto_archivo_2.getvalue()

                    sql_update = """
                                UPDATE "Agua_potable"."VPRS" 
                                SET id_0 = :id_0, id = :id, serie = :serie, diametro = :diametro, marca_valv = :marca_valv, 
                                    model_valv = :model_valv, marca_trim = :marca_trim, domicilio = :domicilio, 
                                    colonia = :colonia, cota_terr = :cota_terr, sector_hid = :sector_hid, 
                                    cal_ant_d = :cal_ant_d, cal_ant_n = :cal_ant_n, fecha_ult_ = :fecha_ult_, 
                                    cal_act_d = :cal_act_d, cal_act_n = :cal_act_n, hora_cal = :hora_cal, 
                                    estat_valv = :estat_valv, observ = :observ, fotos = :fotos, fotos_2 = :fotos_2,
                                    geom = ST_SetSRID(ST_MakePoint(:coord_x, :coord_y), 32613)
                                WHERE fid = :fid
                            """
                    ejecutar_sql(
                        sql_update,
                        {
                            "id_0": e_id_0,
                            "id": e_id,
                            "serie": e_serie if e_serie.strip() != "" else None,
                            "diametro": e_diametro,
                            "marca_valv": e_marca,
                            "model_valv": e_modelo,
                            "marca_trim": e_trim,
                            "domicilio": e_domicilio,
                            "colonia": e_colonia,
                            "cota_terr": e_cota,
                            "sector_hid": e_sector,
                            "cal_ant_d": e_cal_ant_d,
                            "cal_ant_n": e_cal_ant_n,
                            "fecha_ult_": e_fecha,
                            "cal_act_d": e_cal_act_d,
                            "cal_act_n": e_cal_act_n,
                            "hora_cal": e_hora,
                            "estat_valv": e_estat,
                            "observ": e_observ,
                            "fotos": foto_bytes_final,
                            "fotos_2": foto_bytes_final_2,
                            "coord_x": st.session_state[x_key],
                            "coord_y": st.session_state[y_key],
                            "fid": row["fid"],
                        },
                    )

                    # Incrementamos la versión de la key para obligar a Streamlit a destruir y volver a crear el widget limpio
                    st.session_state[key_ver_1] += 1
                    st.session_state[key_ver_2] += 1

                    st.success(f"¡Registro FID {row['fid']} actualizado con éxito!")
                    t.sleep(1)
                    st.rerun()
                except Exception as ex:
                    st.error(f"Error al actualizar: {ex}")

            # --------------------------------------------------------------------------------------------------------------------------------------------------------

            if not es_operador:
                st.markdown(
                    "<hr style='border: 0.5px solid rgba(255,0,0,0.2); margin: 20px 0;'>",
                    unsafe_allow_html=True,
                )

                if st.session_state.registro_to_delete == row["fid"]:
                    st.markdown(
                        f"<p style='color: #ff4d4d; font-size: 0.9rem; font-weight:"
                        f" bold;'>Para eliminar el registro FID {row['fid']} (ID:"
                        f" {row['id']}), escribe la palabra 'delete':</p>",
                        unsafe_allow_html=True,
                    )
                    confirm_text = st.text_input(
                        "Confirmación de eliminación", key=f"input_del_text_{row['fid']}"
                    )

                    col_y, col_n = st.columns(2)
                    with col_y:
                        if st.button(
                            "Sí, eliminar definitivamente",
                            key=f"confirm_del_{row['fid']}",
                            use_container_width=True,
                        ):
                            if confirm_text.strip() == "delete":
                                try:
                                    ejecutar_sql(
                                        'DELETE FROM "Agua_potable"."VPRS" WHERE fid = :fid',
                                        {"fid": row["fid"]},
                                    )
                                    st.session_state.registro_to_delete = None
                                    st.success("Registro eliminado correctamente.")
                                    t.sleep(1)
                                    st.rerun()
                                except Exception as ex_del:
                                    st.error(f"Error al eliminar: {ex_del}")
                            else:
                                st.error(
                                    "Debes escribir exactamente la palabra 'delete' para"
                                    " confirmar."
                                )
                    with col_n:
                        if st.button(
                            "Cancelar",
                            key=f"cancel_del_{row['fid']}",
                            use_container_width=True,
                        ):
                            st.session_state.registro_to_delete = None
                            st.rerun()
                else:
                    # Botón de Eliminar al 100% del ancho
                    if st.button(
                        "🗑️ Eliminar este registro",
                        key=f"btn_del_{row['fid']}",
                        use_container_width=True,
                    ):
                        st.session_state.registro_to_delete = row["fid"]
                        st.rerun()
    else:
        st.info("No se encontró ningún registro para editar.")
# 12 --------------------------------------------------------------------------------------  PIE DE PÁGINA --------------------------------------------------------------------------------------------------
st.markdown(
    """
    <div style="text-align: center; color: #94A3B8; font-size: 0.85rem; margin-top: 3rem; border-top: 1px solid rgba(0, 229, 255, 0.15); padding-top: 1rem;">
        © 2026 MIAA &bull; Sistema de Gestión Valvulas reductoras de presión  (Escritorio)
    </div>
""",
    unsafe_allow_html=True,
)
