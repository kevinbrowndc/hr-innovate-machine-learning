"""HR Innovate GA4 weekly sessions forecast, v3.
Run: python forecast_v3_ga4.py
Uses Google Application Default Credentials or --credentials path.
Optional offline mode: --csv path.csv (columns date, sessions).
"""
import argparse
import os
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt

FEATURES = ["dow", "month", "dayofyear", "weekend", "trend",
            "lag1", "lag7", "lag14", "lag28", "avg7", "avg28"]

def features(history, date, origin):
    vals = history.reindex(pd.date_range(date-pd.Timedelta(days=28),
                                         date-pd.Timedelta(days=1), freq="D"))
    if vals.isna().any():
        raise ValueError("Missing history required for lags; inspect daily GA4 export.")
    a = vals.to_numpy(dtype=float)
    return [date.dayofweek, date.month, date.dayofyear,
            int(date.dayofweek >= 5), (date-origin).days,
            a[-1], a[-7], a[-14], a[-28], a[-7:].mean(), a.mean()]

def training_data(series):
    origin = series.index.min()
    dates = series.index[28:]
    X = pd.DataFrame([features(series.loc[:d-pd.Timedelta(days=1)], d, origin)
                      for d in dates], columns=FEATURES)
    y = series.loc[dates].to_numpy()
    return X, y, origin

def model_factory(name):
    if name == "Ridge":
        return make_pipeline(StandardScaler(), Ridge(alpha=20))
    if name == "Random Forest":
        return RandomForestRegressor(n_estimators=160, min_samples_leaf=5,
                                     max_features=0.8, random_state=42, n_jobs=-1)
    if name == "Gradient Boosting":
        return HistGradientBoostingRegressor(max_iter=130, max_leaf_nodes=12,
                                              l2_regularization=10, random_state=42)
    raise ValueError(name)

def recursive_forecast(model, history, start, days, origin, bias=0):
    h = history.copy()
    result = []
    for d in pd.date_range(start, periods=days, freq="D"):
        row = pd.DataFrame([features(h, d, origin)], columns=FEATURES)
        p = max(0.0, float(model.predict(row)[0]) + bias)
        result.append(p)
        h.loc[d] = p
    return np.array(result)

