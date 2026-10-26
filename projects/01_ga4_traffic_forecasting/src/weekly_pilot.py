"""Frozen eight-week prospective pilot. No legacy forecasts or backfilling."""
import argparse
import base64
from datetime import date, datetime, time, timedelta, timezone
import gzip
from importlib.metadata import version
import json
import os
from pathlib import Path
import pickle
import re
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from pilot_archive import GitHubArchive, Withheld, digest, encoded

CYPRUS = ZoneInfo("Asia/Nicosia")
UTC = timezone.utc
MODEL = "Random Forest"
WEEKS = 8
LAG_HOURS = 72
ROOT = Path(__file__).resolve().parent
# Load archived pure helpers only. The historical main() has a literal-newline typo.
helpers = {}
exec(compile((ROOT / "forecast_v3_ga4.py").read_text(encoding="utf-8").split("def fetch_ga4")[0],
             "archived_v3_helpers", "exec"), helpers)


def utcnow():
    return datetime.now(UTC)


def aware(value):
    if value.tzinfo is None:
        raise Withheld("Timezone-aware timestamp required")
    return value


def boundary(day):
    return datetime.combine(day, time.min, CYPRUS)


def finalized_through(now):
    return (aware(now).astimezone(CYPRUS) - timedelta(hours=LAG_HOURS)).date() - timedelta(days=1)


def scheduled_window(now):
    local = aware(now).astimezone(CYPRUS)
    return local.weekday() == 6 and local.hour == 22 and local.minute >= 30


def runtime_identity():
    return {"versions": {p: version(p) for p in ("numpy", "pandas", "scikit-learn")},
            "source_sha256": digest(b"".join((ROOT / f).read_bytes() for f in (
                "forecast_v3_ga4.py", "weekly_pilot.py", "pilot_archive.py", "pilot_email.py")))}


def validate_history(frame, start, end):
    if not {"date", "sessions"}.issubset(frame):
        raise Withheld("Daily GA4 schema missing")
    f = frame.copy()
    f["date"] = pd.to_datetime(f["date"], errors="raise")
    f["sessions"] = pd.to_numeric(f["sessions"], errors="raise")
    if f.date.duplicated().any() or f.date.isna().any():
        raise Withheld("Duplicate or missing GA4 dates")
    series = f.set_index("date").sessions.sort_index().astype(float)
    expected = pd.date_range(start, end)
    if not series.index.equals(expected):
        raise Withheld("Incomplete GA4 dates; missing observations are never zero-filled")
    values = series.to_numpy()
    if not np.isfinite(values).all() or (values < 0).any() or (values != np.floor(values)).any():
        raise Withheld("Invalid GA4 session counts")
    return series


def fetch_daily(start, end):
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, OrderBy, RunReportRequest
    from google.oauth2 import service_account
    prop = os.environ.get("GA4_PROPERTY_ID", "")
    if not prop.isdigit() or not os.environ.get("GA4_CREDENTIALS_JSON"):
        raise Withheld("GA4 configuration missing")
    info = json.loads(os.environ["GA4_CREDENTIALS_JSON"])
    if info.get("type") != "service_account":
        raise Withheld("Service-account configuration required")
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/analytics.readonly"])
    client = BetaAnalyticsDataClient(credentials=creds)
    rows, offset = [], 0
    while True:
        response = client.run_report(RunReportRequest(property=f"properties/{prop}",
            dimensions=[Dimension(name="date")], metrics=[Metric(name="sessions")],
            date_ranges=[DateRange(start_date=str(start), end_date=str(end))],
            order_bys=[OrderBy(dimension=OrderBy.DimensionOrderBy(dimension_name="date"))],
            limit=100000, offset=offset), timeout=60)
        meta = response.metadata
        if (meta.time_zone != "Asia/Nicosia" or meta.subject_to_thresholding
                or meta.data_loss_from_other_row or len(meta.sampling_metadatas)):
            raise Withheld("GA4 timezone or reporting-quality gate failed")
        for row in response.rows:
            rows.append({"date": pd.to_datetime(row.dimension_values[0].value, format="%Y%m%d"),
                         "sessions": int(row.metric_values[0].value)})
        offset += len(response.rows)
        if offset >= response.row_count:
            break
        if not response.rows:
            raise Withheld("Incomplete GA4 pagination")
    return validate_history(pd.DataFrame(rows), start, end)


