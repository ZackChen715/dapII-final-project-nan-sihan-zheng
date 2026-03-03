import pandas as pd
import altair as alt
from pathlib import Path

def plot_nationwide_call_type(save_path=None):

    # Load data
    script_dir = Path(__file__).parent
    df_call = script_dir / "../data/derived-data/nationwide_long.csv"
    df = pd.read_csv(df_call)
    CALL_CATEGORY_COL = "Call Categories"

    # Aggregate counts
    category_counts = (
        df.groupby(CALL_CATEGORY_COL)
          .size()
          .reset_index(name="Number of Programs")
          .sort_values("Number of Programs", ascending=False)
    )

    # Altair chart
    chart = (
        alt.Chart(category_counts)
        .mark_bar()
        .encode(
            x=alt.X(
                "Number of Programs:Q",
                title="Number of Programs"
            ),
            y=alt.Y(
                f"{CALL_CATEGORY_COL}:N",
                sort="-x",
                title=None
            ),
            color=alt.Color(
                   f"{CALL_CATEGORY_COL}:N",
                   scale=alt.Scale(
                       domain=category_counts[CALL_CATEGORY_COL].tolist(),
                       range=["#2E4A9E", "#5B6B9A", "#7A7A70", "#A59659", "#C9AE45", "#F2C21A"]
                   ),
                   legend=None
            )
        )
        .properties(
            width=700,
            height=400,
            title="Call Categories"
        )
    )

    # Save the chart if save_path is provided
    if save_path:
        chart.save(save_path, scale_factor=2)

    return chart

# Example usage
if __name__ == "__main__":
    # Display the chart
    chart = plot_nationwide_call_type(save_path=None)
    chart.show()
