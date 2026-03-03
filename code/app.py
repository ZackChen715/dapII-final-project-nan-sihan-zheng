import os
import numpy as np
import pandas as pd
import geopandas as gpd
import pydeck as pdk
import streamlit as st
from pathlib import Path
import matplotlib.pyplot as plt
import altair as alt
import plotly.express as px

# Import the plotting functions
from plot_nationwide_call_type import plot_nationwide_call_type

st.set_page_config(
    layout="wide",
    page_title="Seattle CARE Calls Dashboard",
    page_icon="☎️",
)

script_dir = Path(__file__).parent
PLOT_DF_PATH = script_dir / '../data/derived-data/call_clean.csv'                 
NEIGHBORHOODS_SHP_PATH = script_dir / '../data/raw-data/Neighborhood_geo/Neighborhood_Map_Atlas_Districts.shp'
NATIONWIDE_POINTS_PATH = script_dir / '../data/raw-data/Map-Data-as-of-Sep16-25.csv'

HOUR_COL = "hour"
NEIGHBORHOOD_COL_DATA = "neighborhood"       
NEIGHBORHOOD_COL_SHAPE = "L_HOOD"      

DT_CANDIDATES = ["dispatch_datetime", "dispatch_time", "timestamp", "datetime", "date_time"]

MAP_STYLE = "mapbox://styles/mapbox/dark-v11"
DEFAULT_ZOOM = 10.8
DEFAULT_PITCH = 50

COLUMN_RADIUS_METERS = 260     
ELEVATION_SCALE = 35           
CALL_THRESHOLD = 3000

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


@st.cache_data
def load_neighborhood_geo(shp_path: str) -> gpd.GeoDataFrame:
    if not os.path.isfile(shp_path):
        raise FileNotFoundError(f"Cannot find {shp_path}. Please put shp here or update NEIGHBORHOODS_SHP_PATH.")

    gdf = gpd.read_file(shp_path)
    gdf.columns = [c.strip() for c in gdf.columns]

    if NEIGHBORHOOD_COL_SHAPE not in gdf.columns:
        raise ValueError(
            f"Neighborhood shp missing column '{NEIGHBORHOOD_COL_SHAPE}'. "
            f"Available columns: {list(gdf.columns)}"
        )

    gdf[NEIGHBORHOOD_COL_SHAPE] = gdf[NEIGHBORHOOD_COL_SHAPE].astype(str)
    # Plotly expects GeoJSON in WGS84; reproject if needed.
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    else:
        gdf = gdf.to_crs(epsg=4326)
    return gdf


@st.cache_data
def load_nationwide_points(path: str) -> pd.DataFrame:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Cannot find {path}. Please put csv here or update NATIONWIDE_POINTS_PATH.")

    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]

    for col in ["Latitude", "Longitude", "Call Volume"]:
        if col not in df.columns:
            raise ValueError(f"{path} missing required column: '{col}'")

    df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
    df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")
    df["Call Volume"] = pd.to_numeric(df["Call Volume"], errors="coerce")
    df = df.dropna(subset=["Latitude", "Longitude"]).copy()

    df["Call Bucket"] = np.where(
        df["Call Volume"].notna() & (df["Call Volume"] > CALL_THRESHOLD),
        f"More than {CALL_THRESHOLD:,} calls/year",
        f"{CALL_THRESHOLD:,} calls/year or less",
    )
    df.loc[df["Call Volume"].isna(), "Call Bucket"] = "Call volume unknown"

    return df

# Load data
plot_df = load_plot_df(PLOT_DF_PATH)
centroids = load_neighborhood_centroids(NEIGHBORHOODS_SHP_PATH)
nationwide_points = load_nationwide_points(NATIONWIDE_POINTS_PATH)

