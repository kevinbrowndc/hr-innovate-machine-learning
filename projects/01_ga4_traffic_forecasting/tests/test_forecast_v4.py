import os
import re
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace as NS

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import forecast_v4_ga4 as v4


@pytest.fixture
def data():
    return v4.synthetic_fixture(days=98)


@pytest.mark.parametrize("s,m,c,expected", [
    ("linkedin.com", "cpc", "Paid Search", "LinkedIn"),
    ("www.linkedin.com", "referral", "Referral", "LinkedIn"),
    ("notlinkedin.com", "referral", "Referral", "Referral"),
    ("(direct)", "(none)", "Direct", "Direct"),
    ("google", "organic", "Organic Search", "Organic Search"),
    ("google", "cpc", "Paid Search", "Paid Search"),
    (None, None, None, "Other")])
def test_classification(s, m, c, expected):
    assert v4.classify(s, m, c) == expected


def test_response_parsing():
    row = NS(dimension_values=[NS(value=v) for v in ["20261017", "google", "organic", "Organic Search"]],
             metric_values=[NS(value="21")])
    parsed = v4.parse_response(NS(rows=[row]), v4.DIMENSIONS)
    assert parsed[0]["sessions"] == 21
    assert parsed[0]["date"] == pd.Timestamp("2026-10-17")
    with pytest.raises(ValueError):
        v4.parse_response(NS(rows=[row]), ["date"])


def test_reconciliation_and_missing_cells(data):
    raw, agg = data
    panel, total = v4.prepare(raw, agg, "2026-10-17")
    np.testing.assert_array_equal(panel.sum(axis=1), total)
    removed = raw.iloc[0]
    raw = raw.iloc[1:].copy()
    agg.loc[agg.date == removed.date, "sessions"] -= removed.sessions
    panel, _ = v4.prepare(raw, agg, "2026-10-17")
    assert panel.iloc[0]["Direct"] == 0


def test_missing_source_values(data):
    raw, agg = data
    raw.loc[0, v4.DIMENSIONS[1:]] = None
    panel, total = v4.prepare(raw, agg, "2026-10-17")
    assert "Other" in panel
    np.testing.assert_array_equal(panel.sum(axis=1), total)


@pytest.mark.parametrize("bad", ["duplicate", "missing_date", "mismatch", "negative", "nan", "fractional"])
def test_invalid_data(data, bad):
    raw, agg = data
    if bad == "duplicate":
        raw = pd.concat([raw, raw.iloc[:1]])
    elif bad == "missing_date":
        agg = agg.iloc[1:].copy()
    elif bad == "mismatch":
        agg.loc[0, "sessions"] += 1
    else:
        raw["sessions"] = raw.sessions.astype(float)
        raw.loc[0, "sessions"] = {"negative": -1, "nan": np.nan, "fractional": 1.5}[bad]
    with pytest.raises(ValueError):
        v4.prepare(raw, agg, "2026-10-17")


def test_future_poison_does_not_affect_selection_or_forecast(data):
    raw, agg = data
    panel, _ = v4.prepare(raw, agg, "2026-10-17")
    before, choice = v4.forecast_v4(panel, inner_weeks=1)
    poison = raw.tail(1).copy()
    poison["date"] = pd.Timestamp("2026-10-18")
    poison["sessionSource"] = "new.example"
    poison["sessions"] = -999
    future = pd.DataFrame({"date": [pd.Timestamp("2026-10-18")], "sessions": [-999]})
    after_panel, _ = v4.prepare(pd.concat([raw, poison]), pd.concat([agg, future]), "2026-10-17")
    after, choice2 = v4.forecast_v4(after_panel, inner_weeks=1)
    pd.testing.assert_frame_equal(before, after)
    assert choice == choice2
    assert len(before) == 7 and before.index[0] == pd.Timestamp("2026-10-18")
    assert before.index[-1] == pd.Timestamp("2026-10-24")
    assert np.isfinite(before.to_numpy()).all() and (before.to_numpy() >= 0).all()