def fit(history):
    if len(history) < 56:
        raise Withheld("Insufficient training history")
    X, y, origin = helpers["training_data"](history)
    return helpers["model_factory"](MODEL).fit(X, y), origin


def forecast(model, origin, history, start, bias=0):
    start = pd.Timestamp(start)
    first = history.index[-1] + pd.Timedelta(days=1)
    horizon = (start - first).days + 7
    if not 7 <= horizon <= 14:
        raise Withheld("History is too stale or overlaps target dates")
    values = helpers["recursive_forecast"](model, history, first, horizon, origin, bias=bias)
    baseline = np.resize(history.iloc[-7:].to_numpy(), horizon)
    return values[-7:], baseline[-7:]


def calibrate(history):
    """Four earlier weeks estimate bias, four later weeks estimate 80% radius."""
    last_monday = history.index[-1] - pd.Timedelta(days=history.index[-1].weekday() + 7)
    folds = []
    for weeks_ago in range(7, -1, -1):
        target = last_monday - pd.Timedelta(weeks=weeks_ago)
        train = history.loc[:target - pd.Timedelta(days=5)]
        truth = history.reindex(pd.date_range(target, periods=7))
        if truth.isna().any():
            raise Withheld("Incomplete pre-pilot calibration")
        model, origin = fit(train)
        folds.append((model, origin, train, target, truth.to_numpy()))
    early = np.concatenate([truth - forecast(m, o, h, d)[0] for m, o, h, d, truth in folds[:4]])
    bias = float(np.median(early))
    later = np.concatenate([np.abs(truth - forecast(m, o, h, d, bias)[0])
                            for m, o, h, d, truth in folds[4:]])
    return bias, float(np.quantile(later, .80, method="higher"))


def bootstrap(store, pilot_id, start, history, now):
    if start.weekday() != 0 or boundary(start) <= aware(now):
        raise Withheld("Pilot must start on a future Cyprus Monday")
    if history.index[-1].date() > finalized_through(now):
        raise Withheld("Training data not finalized")
    key = f"{pilot_id}/pilot.json"
    if store.read(key):
        raise Withheld("Pilot already frozen")
    bias, radius = calibrate(history)
    model, origin = fit(history)
    model_bytes = gzip.compress(pickle.dumps(model, protocol=5), mtime=0)
    scale = float(np.abs(history.iloc[7:].to_numpy() - history.iloc[:-7].to_numpy()).mean())
    spec = {"schema": 1, "pilot_id": pilot_id, "start": start.isoformat(), "weeks": WEEKS,
            "timezone": "Asia/Nicosia", "model_family": MODEL, "runtime": runtime_identity(),
            "origin": origin.isoformat(), "training_end": str(history.index[-1].date()),
            "created_at": aware(now).isoformat(), "bias": bias, "radius": radius,
            "interval_label": "80% pre-pilot empirical interval; coverage not guaranteed",
            "mase_scale": scale, "history_sha256": digest(history.to_csv().encode()),
            "model_sha256": digest(model_bytes), "model_gzip_base64": base64.b64encode(model_bytes).decode()}
    # One create-only record atomically binds weights, calibration and protocol.
    saved, persisted = store.create(key, encoded(spec))
    if persisted >= boundary(start):
        raise Withheld("Pilot was persisted too late; cannot activate")
    return spec, digest(saved)


