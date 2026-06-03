"""Load, clean, forecast, and plot generator offer curves."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

CSV_PATH = Path(__file__).resolve().parent / "Generator Offer Curve Data for Assessment.csv"
TARGET_FORECAST_DATE = pd.Timestamp("2026-05-29")
PRICE_MIN, PRICE_MAX = -100, 500
MW_MAX = 250
N_BREAKPOINTS = 13


def clean_offer_curve_data(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Clean hourly offer-curve records and return long-format breakpoint rows."""
    cleaned = df.copy()
    log: dict[str, int] = {}

    cleaned["Timestamp"] = pd.to_datetime(cleaned["Timestamp"], errors="coerce")
    log["invalid_timestamps_removed"] = int(cleaned["Timestamp"].isna().sum())
    cleaned = cleaned.dropna(subset=["Timestamp"])

    log["exact_duplicate_rows_removed"] = int(cleaned.duplicated().sum())
    cleaned = cleaned.drop_duplicates()

    log["duplicate_timestamps_removed"] = int(cleaned["Timestamp"].duplicated(keep="last").sum())
    cleaned = cleaned.sort_values("Timestamp").drop_duplicates(subset=["Timestamp"], keep="last")

    cleaned["High Limit"] = pd.to_numeric(cleaned["High Limit"], errors="coerce")
    cleaned["Low Limit"] = pd.to_numeric(cleaned["Low Limit"], errors="coerce")

    swapped = cleaned["Low Limit"] > cleaned["High Limit"]
    log["swapped_limits_fixed"] = int(swapped.sum())
    cleaned.loc[swapped, ["High Limit", "Low Limit"]] = cleaned.loc[
        swapped, ["Low Limit", "High Limit"]
    ].to_numpy()

    invalid_limits = (
        cleaned["High Limit"].isna()
        | cleaned["Low Limit"].isna()
        | (cleaned["Low Limit"] > cleaned["High Limit"])
    )
    log["invalid_limit_rows_removed"] = int(invalid_limits.sum())
    cleaned = cleaned.loc[~invalid_limits].copy()

    cleaned = cleaned.sort_values("Timestamp").reset_index(drop=True)
    cleaned["hour"] = cleaned["Timestamp"].dt.hour
    cleaned["month"] = cleaned["Timestamp"].dt.month
    cleaned["weekday"] = cleaned["Timestamp"].dt.weekday
    cleaned["date"] = cleaned["Timestamp"].dt.date

    long_parts = []
    meta_cols = ["Timestamp", "hour", "month", "weekday", "date", "High Limit", "Low Limit"]
    for i in range(1, N_BREAKPOINTS + 1):
        part = cleaned[meta_cols].copy()
        part["breakpoint"] = i
        part["mw"] = pd.to_numeric(cleaned[f"Quantity-MW{i}"], errors="coerce")
        part["price"] = pd.to_numeric(cleaned[f"Price{i}"], errors="coerce")
        long_parts.append(part)

    curves = pd.concat(long_parts, ignore_index=True)

    before = len(curves)
    curves = curves.dropna(subset=["mw", "price"])
    log["missing_breakpoints_removed"] = before - len(curves)

    price_outliers = (curves["price"] < PRICE_MIN) | (curves["price"] > PRICE_MAX)
    log["price_outliers_removed"] = int(price_outliers.sum())
    curves = curves.loc[~price_outliers]

    mw_invalid = (curves["mw"] < 0) | (curves["mw"] > MW_MAX)
    log["invalid_mw_removed"] = int(mw_invalid.sum())
    curves = curves.loc[~mw_invalid]

    curves = curves.sort_values(["Timestamp", "mw", "breakpoint"]).reset_index(drop=True)
    return cleaned, curves, log


def median_curve(group: pd.DataFrame) -> pd.DataFrame:
    """Median MW/price at each breakpoint index within a group."""
    return (
        group.groupby("breakpoint", as_index=False)
        .agg(mw=("mw", "median"), price=("price", "median"))
        .sort_values("mw")
        .reset_index(drop=True)
    )


