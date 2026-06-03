"""Streamlit app for generator offer curve forecast visualization."""

from pathlib import Path

import pandas as pd
import streamlit as st

from offer_curves import (
    CSV_PATH,
    TARGET_FORECAST_DATE,
    MW_MAX,
    PRICE_MAX,
    PRICE_MIN,
    build_forecasts,
    build_offer_curve_figure,
    load_and_process,
)

st.set_page_config(
    page_title="Generator Offer Curve Forecast",
    page_icon="📈",
    layout="wide",
)

METHODOLOGY = """
### Data cleaning
1. **Timestamps** — parse to datetime; drop unparseable rows; sort chronologically.
2. **Duplicate rows** — remove exact duplicates, then keep the last record per timestamp.
3. **Numeric fields** — coerce MW, price, and limit columns; non-numeric values become missing.
4. **Missing breakpoints** — drop individual MW/price pairs where either value is missing.
5. **Price outliers** — remove points outside **{price_min} to {price_max} $/MWh**.
6. **MW outliers** — remove negative MW and MW above **{mw_max}** (well above this unit's ~190–200 MW cap).
7. **Monotonic MW** — sort valid breakpoint pairs by MW within each hour so curves do not step backward.
8. **High/Low limits** — swap when Low > High; drop rows that remain invalid.

### Forecast method (target date: {target_date})
For each hour of the target day:
1. Use the **same calendar date one year prior** when available.
2. Else use the **median MW/price at each breakpoint** for the same hour, month, and weekday.
3. Else use the **median MW/price at each breakpoint** for the same hour across all history.

### Assumptions
- Historical offer curves for the same hour-of-day are comparable across days.
- Prior-year same-date is a reasonable baseline when available (used for all 24 hours here).
- Fixed outlier thresholds are acceptable because most valid ERCOT offer prices for this unit sit between roughly $20–$45/MWh.
- `Resource Status` is not used in cleaning or forecasting.
- Duplicate timestamps are resolved by keeping the **last** record after sorting.

### AI tools
Cursor AI (Claude) was used to accelerate implementation: exploring the dataset, structuring the
cleaning pipeline, building the Plotly visualization, and creating this Streamlit app. All logic
was reviewed and validated against the assessment requirements.
""".format(
    price_min=PRICE_MIN,
    price_max=PRICE_MAX,
    mw_max=MW_MAX,
    target_date=TARGET_FORECAST_DATE.date(),
)


@st.cache_data
def get_data(csv_path: str):
    hourly_df, curve_points, cleaning_log = load_and_process(csv_path)
    forecast_curves, forecast_methods = build_forecasts(curve_points, TARGET_FORECAST_DATE)
    return hourly_df, curve_points, cleaning_log, forecast_curves, forecast_methods


st.title("Generator Offer Curve Forecast")
st.caption("ERCOT hourly offer curves with forecast for 05/29/2026")

csv_path = st.sidebar.text_input("CSV file path", value=str(CSV_PATH))
if not Path(csv_path).exists():
    st.error(f"File not found: {csv_path}")
    st.stop()

hourly_df, curve_points, cleaning_log, forecast_curves, forecast_methods = get_data(csv_path)

st.sidebar.markdown("### Data summary")
st.sidebar.metric("Clean hourly records", f"{len(hourly_df):,}")
st.sidebar.metric("Valid breakpoint points", f"{len(curve_points):,}")
st.sidebar.metric("Date range", f"{hourly_df['Timestamp'].min():%Y-%m-%d} → {hourly_df['Timestamp'].max():%Y-%m-%d}")

with st.sidebar.expander("Cleaning log"):
    for key, value in cleaning_log.items():
        st.write(f"**{key.replace('_', ' ').title()}:** {value}")

with st.sidebar.expander("Forecast method by hour"):
    st.dataframe(
        pd.Series(forecast_methods, name="method").rename_axis("hour").reset_index(),
        hide_index=True,
        use_container_width=True,
    )

fig = build_offer_curve_figure(curve_points, forecast_curves, TARGET_FORECAST_DATE)
st.plotly_chart(fig, use_container_width=True)

with st.expander("Methodology, assumptions, and AI disclosure"):
    st.markdown(METHODOLOGY)

html_path = Path("offer_curve_forecast.html")
fig.write_html(html_path)
st.download_button(
    label="Download plot as HTML",
    data=html_path.read_bytes(),
    file_name="offer_curve_forecast.html",
    mime="text/html",
)
