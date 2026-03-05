# dapII-final-project-nan-sihan-zheng
This is the student team repository for the final project from DAP II

# Seattle CARE Calls Analysis

This project analyzes Community Assistance & Response Engagement (CARE) calls in Seattle,
combines neighborhood-level call data with equity indicators, and visualizes nationwide
community responder programs. The outputs include static plots and an interactive Streamlit
dashboard.

## Setup

```bash
conda env create -f environment.yml
conda activate "Seattle CARE Calls Analysis"
```

## Project Structure

```
data/
  raw-data/
    Call_Data_20260227.csv              # Seattle CARE calls (raw)
    Map-Data-as-of-Sep16-25.csv         # Nationwide responder programs (raw)
    us-states.json                      # US basemap
    Neighborhood_geo/                   # Seattle neighborhood shapefile
    equity_geodata/                     # Seattle equity index shapefile
  derived-data/
    call_clean.csv                      # Cleaned CARE calls with categories
    nationwide_long.csv                 # Exploded nationwide program categories
    calls_Seattle.png                   # CARE calls by neighborhood map
    heatmap_day_hour.png                # Calls by day/hour heatmap
    bar_call_type.png                   # Call category distribution
    equity_score_map.png                # Equity index map
    national_programs_map.png           # Nationwide programs map
code/
  preprocessing.py                      # Clean and categorize call data
  plot_calls.py                         # Neighborhood map of CARE calls
  plot_time.py                          # Day/hour heatmap
  plot_type_bar.py                      # Call category bar chart
  plot_equity.py                        # Equity index map
  plot_nationwide_map.py                # Nationwide programs map
  plot_nationwide_call_type.py          # Nationwide call category bar chart
  app.py                                # Streamlit dashboard
```

## Usage

1. Run preprocessing to generate cleaned data:
   ```bash
   python code/preprocessing.py
   ```

2. Generate static plots:
   ```bash
   python code/plot_calls.py
   python code/plot_time.py
   python code/plot_type_bar.py
   python code/plot_equity.py
   python code/plot_nationwide_map.py
   ```

3. Run the Streamlit dashboard:
   ```bash
   streamlit run code/app.py
   ```

   Note: `code/app.py` uses Mapbox for the 3D map. Set your token before running:
   ```bash
   export MAPBOX_API_KEY="your_token_here"
   ```

## Special Note for local Dashboard
Since the project use **Mapbox** for map rendering, it need to set up a Mapbox access token to run the code locally.

**Example Setup for Local Dashboard**
```bash
export MAPBOX_API_KEY="your_token_here"
```

### Sepcial Note for Sreamlit Deploying Use
For **deploying use**, the following code in the app.py reads the token from Streamlit secrets and sets it as an environment variable for pydeck to use.

**If you want to run streamlit app locally, the following code will cause an error. For running the local dashboard successfully, you need to remove the following code in app.py:**

mapbox_token = st.secrets["MAPBOX_API_KEY"]
os.environ["MAPBOX_API_KEY"] = mapbox_token
