"""Cutoff-safe acquisition forecasts. Raw data and generated outputs stay local."""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import types

import numpy as np
import pandas as pd

PROJECT = Path(__file__).resolve().parents[1]
DIMENSIONS = ["date", "sessionSource", "sessionMedium", "sessionDefaultChannelGroup"]
MODELS = ["Seasonal", "Ridge", "Random Forest", "Gradient Boosting"]


def v3_adapter():
    """Load only V3's pure model helpers; repair its known literal-newline typo in memory.

    Never execute main(), API calls or V3's forecast-overwriting output code.
    """
    source = (PROJECT / "src/forecast_v3_ga4.py").read_text(encoding="utf-8")
    source = source.replace('args.property_id:\\n        ap.error',
                            'args.property_id:\n        ap.error').replace(
        'live GA4 API.")\\n    df', 'live GA4 API.")\n    df')
    tree = ast.parse(source)
    keep = {"features", "training_data", "model_factory", "recursive_forecast"}
    tree.body = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))
                 or (isinstance(n, ast.FunctionDef) and n.name in keep)
                 or (isinstance(n, ast.Assign) and any(
                     isinstance(t, ast.Name) and t.id == "FEATURES" for t in n.targets))]
    module = types.ModuleType("v3_compatibility")
    exec(compile(tree, "v3_compatibility", "exec"), module.__dict__)
    return module


V3 = v3_adapter()


def parse_response(response, dimensions):
    rows = []
    for row in response.rows:
        if len(row.dimension_values) != len(dimensions) or len(row.metric_values) != 1:
            raise ValueError("Unexpected GA4 response schema")
        item = dict(zip(dimensions, [v.value for v in row.dimension_values]))
        item["date"] = pd.to_datetime(item["date"], format="%Y%m%d", errors="raise")
        item["sessions"] = int(row.metric_values[0].value)
        if item["sessions"] < 0:
            raise ValueError("Negative sessions")
        rows.append(item)
    return rows


def fetch_ga4(start, end, client=None):
    """Reuse V3's ADC/service-account library and environment configuration.

    Query one joint source/medium/channel report plus an independent daily total.
    Reject thresholded/sampled/high-cardinality reports instead of filling lost data.
    """
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest, OrderBy
    property_id = os.environ.get("GA4_PROPERTY_ID")
    if not property_id:
        raise RuntimeError("GA4_PROPERTY_ID is not configured")
    client = client or BetaAnalyticsDataClient()
    frames = []
    for dimensions in [DIMENSIONS, ["date"]]:
        rows, offset = [], 0
        while True:
            response = client.run_report(RunReportRequest(
                property=f"properties/{property_id}",
                dimensions=[Dimension(name=d) for d in dimensions],
                metrics=[Metric(name="sessions")],
                date_ranges=[DateRange(start_date=str(start), end_date=str(end))],
                order_bys=[OrderBy(dimension=OrderBy.DimensionOrderBy(dimension_name=d))
                           for d in dimensions], limit=100000, offset=offset))
            meta = response.metadata
            if (meta.subject_to_thresholding or meta.data_loss_from_other_row
                    or len(meta.sampling_metadatas)):
                raise ValueError("GA4 reporting loss/thresholding/sampling requires investigation")
            page = parse_response(response, dimensions)
            rows.extend(page)
            offset += len(page)
            if offset >= response.row_count:
                break
            if not page:
                raise ValueError("GA4 pagination ended before row_count")
        if not rows:
            raise ValueError("Empty GA4 report")
        frames.append(pd.DataFrame(rows))
    return tuple(frames)


def classify(source, medium, channel):
    s, m, c = [str(v).strip().lower() if pd.notna(v) else "(not set)"
               for v in (source, medium, channel)]
    # Priority is exclusive: paid LinkedIn is LinkedIn, never also Paid Search.
    host = s.removeprefix("https://").removeprefix("http://").split("/")[0]
    if host in {"linkedin", "lnkd.in", "linkedin.com"} or host.endswith(".linkedin.com"):
        return "LinkedIn"
    if c == "direct" or (s == "(direct)" and m in {"(none)", "(not set)"}):
        return "Direct"
    if c == "organic search" or m == "organic":
        return "Organic Search"
    if c == "paid search":
        return "Paid Search"
    if c == "referral" or m == "referral":
        return "Referral"
    return "Other"