def load_pilot(store, pilot_id):
    saved = store.read(f"{pilot_id}/pilot.json")
    if saved is None:
        raise Withheld("Pilot has not been initialized")
    body, persisted = saved
    spec = json.loads(body)
    start = date.fromisoformat(spec["start"])
    if (spec["pilot_id"] != pilot_id or spec["weeks"] != WEEKS or spec["model_family"] != MODEL
            or persisted >= boundary(start) or datetime.fromisoformat(spec["created_at"]) >= boundary(start)
            or spec["runtime"] != runtime_identity()):
        raise Withheld("Frozen pilot identity, runtime or timestamp mismatch")
    compressed = base64.b64decode(spec["model_gzip_base64"])
    if digest(compressed) != spec["model_sha256"]:
        raise Withheld("Frozen model integrity check failed")
    # Only unpickle our authenticated private archive, after identity/hash checks.
    return spec, digest(body), pickle.loads(gzip.decompress(compressed))


def week_key(pilot_id, start):
    return f"{pilot_id}/forecasts/{start.isoformat()}.json"


def validate_saved(saved, spec, spec_hash, target):
    if saved is None:
        raise Withheld("Required genuine saved forecast missing; no backfill")
    body, persisted = saved
    record = json.loads(body)
    dates = [(target + timedelta(days=i)).isoformat() for i in range(7)]
    if (record["dates"] != dates or record["pilot_sha256"] != spec_hash
            or persisted >= boundary(target)
            or datetime.fromisoformat(record["created_at"]) >= boundary(target)
            or date.fromisoformat(record["history_end"]) >= target):
        raise Withheld("Forecast provenance invalid or forecast saved too late")
    for field in ("predicted", "lower", "upper", "baseline"):
        values = np.asarray(record[field], dtype=float)
        if values.shape != (7,) or not np.isfinite(values).all() or (values < 0).any():
            raise Withheld("Invalid saved forecast values")
    if ((np.array(record["lower"]) > record["predicted"]).any()
            or (np.array(record["upper"]) < record["predicted"]).any()):
        raise Withheld("Invalid saved prediction intervals")
    return record


def freeze_forecast(store, spec, spec_hash, model, history, target, now):
    if boundary(target) <= aware(now) or target.weekday() != 0:
        raise Withheld("Never generate a historical or started forecast")
    elapsed = (target - date.fromisoformat(spec["start"])).days
    if elapsed < 0 or elapsed % 7 or elapsed > 63:
        raise Withheld("Outside eight-week pilot and two reporting-tail outlooks")
    if history.index[-1].date() != finalized_through(now):
        raise Withheld("Required finalized history unavailable")
    key = week_key(spec["pilot_id"], target)
    existing = store.read(key)
    if existing:
        return validate_saved(existing, spec, spec_hash, target)
    predicted, baseline = forecast(model, pd.Timestamp(spec["origin"]), history, target, spec["bias"])
    record = {"schema": 1, "pilot_sha256": spec_hash, "created_at": aware(now).isoformat(),
              "history_end": str(history.index[-1].date()),
              "history_sha256": digest(history.to_csv().encode()),
              "kind": "pilot" if elapsed < 56 else "post-pilot outlook (excluded from scoring)",
              "dates": [(target + timedelta(days=i)).isoformat() for i in range(7)],
              "predicted": predicted.tolist(), "baseline": baseline.tolist(),
              "lower": np.maximum(0, predicted - spec["radius"]).tolist(),
              "upper": (predicted + spec["radius"]).tolist()}
    saved = store.create(key, encoded(record))
    return validate_saved(saved, spec, spec_hash, target)


def metrics(actual, predicted, scale):
    a, p = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    if a.shape != p.shape or not len(a) or not np.isfinite(a).all() or (a < 0).any():
        raise Withheld("Complete aligned actuals required")
    error = p - a
    positive = a > 0
    mae = float(np.abs(error).mean())
    return {"mae": mae, "mape": float(np.mean(np.abs(error[positive]) / a[positive]) * 100) if positive.any() else None,
            "mape_n": int(positive.sum()), "zero_days": int((~positive).sum()),
            "mase": mae / scale if np.isfinite(scale) and scale > 0 else None,
            "bias": float(error.mean())}


