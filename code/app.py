import os
import numpy as np
import pandas as pd
import geopandas as gpd
import pydeck as pdk
import streamlit as st
from pathlib import Path

mapbox_token = st.secrets["MAPBOX_API_KEY"]
os.environ["MAPBOX_API_KEY"] = mapbox_token

st.set_page_config(
    layout="wide",
    page_title="Seattle CARE Calls Dashboard",
    page_icon="☎️",
)

script_dir = Path(__file__).parent
PLOT_DF_PATH = script_dir / '../data/derived-data/call_clean.csv'                 
NEIGHBORHOODS_SHP_PATH = script_dir / '../data/raw-data/Neighborhood_geo/Neighborhood_Map_Atlas_Districts.shp'

HOUR_COL = "hour"
NEIGHBORHOOD_COL_DATA = "neighborhood"       
NEIGHBORHOOD_COL_SHAPE = "L_HOOD"      

DT_CANDIDATES = ["dispatch_datetime", "dispatch_time", "timestamp", "datetime", "date_time"]

MAP_STYLE = "mapbox://styles/mapbox/dark-v11"
DEFAULT_ZOOM = 10.8
DEFAULT_PITCH = 50

COLUMN_RADIUS_METERS = 260     
ELEVATION_SCALE = 35           

# loaders
@st.cache_data
def load_plot_df(path: str) -> pd.DataFrame:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Cannot find {path}. Please put plot_df.csv here or update PLOT_DF_PATH.")

    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]

    # validate columns
    for c in [HOUR_COL, NEIGHBORHOOD_COL_DATA]:
        if c not in df.columns:
            raise ValueError(f"{path} missing required column: '{c}'")

    df[HOUR_COL] = pd.to_numeric(df[HOUR_COL], errors="coerce").astype("Int64")
    df[NEIGHBORHOOD_COL_DATA] = df[NEIGHBORHOOD_COL_DATA].astype(str).fillna("Unknown")

    # try parse datetime
    dt_col = next((c for c in DT_CANDIDATES if c in df.columns), None)
    if dt_col:
        df["_dt"] = pd.to_datetime(df[dt_col], errors="coerce")
    else:
        df["_dt"] = pd.NaT

    df = df.dropna(subset=[HOUR_COL])
    df = df[(df[HOUR_COL] >= 0) & (df[HOUR_COL] <= 23)]
    return df


@st.cache_data
def load_neighborhood_centroids(shp_path: str) -> pd.DataFrame:
    """
    Read neighborhood polygons and return centroids (lat/lon) for each neighborhood.
    """
    if not os.path.isfile(shp_path):
        raise FileNotFoundError(f"Cannot find {shp_path}. Please put shp here or update NEIGHBORHOODS_SHP_PATH.")

    gdf = gpd.read_file(shp_path)
    gdf.columns = [c.strip() for c in gdf.columns]

    if NEIGHBORHOOD_COL_SHAPE not in gdf.columns:
        raise ValueError(
            f"Neighborhood shp missing column '{NEIGHBORHOOD_COL_SHAPE}'. "
            f"Available columns: {list(gdf.columns)}"
        )

    # Use a projected CRS to compute centroids more accurately, then convert back to WGS84
    # If gdf has no CRS, assume it's already WGS84.
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)

    gdf_proj = gdf.to_crs(epsg=3857)
    gdf_proj["centroid"] = gdf_proj.geometry.centroid
    cent = gdf_proj.set_geometry("centroid").to_crs(epsg=4326)

    centroids = pd.DataFrame({
        NEIGHBORHOOD_COL_SHAPE: cent[NEIGHBORHOOD_COL_SHAPE].astype(str),
        "lon": cent.geometry.x,
        "lat": cent.geometry.y,
    }).drop_duplicates(subset=[NEIGHBORHOOD_COL_SHAPE])

    return centroids


@st.cache_data
def agg_calls_by_hour_neighborhood(df: pd.DataFrame, hour_selected: int) -> pd.DataFrame:
    """
    Count calls per neighborhood for the selected hour.
    """
    d = df[df[HOUR_COL] == hour_selected].copy()
    out = (
        d.groupby(NEIGHBORHOOD_COL_DATA)
         .size()
         .reset_index(name="calls")
    )
    out[NEIGHBORHOOD_COL_DATA] = out[NEIGHBORHOOD_COL_DATA].astype(str)
    return out


@st.cache_data
def calls_per_minute_in_hour(df: pd.DataFrame, hour_selected: int) -> pd.DataFrame:
    """
    Optional bottom chart. If datetime exists, show calls per minute within the selected hour.
    """
    d = df[(df[HOUR_COL] == hour_selected) & (df["_dt"].notna())].copy()
    if d.empty:
        return pd.DataFrame()

    d["minute"] = d["_dt"].dt.minute.astype(int)
    out = d.groupby("minute").size().reindex(range(60), fill_value=0).reset_index()
    out.columns = ["minute", "calls"]
    return out


@st.cache_data
def overall_center(centroids: pd.DataFrame) -> tuple[float, float]:
    return float(np.average(centroids["lat"])), float(np.average(centroids["lon"]))

# Load data
plot_df = load_plot_df(PLOT_DF_PATH)
centroids = load_neighborhood_centroids(NEIGHBORHOODS_SHP_PATH)

# Top layout
row1_left, row1_right = st.columns((2, 3))

with row1_left:
    st.title("Seattle CARE Calls Dashboard")
    hour_selected = st.slider(
        "Select hour of dispatch",
        min_value=0,
        max_value=23,
        value=int(st.session_state.get("dispatch_hour", 14)),
        key="dispatch_hour",
    )

with row1_right:
    st.write(
        """
        ##
        Explore how **the number of calls varies over time** across Seattle.

        - Slide to pick an **hour window** (e.g., 14 = 14:00–15:00).
        - Each 3D column is anchored at a **neighborhood centroid**.
        - Column height represents **call volume** in that hour.
        """
    )

# Aggregate + merge with centroids
calls_nb = agg_calls_by_hour_neighborhood(plot_df, hour_selected)

# merge 
merged = centroids.merge(
    calls_nb,
    left_on=NEIGHBORHOOD_COL_SHAPE,
    right_on=NEIGHBORHOOD_COL_DATA,
    how="left",
)
merged["calls"] = merged["calls"].fillna(0).astype(int)

# Center view
center_lat, center_lon = overall_center(centroids)

st.write(f"**All Seattle from {hour_selected}:00 to {(hour_selected + 1) % 24}:00**")

# Pydeck layer
max_calls = merged["calls"].max()

layer = pdk.Layer(
    "ColumnLayer",
    data=merged,
    get_position=["lon", "lat"],
    get_elevation="calls",
    elevation_scale=ELEVATION_SCALE,
    radius=COLUMN_RADIUS_METERS,
    pickable=True,
    extruded=True,

    get_fill_color="""
        calls == %d
        ? [220, 30, 30, 230]      
        : [255, 223, 120, 200]    
    """ % max_calls,
)

view_state = pdk.ViewState(
    latitude=center_lat,
    longitude=center_lon,
    zoom=DEFAULT_ZOOM,
    pitch=DEFAULT_PITCH,
)

tooltip = {
    "html": "<b>Neighborhood:</b> {" + NEIGHBORHOOD_COL_SHAPE + "}<br/><b>Calls:</b> {calls}",
    "style": {"backgroundColor": "white", "color": "black"},
}

deck = pdk.Deck(
    map_style=MAP_STYLE,
    initial_view_state=view_state,
    layers=[layer],
    tooltip=tooltip,
)

st.pydeck_chart(deck, use_container_width=True)