def validate_frame(frame, keys):
    frame = frame.copy()
    if not set(keys + ["sessions"]).issubset(frame.columns):
        raise ValueError("Missing required columns")
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    if frame["date"].isna().any() or (frame["date"] != frame["date"].dt.normalize()).any():
        raise ValueError("Dates must be non-null daily dates")
    if frame["date"].dt.tz is not None:
        raise ValueError("Use timezone-free GA4 property calendar dates")
    frame["sessions"] = pd.to_numeric(frame["sessions"], errors="raise")
    a = frame["sessions"].to_numpy(dtype=float)
    if not np.isfinite(a).all() or (a < 0).any() or (a != np.floor(a)).any():
        raise ValueError("Sessions must be finite nonnegative integers")
    for key in keys:
        if key != "date":
            frame[key] = frame[key].fillna("(not set)").astype(str).str.strip().replace("", "(not set)")
    if frame.duplicated(keys).any():
        raise ValueError("Duplicate dimension keys; do not combine overlapping reports")
    return frame.sort_values("date")


def prepare(raw, aggregate, cutoff, reconciliation_tolerance=0):
    # Truncate BEFORE validation, grouping, source discovery or model selection.
    cutoff = pd.Timestamp(cutoff)
    if (not isinstance(reconciliation_tolerance, int)
            or not 0 <= reconciliation_tolerance <= 2):
        raise ValueError("Reconciliation tolerance must be an integer from 0 to 2 sessions")
    raw = raw.loc[pd.to_datetime(raw.date) <= cutoff].copy()
    aggregate = aggregate.loc[pd.to_datetime(aggregate.date) <= cutoff].copy()
    raw = validate_frame(raw, DIMENSIONS)
    aggregate = validate_frame(aggregate, ["date"])
    total = aggregate.set_index("date").sessions.astype(float)
    if total.empty or total.index.max() != cutoff:
        raise ValueError("Aggregate data must include the cutoff")
    dates = pd.date_range(total.index.min(), cutoff)
    if not dates.equals(total.index):
        raise ValueError("Missing aggregate dates; never assume an outage is zero traffic")
    if not raw.date.isin(dates).all():
        raise ValueError("Source dates outside aggregate coverage")
    absent = dates.difference(raw.date)
    if (total.reindex(absent) > 0).any():
        raise ValueError("Missing source report dates with positive aggregate sessions")
    source_total = raw.groupby("date").sessions.sum().reindex(dates, fill_value=0)
    difference = source_total.to_numpy() - total.to_numpy()
    if (np.abs(difference) > reconciliation_tolerance).any():
        raise ValueError("Source totals exceed the permitted daily reconciliation discrepancy")
    raw["channel"] = [classify(*v) for v in raw[DIMENSIONS[1:]].itertuples(index=False, name=None)]
    panel = raw.pivot_table(index="date", columns="channel", values="sessions", aggfunc="sum")
    # Absent source cells are zero only after complete daily totals reconcile.
    panel = panel.reindex(dates).fillna(0).astype(float)
    return panel, total


def group_channels(panel, min_share):
    shares = panel.sum() / max(float(panel.to_numpy().sum()), 1)
    keep = sorted(shares[(shares >= min_share) & (shares > 0)].index.difference(["Other"]))
    result = panel.reindex(columns=keep).copy()
    result["Other"] = panel.drop(columns=keep).sum(axis=1)
    return result


def predict(series, name, bias=0):
    # Repeated inner origins fit identical histories. Cache full histories, never just dates.
    # Immutable cached results and fresh returned arrays prevent callers mutating the cache.
    return np.asarray(_predict_cached(tuple(series.index), tuple(series.to_numpy(dtype=float)),
                                     name, float(bias)), dtype=float)


@lru_cache(maxsize=512)
def _predict_cached(dates, values, name, bias):
    return tuple(_predict_uncached(pd.Series(values, index=pd.DatetimeIndex(dates)), name, bias))


@lru_cache(maxsize=128)
def _training_cached(dates, values):
    return V3.training_data(pd.Series(values, index=pd.DatetimeIndex(dates)))


def _predict_uncached(series, name, bias=0):
    if len(series) < 56:
        raise ValueError("At least 56 training days required")
    if name == "Seasonal":
        return series.iloc[-7:].to_numpy(dtype=float)
    X, y, origin = _training_cached(tuple(series.index), tuple(series.to_numpy(dtype=float)))
    model = V3.model_factory(name)
    model.fit(X.copy(), y.copy())
    return V3.recursive_forecast(model, series, series.index[-1] + pd.Timedelta(days=1), 7, origin, bias)


def inner_origins(length, weeks):
    if weeks < 1 or length - weeks * 7 < 56:
        raise ValueError("Insufficient history for requested inner weeks")
    return range(length - weeks * 7, length, 7)


