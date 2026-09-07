import folium
from folium.plugins import MarkerCluster
import pandas as pd
from pyproj import Transformer
import sqlalchemy
import streamlit as st
from streamlit_folium import st_folium


def render_vrp_map_from_db(engine):
  # 1. Consulta SQL directa extrayendo X e Y de PostGIS y el campo correcto de estado: estat_valvula
  query = """
        SELECT 
            id,
            estat_valvula,
            ST_X(geom) as x,
            ST_Y(geom) as y
        FROM Agua_potable."VPRS"
        WHERE geom IS NOT NULL;
    """
  df = pd.read_sql(query, engine)

  # 2. Configurar transformador de EPSG:32613 a WGS84 (Lat/Lon)
  transformer = Transformer.from_crs("EPSG:32613", "EPSG:4326", always_xy=True)

  # 3. Paleta de colores según 'estat_valvula'
  def get_valve_color(estado):
    estado_str = str(estado).strip().lower()
    if "cerrada" in estado_str:
      return "red"
    elif "calibrada" in estado_str:
      return "green"
    elif "habilitada" in estado_str:
      return "blue"
    elif "mantenimiento" in estado_str:
      return "orange"
    else:
      return "gray"

  st.subheader("Mapa Principal de VRPs - Registros")

  # 4. Crear mapa centrado en Aguascalientes
  m = folium.Map(
      location=[21.8853, -102.2916], zoom_start=12, control_scale=True
  )
  folium.TileLayer("cartodark_matter").add_to(m)

  marker_cluster = MarkerCluster().add_to(m)

  success_count = 0
  for _, row in df.iterrows():
    try:
      # Transformar X e Y directamente
      lon, lat = transformer.transform(row["x"], row["y"])
      estado = row["estat_valvula"]
      color = get_valve_color(estado)

      folium.CircleMarker(
          location=[lat, lon],
          radius=8,
          color=color,
          fill=True,
          fill_color=color,
          fill_opacity=0.85,
          popup=folium.Popup(
              f"<b>VRP ID:</b> {row['id']}<br>"
              f"<b>Estado:</b> {estado or 'No especificado'}",
              max_width=300,
          ),
      ).add_to(marker_cluster)
      success_count += 1
    except Exception:
      continue

  st_folium(m, width="100%", height=600)
  st.success(f"Se cargaron {success_count} VRPs correctamente desde PostGIS.")