def forecast_hour_curve(
    hour: int, curve_points: pd.DataFrame, target_date: pd.Timestamp
) -> tuple[pd.DataFrame, str]:
    target_month = target_date.month
    target_weekday = target_date.weekday()
    prior_year_date = (target_date - pd.DateOffset(years=1)).date()

    prior_year_points = curve_points[
        (curve_points["date"] == prior_year_date) & (curve_points["hour"] == hour)
    ]
    if not prior_year_points.empty:
        curve = (
            prior_year_points.sort_values(["mw", "breakpoint"])
            .drop_duplicates(subset=["mw"], keep="last")[["mw", "price", "breakpoint"]]
            .reset_index(drop=True)
        )
        return curve, "prior_year_same_date"

    month_weekday_points = curve_points[
        (curve_points["hour"] == hour)
        & (curve_points["month"] == target_month)
        & (curve_points["weekday"] == target_weekday)
    ]
    if not month_weekday_points.empty:
        return median_curve(month_weekday_points), "median_hour_month_weekday"

    hour_points = curve_points[curve_points["hour"] == hour]
    return median_curve(hour_points), "median_hour_all"


def build_forecasts(
    curve_points: pd.DataFrame, target_date: pd.Timestamp
) -> tuple[dict[int, pd.DataFrame], dict[int, str]]:
    forecast_curves: dict[int, pd.DataFrame] = {}
    forecast_methods: dict[int, str] = {}
    for hour in range(24):
        forecast_curves[hour], forecast_methods[hour] = forecast_hour_curve(
            hour, curve_points, target_date
        )
    return forecast_curves, forecast_methods


def build_offer_curve_figure(
    curve_points: pd.DataFrame,
    forecast_curves: dict[int, pd.DataFrame],
    target_date: pd.Timestamp,
) -> go.Figure:
    subplot_titles = [f"Hour {h:02d}" for h in range(24)]
    fig = make_subplots(
        rows=6,
        cols=4,
        subplot_titles=subplot_titles,
        horizontal_spacing=0.06,
        vertical_spacing=0.08,
        shared_xaxes=False,
        shared_yaxes=False,
    )

    for hour in range(24):
        row = hour // 4 + 1
        col = hour % 4 + 1

        history = curve_points[curve_points["hour"] == hour]
        for ts, day_curve in history.groupby("Timestamp"):
            fig.add_trace(
                go.Scatter(
                    x=day_curve["mw"],
                    y=day_curve["price"],
                    mode="lines",
                    line=dict(color="rgba(100, 149, 237, 0.15)", width=1),
                    showlegend=False,
                    hovertemplate=(
                        f"Hour {hour:02d}<br>MW=%{{x:.1f}}<br>Price=%{{y:.2f}}<br>"
                        f"Date={ts.strftime('%Y-%m-%d %H:%M')}<extra></extra>"
                    ),
                ),
                row=row,
                col=col,
            )

        forecast = forecast_curves[hour]
        fig.add_trace(
            go.Scatter(
                x=forecast["mw"],
                y=forecast["price"],
                mode="lines+markers",
                line=dict(color="crimson", width=2.5),
                marker=dict(size=7, color="crimson"),
                name="Forecast",
                showlegend=hour == 0,
                hovertemplate=(
                    f"Forecast Hour {hour:02d}<br>MW=%{{x:.1f}}<br>Price=%{{y:.2f}}<extra></extra>"
                ),
            ),
            row=row,
            col=col,
        )

        fig.update_xaxes(title_text="MW", row=row, col=col)
        fig.update_yaxes(title_text="Price ($/MWh)", row=row, col=col)

    fig.update_layout(
        height=1400,
        width=1200,
        title_text=f"Generator Offer Curves by Hour — Forecast for {target_date.date()}",
        template="plotly_white",
        legend=dict(orientation="h", y=-0.02),
    )
    return fig


def load_and_process(csv_path: Path | str = CSV_PATH) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    raw_df = pd.read_csv(csv_path)
    return clean_offer_curve_data(raw_df)