def fetch_ga4(property_id, credentials_path=None):
    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest
        from google.oauth2 import service_account
    except ImportError as exc:
        raise RuntimeError("Install GA4 dependencies: pip install google-analytics-data google-auth") from exc
    if credentials_path:
        if not os.path.isfile(credentials_path):
            raise FileNotFoundError(f"Credentials file not found: {credentials_path}")
        creds = service_account.Credentials.from_service_account_file(
            credentials_path, scopes=["https://www.googleapis.com/auth/analytics.readonly"])
        client = BetaAnalyticsDataClient(credentials=creds)
    else:
        # ADC supports the existing GOOGLE_APPLICATION_CREDENTIALS environment variable.
        client = BetaAnalyticsDataClient()
    # Exclude today: GA4 daily totals may still be incomplete.
    end = (datetime.now().date() - timedelta(days=1)).isoformat()
    rows = []
    offset = 0
    while True:
        response = client.run_report(RunReportRequest(
            property=f"properties/{property_id}",
            dimensions=[Dimension(name="date")], metrics=[Metric(name="sessions")],
            date_ranges=[DateRange(start_date="2022-05-10", end_date=end)],
            limit=100000, offset=offset))
        for row in response.rows:
            rows.append({"date": pd.to_datetime(row.dimension_values[0].value, format="%Y%m%d"),
                         "sessions": int(row.metric_values[0].value)})
        offset += len(response.rows)
        if not response.rows or offset >= response.row_count:
            break
    if not rows:
        raise RuntimeError("GA4 returned no daily session rows; check property access.")
    result = pd.DataFrame(rows)
    print(f"GA4 API: retrieved {len(result)} dates through {end} from property {property_id}.")
    return result

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=None, help="Optional offline CSV instead of GA4 API")
    ap.add_argument("--credentials", default=None, help="Existing service-account JSON path; omit for ADC")
    ap.add_argument("--property-id", default=os.environ.get("GA4_PROPERTY_ID"))
    ap.add_argument("--backtest-weeks", type=int, default=8)
    args = ap.parse_args()
    if not args.csv and not args.property_id:\n        ap.error("Set GA4_PROPERTY_ID or supply --property-id when using the live GA4 API.")\n    df = pd.read_csv(args.csv) if args.csv else fetch_ga4(args.property_id, args.credentials)
    if not {"date", "sessions"}.issubset(df.columns):
        raise ValueError("CSV needs columns named date and sessions.")
    df["date"] = pd.to_datetime(df["date"], errors="raise").dt.normalize()
    df["sessions"] = pd.to_numeric(df["sessions"], errors="raise")
    if (df["sessions"] < 0).any():
        raise ValueError("Sessions cannot be negative.")
    if df["date"].duplicated().any():
        raise ValueError("Duplicate dates: export one total sessions row per date.")
    series = df.set_index("date")["sessions"].sort_index().astype(float)
    full_dates = pd.date_range(series.index.min(), series.index.max(), freq="D")
    # Missing historical dates should not be silently treated as zero.
    missing = full_dates.difference(series.index)
    if len(missing) and all(d <= series.index.min() + pd.Timedelta(days=30) for d in missing):
        series = series.loc[missing.max() + pd.Timedelta(days=1):]
        print(f"Trimmed early incomplete export; using continuous data from {series.index.min().date()}.")
        missing = pd.date_range(series.index.min(), series.index.max(), freq="D").difference(series.index)
    if len(missing):
        raise ValueError(f"Missing dates ({len(missing)}): {list(missing[:10].date)}. "
                         "Do not silently treat missing API dates as zero.")
    if len(series) < 140:
        raise ValueError("At least 140 continuous daily observations required.")
    if series.index.max() >= pd.Timestamp.today().normalize():
        print("WARNING: Latest date may be incomplete; verify it is a finished GA4 day.")

    # Backtest on nonoverlapping 7-day windows, using only information available at each origin.
    n_weeks = min(args.backtest_weeks, (len(series)-90)//7)
    if n_weeks < 4:
        raise ValueError("Not enough history for four complete backtest weeks.")
    names = ["Ridge", "Random Forest", "Gradient Boosting"]
    errors = {name: [] for name in names}
    predictions = {name: [] for name in names}
    actuals = []
    for w in range(n_weeks, 0, -1):
        cutoff = len(series)-7*w
        train = series.iloc[:cutoff]
        truth = series.iloc[cutoff:cutoff+7].to_numpy()
        X, y, origin = training_data(train)
        actuals.extend(truth)
        for name in names:
            model = model_factory(name)
            model.fit(X, y)
            pred = recursive_forecast(model, train, series.index[cutoff], 7, origin)
            errors[name].extend(truth-pred)
            predictions[name].extend(pred)
    actuals = np.array(actuals)
    # MAPE excludes zero-session days; MAE is also reported.
    def mape(pred):
        mask = actuals > 0
        return float(np.mean(np.abs(actuals[mask]-np.asarray(pred)[mask]) /
                             actuals[mask]) * 100) if mask.any() else float("inf")
    ranking = sorted(names, key=lambda name: np.mean(np.abs(errors[name])))
    print("\nWalk-forward backtest (7-day blocks; lower is better)")
    for name in ranking:
        print(f"{name:20s} MAE={np.mean(np.abs(errors[name])):.1f} "
              f"sessions | MAPE={mape(predictions[name]):.1f}%")
    best = ranking[0]
    residuals = np.asarray(errors[best])
    # Bias adjustment is estimated only from backtest residuals.
    bias = float(np.median(residuals))
    corrected_errors = residuals-bias
    # Empirical symmetric 80% interval; validate coverage on future weeks.
    radius = float(np.quantile(np.abs(corrected_errors), 0.80))
    X, y, origin = training_data(series)
    final_model = model_factory(best)
    final_model.fit(X, y)
    dates = pd.date_range(series.index.max()+pd.Timedelta(days=1), periods=7)
    central = recursive_forecast(final_model, series, dates[0], 7, origin, bias=bias)
    out = pd.DataFrame({"date": dates.date, "low": np.maximum(0, np.floor(central-radius)).astype(int),
                        "expected": np.rint(central).astype(int),
                        "high": np.ceil(central+radius).astype(int)})
    out.to_csv("forecast_v2_results.csv", index=False)
    print(f"\nSelected: {best}; bias correction: {bias:+.1f}; "
          f"80% empirical error radius: ±{radius:.1f} sessions")
    print("These are approximate prediction intervals, not guaranteed 80% coverage.")
    print(out.to_string(index=False))
    print(f"Expected weekly total: {out.expected.sum()} sessions")

    # Preserve the previous forecast before overwriting it on the next run.
    # On subsequent runs, compare the frozen prior forecast with GA4 actuals.
    previous_path = "forecast_v2_previous.csv"
    current_path = "forecast_v2_results.csv"
    # Read previous forecast from disk if available, otherwise use this week's forecast.
    from pathlib import Path
    existing = Path(current_path)
    if existing.exists():
        previous = pd.read_csv(existing)
        previous.to_csv(previous_path, index=False)
    else:
        previous = None

    def draw_comparison(frame, filename, title):
        f = frame.copy()
        f["date"] = pd.to_datetime(f["date"])
        f["actual"] = f["date"].map(series)
        xx = np.arange(len(f))
        pred = f["expected"].to_numpy(dtype=float)
        low = f["low"].to_numpy(dtype=float)
        high = f["high"].to_numpy(dtype=float)
        observed = f["actual"].to_numpy(dtype=float)
        fig, ax = plt.subplots(figsize=(11, 5.7), facecolor="black")
        ax.set_facecolor("black")
        width = 0.34
        ax.bar(xx-width/2, pred, width, color="#238bff", label="Predicted")
        available = np.isfinite(observed)
        if available.any():
            ax.bar(xx[available]+width/2, observed[available], width,
                   color="#24b76a", label="Actual (GA4)")
        # White capped whiskers show the low-to-high forecast interval.
        ax.errorbar(xx-width/2, pred,
                    yerr=np.vstack((np.maximum(0, pred-low), np.maximum(0, high-pred))),
                    fmt="none", ecolor="white", elinewidth=1.8, capsize=5,
                    capthick=1.8, label="Approx. 80% interval", zorder=5)
        for i, val in enumerate(pred):
            ax.text(i-width/2, max(high[i], val)+3, str(int(round(val))),
                    ha="center", va="bottom", color="white", fontsize=10, weight="bold")
        for i in xx[available]:
            ax.text(i+width/2, observed[i]+3, str(int(round(observed[i]))),
                    ha="center", va="bottom", color="white", fontsize=10, weight="bold")
        ax.set_xticks(xx, f["date"].dt.strftime("%a %m/%d"), color="white")
        ax.tick_params(axis="y", colors="white")
        ax.grid(axis="y", linestyle="--", alpha=.35)
        ax.set_axisbelow(True)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ceiling = max(float(np.max(high)), float(np.nanmax(observed)) if available.any() else 0)
        ax.set_ylim(0, max(20, ceiling*1.25))
        ax.set_title(title, color="white", pad=16, fontsize=16, weight="bold")
        ax.legend(facecolor="black", labelcolor="white", edgecolor="none")
        fig.tight_layout()
        fig.savefig(filename, dpi=180, facecolor="black")
        plt.show()
        plt.close(fig)

    draw_comparison(out, "forecast_v2_chart.png",
                    "HR Innovate | Predicted vs. actual sessions")
    if previous is not None:
        previous_dates = pd.to_datetime(previous["date"])
        if previous_dates.isin(series.index).any():
            draw_comparison(previous, "forecast_v2_previous_comparison.png",
                            "HR Innovate | Previous forecast vs. actual")
            print("Saved forecast_v2_previous_comparison.png")
    out.to_csv(current_path, index=False)
    print("Saved forecast_v2_results.csv and forecast_v2_chart.png")

if __name__ == "__main__":
    main()