def test_future_only_category_does_not_enter_training(data):
    panel, _ = v4.prepare(*data, "2026-10-17")
    panel["Unseen"] = 0
    panel.loc[panel.index[-1], "Unseen"] = 1000
    assert "Unseen" not in v4.group_channels(panel.iloc[:-1], 0)


def test_reproducible_backtest_and_origin_boundaries(data, monkeypatch):
    panel, total = v4.prepare(*data, "2026-10-17")
    seen = []
    original = v4.predict
    def recording(series, name, bias=0):
        seen.append(series.index.max())
        return original(series, name, bias)
    monkeypatch.setattr(v4, "predict", recording)
    a, sources, choices = v4.backtest(panel, total, outer_weeks=1, inner_weeks=1)
    b, _, _ = v4.backtest(panel, total, outer_weeks=1, inner_weeks=1)
    pd.testing.assert_frame_equal(a, b)
    assert max(seen) == total.index[-8]
    assert (a.date > a.cutoff).all()
    assert len(a) == 21
    np.testing.assert_allclose(sources.groupby("date").predicted.sum(),
                               a.loc[a.model == "V4", "predicted"])


def test_metrics_zero_days_and_bias():
    m = v4.metrics([0, 10], [2, 12])
    assert m == dict(mae=2., bias_sessions=2., mape_pct=20., zero_actual_days=1, total_error_pct=40.)
    assert v4.metrics([0], [0])["mape_pct"] is None


def test_zero_aggregate_day_is_valid_only_with_reconciliation(data):
    raw, agg = data
    day = agg.date.iloc[20]
    raw = raw.loc[raw.date != day]
    agg.loc[agg.date == day, "sessions"] = 0
    panel, total = v4.prepare(raw, agg, "2026-10-17")
    assert panel.loc[day].sum() == total.loc[day] == 0
    with pytest.raises(ValueError, match="Missing aggregate dates"):
        v4.prepare(raw, agg.loc[agg.date != day], "2026-10-17")


def test_explicit_reconciliation_tolerance_retains_reported_counts(data):
    raw, agg = data
    agg.loc[0, "sessions"] -= 2
    with pytest.raises(ValueError, match="reconciliation"):
        v4.prepare(raw, agg, "2026-10-17")
    panel, total = v4.prepare(raw, agg, "2026-10-17", reconciliation_tolerance=2)
    assert panel.iloc[0].sum() - total.iloc[0] == 2
    agg.loc[0, "sessions"] -= 1
    with pytest.raises(ValueError, match="reconciliation"):
        v4.prepare(raw, agg, "2026-10-17", reconciliation_tolerance=2)


def test_tolerance_cannot_hide_missing_positive_day(data):
    raw, agg = data
    day = agg.date.iloc[0]
    raw = raw.loc[raw.date != day]
    agg.loc[agg.date == day, "sessions"] = 1
    with pytest.raises(ValueError, match="Missing source report dates"):
        v4.prepare(raw, agg, "2026-10-17", reconciliation_tolerance=2)


def test_forecast_cache_matches_uncached_and_isolates_results(data):
    _, total = v4.prepare(*data, "2026-10-17")
    cached = v4.predict(total, "Ridge")
    np.testing.assert_allclose(cached, v4._predict_uncached(total, "Ridge"))
    cached[0] = -999
    assert v4.predict(total, "Ridge")[0] >= 0
    changed = total.copy()
    changed.iloc[-1] += 100
    np.testing.assert_allclose(v4.predict(changed, "Ridge"), v4._predict_uncached(changed, "Ridge"))


def test_v4_selection_scores_independent_aggregate(data, monkeypatch):
    panel, total = v4.prepare(*data, "2026-10-17")
    monkeypatch.setattr(v4, "MODELS", ["Seasonal"])
    _, info = v4.forecast_v4(panel, inner_weeks=1, shares=(0,), aggregate=total + 100)
    expected = np.abs(panel.iloc[-14:-7].sum(axis=1).to_numpy()
                      - (total.iloc[-7:].to_numpy() + 100)).mean()
    assert info["inner_mae"] == pytest.approx(expected)


