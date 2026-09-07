import folium
from folium.plugins import MarkerCluster
import pandas as pd
from pyproj import Transformer
import streamlit as st
from streamlit_folium import st_folium


def render_vrp_map(df):
  # 1. Configurar el transformador de coordenadas UTM Zona 13N a WGS84 (Lat/Lon)
  transformer = Transformer.from_crs("EPSG:32613", "EPSG:4326", always_xy=True)

  def parse_and_transform(geom_str):
    coords = (
        str(geom_str)
        .replace("POINT", "")
        .replace("(", "")
        .replace(")", "")
        .strip()
    )
    x, y = map(float, coords.split())
    lon, lat = transformer.transform(x, y)
    return lat, lon

  # 2. Definir paleta de colores según el estado de la válvula
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
      return "gray"  # Color por defecto para otros estados

  st.subheader("Mapa Principal de VRPs - Registros")

  # 3. Crear mapa centrado en Aguascalientes
  m = folium.Map(
      location=[21.8853, -102.2916], zoom_start=12, control_scale=True
  )
  folium.TileLayer("cartodark_matter").add_to(
      m
  )  # Compatible con tu configuración previa de mapas oscuros

  marker_cluster = MarkerCluster().add_to(m)

  # 4. Procesar geometrías y agregar marcadores
  success_count = 0
  for idx, row in df.iterrows():
    try:
      lat, lon = parse_and_transform(row["geom"])
      estado = row.get("estado_valvula", "Desconocido")
      color = get_valve_color(estado)

      folium.CircleMarker(
          location=[lat, lon],
          radius=8,
          color=color,
          fill=True,
          fill_color=color,
          fill_opacity=0.85,
          popup=folium.Popup(
              f"<b>VRP ID:</b> {row.get('id', idx)}<br>"
              f"<b>Estado:</b> {estado}",
              max_width=300,
          ),
      ).add_to(marker_cluster)
      success_count += 1
    except Exception as e:
      continue

  # 5. Renderizar en Streamlit
  st_folium(m, width="100%", height=600)

  # Verificación de éxito en la carga de puntos
  if success_count > 0:
    st.success(
        f"Mapa actualizado correctamente. Se cargaron {success_count} VRPs"
        " georreferenciados."
    )
  else:
    st.warning(
        "No se pudieron renderizar puntos. Verifique el formato de la columna"
        " geom."
    )