def evaluate(store, spec, spec_hash, actuals, now):
    first = date.fromisoformat(spec["start"])
    eligible = [first + timedelta(weeks=i) for i in range(WEEKS)
                if first + timedelta(weeks=i, days=6) <= finalized_through(now)]
    if not eligible:
        raise Withheld("No finalized prospective pilot week yet")
    weeks, all_a, all_p, all_b = [], [], [], []
    for target in eligible:
        record = validate_saved(store.read(week_key(spec["pilot_id"], target)), spec, spec_hash, target)
        truth = actuals.reindex(pd.to_datetime(record["dates"]))
        if truth.isna().any():
            raise Withheld("Required actual sessions missing; report withheld")
        model_scores = metrics(truth, record["predicted"], spec["mase_scale"])
        baseline_scores = metrics(truth, record["baseline"], spec["mase_scale"])
        coverage = float(np.mean((truth.to_numpy() >= record["lower"]) & (truth.to_numpy() <= record["upper"])))
        weeks.append({"start": str(target), "forecast": record, "actual": truth.tolist(),
                      "model": model_scores, "baseline": baseline_scores, "interval_coverage": coverage})
        all_a.extend(truth); all_p.extend(record["predicted"]); all_b.extend(record["baseline"])
    return {"weeks": weeks, "model": metrics(all_a, all_p, spec["mase_scale"]),
            "baseline": metrics(all_a, all_b, spec["mase_scale"]), "as_of": aware(now).isoformat()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["initialize", "weekly", "verify-email"])
    args = parser.parse_args()
    pilot_id = os.environ.get("PILOT_ID", "")
    if not re.fullmatch(r"[a-z0-9-]{1,60}", pilot_id):
        raise Withheld("PILOT_ID not configured")
    now = utcnow()
    if args.mode == "weekly" and not scheduled_window(now):
        print("Skipped: outside Cyprus Sunday 22:30–22:59 window")
        return
    store = GitHubArchive(os.environ.get("FORECAST_ARCHIVE_REPO"), os.environ.get("FORECAST_ARCHIVE_TOKEN"))
    if args.mode == "verify-email":
        from pilot_email import verify_transport
        configuration_hash = verify_transport()
        if not store.read(f"{pilot_id}/smtp-verified.json"):
            store.create(f"{pilot_id}/smtp-verified.json", encoded({"verified_at": now.isoformat(),
                         "configuration_sha256": configuration_hash}))
        print("SMTP TLS/login verified; no message sent")
        return
    if args.mode == "initialize":
        start = date.fromisoformat(os.environ["PILOT_START_DATE"])
        if start != now.astimezone(CYPRUS).date() + timedelta(days=1) or not scheduled_window(now):
            raise Withheld("Initialize on the Sunday before pilot start, at 22:30 Cyprus time")
        history = fetch_daily(date(2022, 5, 16), finalized_through(now))
        bootstrap(store, pilot_id, start, history, now)
    spec, spec_hash, model = load_pilot(store, pilot_id)
    target = now.astimezone(CYPRUS).date() + timedelta(days=1)
    if target > date.fromisoformat(spec["start"]) + timedelta(days=63):
        print("Pilot and reporting tail finished; no new forecasts")
        return
    history = fetch_daily(date(2022, 5, 16), finalized_through(now))
    forward = freeze_forecast(store, spec, spec_hash, model, history, target, utcnow())
    # Forecast persistence happens even when actuals are unavailable or delivery disabled.
    evaluation = evaluate(store, spec, spec_hash, history, utcnow())
    from pilot_email import deliver_report
    deliver_report(store, spec, evaluation, forward)
    print("Prospective records processed; private outputs not logged")


if __name__ == "__main__":
    try:
        main()
    except Withheld as exc:
        print(f"WITHHELD: {exc}")
        raise SystemExit(2)
    except Exception:
        # Google/SMTP/HTTP exceptions can contain private payloads or authentication details.
        print("WITHHELD: operation failed; inspect configuration privately")
        raise SystemExit(2)