def test_outputs_cannot_overwrite_existing_forecast(data, tmp_path):
    sentinel = tmp_path / "forecast.csv"
    sentinel.write_text("preserve me")
    with pytest.raises(FileExistsError):
        v4.run(*data, "2026-10-17", tmp_path, 1, 1, True)
    assert sentinel.read_text() == "preserve me"


def test_end_to_end_exports_independent_reconciliation(data, tmp_path):
    import json
    raw, agg = data
    agg.loc[0, "sessions"] -= 1
    output = tmp_path / "new_run"
    forecast, rows = v4.run(raw, agg, "2026-10-17", output, 1, 1, True, 2)
    reconciliation = pd.read_csv(output / "reconciliation.csv")
    assert reconciliation["difference"].sum() == 1
    assert reconciliation["aggregate"].sum() == agg.sessions.sum()
    assert len(pd.read_csv(output / "forecast.csv")) == len(forecast) == 7
    assert len(rows) == 21
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["fixture"] and manifest["reconciliation_tolerance_sessions"] == 2


def test_v3_adapter_matches_helpers(data):
    # Independent extraction up to fetch_ga4 avoids the broken main entirely.
    code = (v4.PROJECT / "src/forecast_v3_ga4.py").read_text(encoding="utf-8").split("def fetch_ga4")[0]
    namespace = {}
    exec(compile(code, "historical_v3_helpers", "exec"), namespace)
    _, total = v4.prepare(*data, "2026-10-17")
    X, y, origin = namespace["training_data"](total)
    model = namespace["model_factory"]("Ridge").fit(X, y)
    expected = namespace["recursive_forecast"](model, total, total.index[-1] + pd.Timedelta(days=1), 7, origin)
    np.testing.assert_allclose(v4.predict(total, "Ridge"), expected)


def test_api_pagination_and_reporting_loss(monkeypatch):
    from google.analytics.data_v1beta.types import RunReportResponse, Row, DimensionValue, MetricValue, ResponseMetaData
    monkeypatch.setenv("GA4_PROPERTY_ID", "fixture-property")
    calls = []
    class Client:
        def run_report(self, req):
            calls.append(req)
            dims = ["20261017", "google", "organic", "Organic Search"] if len(req.dimensions) == 4 else ["20261017"]
            # Two distinct pages for the joint report; one for aggregate.
            if req.offset:
                dims[1] = "bing"
            return RunReportResponse(rows=[Row(dimension_values=[DimensionValue(value=x) for x in dims],
                metric_values=[MetricValue(value="2")])], row_count=2 if len(dims) == 4 else 1)
    raw, agg = v4.fetch_ga4("2026-10-17", "2026-10-17", Client())
    assert len(raw) == 2 and len(agg) == 1
    assert [r.offset for r in calls] == [0, 1, 0]
    assert all(r.date_ranges[0].end_date == "2026-10-17" for r in calls)
    class LossClient:
        def run_report(self, req):
            return RunReportResponse(metadata=ResponseMetaData(subject_to_thresholding=True))
    with pytest.raises(ValueError, match="reporting loss"):
        v4.fetch_ga4("2026-10-17", "2026-10-17", LossClient())


def test_credentials_excluded_from_tracked_files():
    root = v4.PROJECT.parents[1]
    paths = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0")
    for name in filter(None, paths):
        assert not name.endswith((".pem", ".key")) and Path(name).name != ".env"
        text = (root / name).read_text(encoding="utf-8", errors="replace")
        assert '-----BEGIN ' + 'PRIVATE KEY-----' not in text
        assert '"private_key"' + ':' not in text
        assert not re.search(r'gh[pousr]_[A-Za-z0-9]{30,}|AIza[0-9A-Za-z_-]{30,}', text)
        if name.endswith("HR_Innovate_GA4_V4.ipynb"):
            import json
            notebook = json.loads(text)
            assert all(not c.get("outputs") for c in notebook["cells"])
    assert subprocess.run(["git", "check-ignore", "credentials.json", ".env", "local-v4/private.csv"],
                          cwd=root, capture_output=True).returncode == 0