def forecast_v3(total, inner_weeks=8):
    """V3 selection and median bias, refitted inside each outer origin."""
    errors = {}
    for name in MODELS[1:]:
        errors[name] = np.concatenate([
            total.iloc[i:i+7].to_numpy() - predict(total.iloc[:i], name)
            for i in inner_origins(len(total), inner_weeks)])
    best = min(errors, key=lambda n: np.abs(errors[n]).mean())
    bias = float(np.median(errors[best]))
    return predict(total, best, bias), {"model": best, "bias": bias}


def forecast_v4(panel, inner_weeks=8, shares=(0.0, 0.02), aggregate=None):
    # One model family per panel; both model and grouping policy selected in inner folds.
    scores = {}
    truth_total = panel.sum(axis=1) if aggregate is None else aggregate
    if not truth_total.index.equals(panel.index):
        raise ValueError("Aggregate training dates must match the source panel")
    for share in shares:
        for name in MODELS:
            errors = []
            for i in inner_origins(len(panel), inner_weeks):
                train = group_channels(panel.iloc[:i], share)
                pred = sum((predict(train[c], name) for c in train), np.zeros(7))
                truth = truth_total.iloc[i:i+7].to_numpy()
                errors.extend(np.abs(pred - truth))
            scores[(share, name)] = float(np.mean(errors))
    share, name = min(scores, key=scores.get)
    train = group_channels(panel, share)
    dates = pd.date_range(panel.index[-1] + pd.Timedelta(days=1), periods=7)
    channels = pd.DataFrame({c: predict(train[c], name) for c in train}, index=dates)
    return channels, {"model": name, "min_share": share, "inner_mae": scores[(share, name)]}


def metrics(actual, predicted):
    a, p = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    e = p - a
    positive = a > 0
    return {"mae": float(np.abs(e).mean()), "bias_sessions": float(e.mean()),
            "mape_pct": float((np.abs(e[positive]) / a[positive]).mean() * 100) if positive.any() else None,
            "zero_actual_days": int((~positive).sum()),
            "total_error_pct": float(e.sum() / a.sum() * 100) if a.sum() else None}


def backtest(panel, total, outer_weeks=8, inner_weeks=8, progress=None):
    if outer_weeks < 1 or len(total) - (outer_weeks + inner_weeks) * 7 < 56:
        raise ValueError("Insufficient history for nested backtest")
    rows, source_rows, selections = [], [], []
    for i in range(len(total) - outer_weeks * 7, len(total), 7):
        train, truth = total.iloc[:i], total.iloc[i:i+7]
        v3, m3 = forecast_v3(train, inner_weeks)
        channels, m4 = forecast_v4(panel.iloc[:i], inner_weeks, aggregate=train)
        selections.append({"cutoff": str(train.index[-1].date()), "v3": m3, "v4": m4})
        forecasts = {"V3 adapted": v3, "V4": channels.sum(axis=1).to_numpy(),
                     "Seasonal": predict(train, "Seasonal")}
        actual_channels = panel.iloc[i:i+7].reindex(columns=channels.columns, fill_value=0)
        kept = channels.columns.difference(["Other"])
        actual_channels["Other"] = panel.iloc[i:i+7].drop(columns=kept).sum(axis=1)
        for c in channels:
            for d, a, p in zip(truth.index, actual_channels[c], channels[c]):
                source_rows.append(dict(cutoff=train.index[-1], date=d, channel=c, actual=a, predicted=p))
        for model, values in forecasts.items():
            for d, a, p in zip(truth.index, truth, values):
                rows.append(dict(cutoff=train.index[-1], date=d, model=model, actual=a, predicted=p))
        if progress:
            progress(f"Completed historical cutoff {train.index[-1].date()}")
    return pd.DataFrame(rows), pd.DataFrame(source_rows), selections


def summarize(rows, keys):
    return pd.DataFrame([dict(zip(keys, key if isinstance(key, tuple) else (key,)),
                             **metrics(frame.actual, frame.predicted))
                         for key, frame in rows.groupby(keys)])


