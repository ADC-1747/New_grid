# Generator Offer Curve Assessment

Interactive visualization of hourly generator offer curves with a forecast for **May 29, 2026**, built from the ERCOT assessment dataset.

## Project structure

```
.
├── app.py                                          # Streamlit app (preferred deliverable)
├── offer_curves.py                                 # Shared cleaning, forecast, and plot logic
├── Untitled.ipynb                                  # Jupyter notebook with EDA and charts
├── Generator Offer Curve Data for Assessment.csv   # Input data (not in repo if large — place locally)
├── requirements.txt
└── offer_curve_forecast.html                       # Generated standalone plot (after running)
```

## Setup

Requires **Python 3.11+**.

```bash
cd assessment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Place `Generator Offer Curve Data for Assessment.csv` in the project root if it is not already there.

## Run the Streamlit app (preferred)

```bash
streamlit run app.py
```

Open the URL shown in the terminal (typically http://localhost:8501).

To deploy publicly, push this repo to GitHub and use [Streamlit Community Cloud](https://streamlit.io/cloud) with `app.py` as the entry point.

## Run the Jupyter notebook

```bash
jupyter notebook Untitled.ipynb
```

Run all cells to reproduce cleaning, forecasting, and the 24-panel Plotly chart.

## Export HTML plot

From the notebook (last cells) or the Streamlit app (download button), generate:

```bash
# Or from Python:
python -c "
from offer_curves import load_and_process, build_forecasts, build_offer_curve_figure, TARGET_FORECAST_DATE
_, curves, _ = load_and_process()
forecasts, _ = build_forecasts(curves, TARGET_FORECAST_DATE)
fig = build_offer_curve_figure(curves, forecasts, TARGET_FORECAST_DATE)
fig.write_html('offer_curve_forecast.html')
print('Saved offer_curve_forecast.html')
"
```

---

## Data cleaning approach

| Step | Action |
|------|--------|
| Timestamps | Parse to datetime; drop unparseable; sort |
| Duplicate rows | Remove exact duplicates |
| Duplicate timestamps | Keep last record per timestamp |
| Numeric conversion | Coerce MW, price, and limit columns |
| Missing breakpoints | Drop individual pairs with missing MW or price |
| Price outliers | Remove points outside **-100 to 500 $/MWh** |
| MW outliers | Remove MW **< 0** or **> 250** |
| Non-monotonic MW | Sort breakpoint pairs by MW within each hour |
| High/Low limits | Swap when reversed; drop rows still invalid |

## Forecast method

For each hour on **2026-05-29**:

1. **Prior-year same date** — use breakpoints from 2025-05-29 for that hour (used for all 24 hours in this dataset).
2. **Median by hour + month + weekday** — median MW/price at each breakpoint index.
3. **Median by hour** — median MW/price at each breakpoint across all history.

## Assumptions

- Same hour-of-day curves are comparable across days.
- Prior-year same-date is a strong baseline when available.
- Fixed outlier thresholds are appropriate for this unit (typical offer prices ~$20–$45/MWh; high limit ~190–200 MW).
- `Resource Status` is not used in cleaning or forecasting.
- Duplicate timestamps resolve to the **last** record after sorting.

## Future scope

The current forecast uses a simple, interpretable rules-based approach (prior-year lookup with median fallbacks). With more time and data, offer curves could be modeled more rigorously along two broad paths:

### Statistical / classical time-series methods

These work well when relationships are mostly linear and the history is relatively short:

| Method | Use case |
|--------|----------|
| **ARIMA / SARIMA** | Forecast individual price or MW series at each breakpoint with hourly/seasonal structure |
| **VAR (Vector Autoregression)** | Model multiple breakpoints jointly when prices/MW co-move across the curve |
| **Exponential smoothing (ETS)** | Smooth seasonal patterns per hour-of-day or per breakpoint |
| **Prophet / state-space models** | Handle holidays, outages, and regime changes with explicit seasonality |
| **Quantile regression** | Produce forecast intervals (e.g. P10/P50/P90 offer prices) instead of a single curve |

These methods typically need less data than deep learning and are easier to explain to market operators, but they may struggle with sharp regime shifts (e.g. fuel price spikes, unit derates) unless exogenous variables are added.

### Deep learning options

Neural sequence models can capture non-linear dependencies across time and across breakpoints:

| Model | Use case |
|-------|----------|
| **LSTM** | Learn temporal patterns in hourly offer curves over long lookback windows |
| **GRU** | Similar to LSTM with fewer parameters; often faster to train |
| **Seq2seq / encoder–decoder** | Predict the full 13-point curve for a target hour from past N days |
| **Temporal CNN / TCN** | Parallel convolutions over time for multi-breakpoint inputs |
| **Transformers** | Attention over historical days/hours when many correlated features are available |

**Data requirement:** deep learning models generally need **substantially more data** than we have here (~8,700 hourly rows / one year). A single unit-year is often insufficient to train LSTMs or GRUs reliably without overfitting. Practical DL forecasting would likely require:

- Multiple years of history for the same unit
- Pooling data across similar units (transfer learning or multi-unit training)
- Rich exogenous features (gas prices, load, outages, heat rate, LMP, weather)
- Careful validation (walk-forward, blocked cross-validation by date)

For this assessment dataset, classical or rules-based methods are a better fit; DL becomes more attractive as history length and feature breadth grow.

## AI tools disclosure

**Cursor AI (Claude)** was used to help with dataset exploration, pipeline design, Plotly visualization, Streamlit app scaffolding, and documentation. The approach and thresholds were chosen to match the assessment specification; outputs were validated against the raw CSV.

## Submission checklist

- [ ] Push code + `requirements.txt` + this README to a public GitHub repo or Drive folder
- [ ] Deploy Streamlit app and include the public URL (or submit `offer_curve_forecast.html` / screenshot)
- [ ] Submit the Google form: https://forms.gle/2f9cYXsdmSc7bYq97
- [ ] Email the same materials to srv@newgridconsulting.com