# Define individual pages as functions
def home_page():
    st.title("Welcome to the Seattle CARE Calls Dashboard☎️")
    st.write(
        """
        This application provides insights into Seattle CARE calls data.

        ## User Guide 🧭
        - Use the **Dashboard** page to explore the number of CARE call across different time preiod.
        - Hover over the 3D map at **Care Call Map** to view details of CARE CAll about each neighborhood.

        ## Introduction to CARE 
        - Full Name: Community Assistance & Response Engagement
        ### Responsibility:
        - Co-response with behavioral health professionals 
        - Designed to respond to mental health crises 
        - Reduce reliance on traditional police response
        """
    )
    st.sidebar.success("You are on the Home page.")

    # First chart: Nationwide Community Responder Programs
    st.subheader("Why Seattle?")
    st.write("- A large, mature city with an established community responder program")
    st.write("- Call volume is not among the highest nationwide (Seattle is the white dot at the upper-left corner).")
    fig = px.scatter_geo(
        nationwide_points,
        lat="Latitude",
        lon="Longitude",
        color="Call Bucket",
        symbol="Call Bucket",
        hover_name="Combined City + Program Name",
        hover_data={
            "Program Name": True,
            "Call Volume": True,
            "Launch Year": True,
            "Responder Type": True,
            "Dispatch method": True,
            "Latitude": False,
            "Longitude": False,
        },
        color_discrete_map={
            f"More than {CALL_THRESHOLD:,} calls/year": "#f1c40f",
            f"{CALL_THRESHOLD:,} calls/year or less": "#ffffff",
            "Call volume unknown": "#9aa0a6",
        },
        scope="usa",
    )
    fig.update_traces(marker=dict(size=10, line=dict(width=1, color="black")))
    fig.update_layout(legend_title_text="", margin={"r": 0, "t": 0, "l": 0, "b": 0})
    st.plotly_chart(fig, use_container_width=True)

    # Second chart: Call Categories
    st.write("### CARE primarily responding to nation-wide behavioral and psychological crisis")
    plot_nationwide_call_type()  # Call the function to generate the chart
    image2_path = script_dir / "../data/derived-data/national_call_categories.png"
    st.image(image2_path)

def call_time_page():
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

    # Merge data with centroids
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

    # Add the heatmap
    st.subheader("Behavioral / CARE Calls by Day and Hour")
    script_dir = Path(__file__).parent
    image3_path = script_dir / "../data/derived-data/heatmap_day_hour.png"
    st.image(image3_path)

# Add more pages as needed
def geo_plot_page():
    st.title("CARE Calls by Neighborhood")
    st.write("Hover to see neighborhood name and call count.")
    st.write(
        "This map shows total CARE call volume by neighborhood. "
        "Darker areas indicate more calls overall, which helps compare "
        "hotspots against the equity index map on the right."
    )

    gdf = load_neighborhood_geo(NEIGHBORHOODS_SHP_PATH)
    call_counts = (
        plot_df.groupby(NEIGHBORHOOD_COL_DATA)
        .size()
        .reset_index(name="n_calls")
    )
    call_counts[NEIGHBORHOOD_COL_DATA] = call_counts[NEIGHBORHOOD_COL_DATA].astype(str)

    merged = gdf.merge(
        call_counts,
        left_on=NEIGHBORHOOD_COL_SHAPE,
        right_on=NEIGHBORHOOD_COL_DATA,
        how="left",
    )
    merged["n_calls"] = merged["n_calls"].fillna(0).astype(int)

    merged = merged.set_index(NEIGHBORHOOD_COL_SHAPE)
    minx, miny, maxx, maxy = merged.total_bounds
    pad_x = (maxx - minx) * 0.08
    pad_y = (maxy - miny) * 0.08
    geojson = merged.__geo_interface__
    fig = px.choropleth(
        merged,
        geojson=geojson,
        locations=merged.index,
        color="n_calls",
        color_continuous_scale="Reds",
        hover_name=merged.index,
        hover_data={"n_calls": True},
    )
    fig.update_geos(
        visible=False,
        projection_type="mercator",
        lonaxis_range=[minx - pad_x, maxx + pad_x],
        lataxis_range=[miny - pad_y, maxy + pad_y],
    )
    fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, height=750, autosize=False)

    left, right = st.columns((3, 2))
    with left:
        st.plotly_chart(fig, use_container_width=True)
    with right:
        equity_img = Path(__file__).parent / "../data/derived-data/seattle_ses_disadv_heatmap.png"
        st.image(equity_img, caption="Seattle Socioeconomic Disadvantage Score (0–1)")

    col_left, col_right = st.columns(2)
    with col_left:
        st.write("""
        ### The Composite Index includes sub-indices of:
        **1.Race, English Language Learners, and Origins Index**

        ranks census tracts by an index of three measures weighted as follows:
        - Persons of color (weight: 1.0)
        - English language learner (weight: 0.5)
        - Foreign born (weight: 0.5)
                 
        **2.Socioeconomic Disadvantage Index**

        ranks census tracts by an index of two equally weighted measures:
        - Income below 200% of poverty level
        - Educational attainment less than a bachelor’s degree
                 
        """)
    with col_right:
        st.write("""
        **3.Health Disadvantage Index**

        ranks census tracts by an index of seven equally weighted measures:
        - No leisure-time physical activity
        - Diagnosed diabetes
        - Obesity
        - Mental health not good
        - Asthma
        - Low life expectancy at birth
        - Disability
        """)

# Map page names to functions
PAGES = {
    "Home": home_page,
    "Call Time Analysis": call_time_page,  # Updated page name
    "CARE Calls Map": geo_plot_page,
}

# Sidebar navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", options=list(PAGES.keys()))

# Render the selected page
PAGES[page]()