def synthetic_fixture(days=196, end="2026-10-17"):
    """Deliberately artificial fixture, NEVER an estimate of HR Innovate traffic."""
    rng = np.random.default_rng(42)
    dates = pd.date_range(end=end, periods=days)
    rows = []
    for d in dates:
        for source, medium, channel, base in [
            ("(direct)", "(none)", "Direct", 35),
            ("linkedin.com", "referral", "Organic Social", 20),
            ("google", "organic", "Organic Search", 25),
            ("google", "cpc", "Paid Search", 7),
            ("example.org", "referral", "Referral", 4)]:
            sessions = int(rng.poisson(base * (0.5 if d.dayofweek >= 5 else 1)))
            rows.append(dict(zip(DIMENSIONS + ["sessions"], [d, source, medium, channel, sessions])))
    raw = pd.DataFrame(rows)
    return raw, raw.groupby("date", as_index=False).sessions.sum()


def run(raw, aggregate, cutoff, output, outer_weeks=8, inner_weeks=8, fixture=False,
        reconciliation_tolerance=0):
    panel, total = prepare(raw, aggregate, cutoff, reconciliation_tolerance)
    output = Path(output)
    # A new directory is required, making forecasts immutable across repeated runs.
    output.mkdir(parents=True, exist_ok=False)
    rows, source_rows, selections = backtest(panel, total, outer_weeks, inner_weeks,
                                            progress=lambda message: print(message, flush=True))
    channels, selection = forecast_v4(panel, inner_weeks, aggregate=total)
    v3, selected_v3 = forecast_v3(total, inner_weeks)
    forecast = pd.DataFrame({"date": channels.index, "v4": channels.sum(axis=1).to_numpy(),
                             "v3_adapted": v3})
    forecast["status"] = "SYNTHETIC FIXTURE" if fixture else "retrospective simulation / as-of forecast"
    reconciliation = pd.DataFrame({"date": total.index, "aggregate": total.to_numpy(),
                                   "source_sum": panel.sum(axis=1).to_numpy()})
    reconciliation["difference"] = reconciliation["source_sum"] - reconciliation["aggregate"]
    for name, frame in {"forecast": forecast, "channels": channels.reset_index(names="date"),
                        "backtest": rows, "source_errors": source_rows, "reconciliation": reconciliation,
                        "metrics": summarize(rows, ["model"]),
                        "weekly_metrics": summarize(rows, ["model", "cutoff"]),
                        "weekday_metrics": summarize(rows.assign(weekday=rows.date.dt.day_name()), ["model", "weekday"]),
                        "channel_metrics": summarize(source_rows, ["channel"])}.items():
        frame.to_csv(output / f"{name}.csv", index=False)
    def digest(frame):
        return hashlib.sha256(frame.to_csv(index=False).encode("utf-8")).hexdigest()
    manifest = {"cutoff": str(pd.Timestamp(cutoff).date()), "fixture": fixture,
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "reconciliation_tolerance_sessions": reconciliation_tolerance,
                "input_sha256": {"sources": digest(raw), "aggregate": digest(aggregate)},
                "versions": {p: version(p) for p in ["numpy", "pandas", "scikit-learn", "google-analytics-data"]},
                "v4": selection, "v3_adapted": selected_v3, "backtest_selections": selections,
                "note": "V3 in-memory syntax adapter; no raw exports published; no calibrated intervals."}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return forecast, rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fixture", action="store_true")
    ap.add_argument("--sources-csv")
    ap.add_argument("--aggregate-csv")
    ap.add_argument("--cutoff", required=True, help="Completed GA4 property calendar day (ISO date)")
    ap.add_argument("--start", default="2022-05-10")
    ap.add_argument("--output", required=True, help="New local output directory; never overwritten")
    ap.add_argument("--outer-weeks", type=int, default=8)
    ap.add_argument("--inner-weeks", type=int, default=8)
    ap.add_argument("--reconciliation-tolerance", type=int, default=0,
                    help="Explicit permitted daily discrepancy (0-2 sessions); no rescaling")
    args = ap.parse_args()
    if args.fixture and (args.sources_csv or args.aggregate_csv):
        ap.error("Choose fixture OR private CSV inputs")
    if bool(args.sources_csv) != bool(args.aggregate_csv):
        ap.error("Supply both source and independent aggregate CSVs")
    if args.fixture:
        raw, aggregate = synthetic_fixture(end=args.cutoff)
    elif args.sources_csv:
        raw, aggregate = pd.read_csv(args.sources_csv), pd.read_csv(args.aggregate_csv)
    else:
        raw, aggregate = fetch_ga4(args.start, args.cutoff)
    forecast, rows = run(raw, aggregate, args.cutoff, args.output,
                         args.outer_weeks, args.inner_weeks, args.fixture, args.reconciliation_tolerance)
    print(forecast.to_string(index=False))
    print(summarize(rows, ["model"]).to_string(index=False))


if __name__ == "__main__":
    main()
