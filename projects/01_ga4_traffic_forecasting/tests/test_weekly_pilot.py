import copy
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import weekly_pilot as p
import pilot_email as mail
from pilot_archive import GitHubArchive, Withheld, encoded, digest

UTC = timezone.utc
ISSUED = datetime(2026, 11, 1, 20, 35, tzinfo=UTC)
START = date(2026, 11, 2)


class MemoryArchive:
    def __init__(self, now=ISSUED):
        self.now, self.data = now, {}
    def read(self, key):
        return self.data.get(key)
    def create(self, key, body):
        if key in self.data:
            raise Withheld("immutable")
        self.data[key] = body, self.now
        return self.data[key]
    def json(self, key):
        obj = self.read(key)
        return None if obj is None else (json.loads(obj[0]), obj[1])


class SimpleModel:
    def predict(self, X):
        return np.maximum(0, np.asarray(X["lag1"]) + 1)


@pytest.fixture
def history():
    dates = pd.date_range(end=p.finalized_through(ISSUED), periods=200)
    return pd.Series(50 + np.arange(200) % 7, index=dates, dtype=float)


@pytest.fixture
def pilot(history, monkeypatch):
    monkeypatch.setattr(p, "calibrate", lambda h: (0., 10.))
    monkeypatch.setattr(p, "fit", lambda h: (SimpleModel(), h.index[0]))
    store = MemoryArchive()
    spec, sha = p.bootstrap(store, "test-pilot", START, history, ISSUED)
    loaded, loaded_sha, model = p.load_pilot(store, "test-pilot")
    assert sha == loaded_sha and loaded == spec
    return store, spec, sha, model


@pytest.mark.parametrize("stamp,active", [
    ("2026-07-05T19:35:00+00:00", True),
    ("2026-07-05T20:35:00+00:00", False),
    ("2026-10-25T20:35:00+00:00", True),
    ("2026-10-25T19:35:00+00:00", False),
    ("2026-03-29T19:35:00+00:00", True),
    ("2026-11-02T20:35:00+00:00", False),
    ("2026-11-01T20:29:00+00:00", False),
])
def test_cyprus_schedule_dst(stamp, active):
    assert p.scheduled_window(datetime.fromisoformat(stamp)) == active


def test_readiness_and_timezone():
    assert p.finalized_through(ISSUED) == date(2026, 10, 28)
    with pytest.raises(Withheld):
        p.scheduled_window(datetime(2026, 11, 1))


@pytest.mark.parametrize("bad", ["gap", "duplicate", "nan", "negative", "fraction"])
def test_data_gates(history, bad):
    frame = history.rename("sessions").rename_axis("date").reset_index()
    if bad == "gap": frame = frame.iloc[1:]
    elif bad == "duplicate": frame = pd.concat([frame, frame.iloc[:1]])
    else: frame.loc[0, "sessions"] = {"nan": np.nan, "negative": -1, "fraction": .2}[bad]
    with pytest.raises(Withheld):
        p.validate_history(frame, history.index[0], history.index[-1])


def test_frozen_model_no_retraining(pilot, history, monkeypatch):
    store, spec, sha, model = pilot
    monkeypatch.setattr(p, "fit", lambda _: pytest.fail("No pilot refitting"))
    before = store.read("test-pilot/pilot.json")[0]
    record = p.freeze_forecast(store, spec, sha, model, history, START, ISSUED)
    assert len(record["predicted"]) == 7
    assert record["predicted"][0] == history.iloc[-1] + 5  # Four-day readiness bridge.
    assert np.all(np.array(record["lower"]) >= 0)
    assert store.read("test-pilot/pilot.json")[0] == before
    assert p.freeze_forecast(store, spec, sha, model, history, START, ISSUED) == record


def test_late_forecast_never_backfilled(pilot, history):
    store, spec, sha, model = pilot
    with pytest.raises(Withheld, match="historical"):
        p.freeze_forecast(store, spec, sha, model, history, START, p.boundary(START))
    assert store.read(p.week_key("test-pilot", START)) is None


def test_crossing_deadline_during_persistence(pilot, history):
    store, spec, sha, model = pilot
    store.now = p.boundary(START)
    with pytest.raises(Withheld, match="too late"):
        p.freeze_forecast(store, spec, sha, model, history, START, ISSUED)


def test_model_and_runtime_integrity(pilot, monkeypatch):
    store, spec, sha, model = pilot
    monkeypatch.setattr(p, "runtime_identity", lambda: {"wrong": True})
    with pytest.raises(Withheld, match="mismatch"):
        p.load_pilot(store, "test-pilot")


def test_duplicate_bootstrap(pilot, history):
    with pytest.raises(Withheld, match="already frozen"):
        p.bootstrap(pilot[0], "test-pilot", START, history, ISSUED)


def test_saved_only_evaluation_missing_week_withholds(pilot, history, monkeypatch):
    store, spec, sha, model = pilot
    now = ISSUED + timedelta(weeks=2)
    actual = pd.Series(60., index=pd.date_range(START, periods=7))
    with pytest.raises(Withheld, match="saved forecast missing"):
        p.evaluate(store, spec, sha, actual, now)
    p.freeze_forecast(store, spec, sha, model, history, START, ISSUED)
    monkeypatch.setattr(p, "forecast", lambda *a, **k: pytest.fail("Never reconstruct predictions for scoring"))
    result = p.evaluate(store, spec, sha, actual, now)
    assert len(result["weeks"]) == 1
    expected = np.abs(np.array(result["weeks"][0]["forecast"]["predicted"]) - 60).mean()
    assert result["model"]["mae"] == expected
    with pytest.raises(Withheld, match="saved forecast missing"):
        p.evaluate(store, spec, sha, actual, now + timedelta(weeks=1))


def test_missing_actuals_withholds(pilot, history):
    store, spec, sha, model = pilot
    p.freeze_forecast(store, spec, sha, model, history, START, ISSUED)
    actual = pd.Series(60., index=pd.date_range(START, periods=6))
    with pytest.raises(Withheld, match="actual sessions missing"):
        p.evaluate(store, spec, sha, actual, ISSUED + timedelta(weeks=2))


def test_zero_mape_and_invalid_mase():
    scores = p.metrics([0, 10], [2, 12], 0)
    assert scores == dict(mae=2., mape=20., mape_n=1, zero_days=1, mase=None, bias=2.)
    assert p.metrics([0], [1], float("nan"))["mape"] is None
    assert p.metrics([2, 4], [4, 6], 2)["mase"] == 1


def test_stored_baseline_is_recursive_and_unchanged(pilot, history):
    store, spec, sha, model = pilot
    record = p.freeze_forecast(store, spec, sha, model, history, START, ISSUED)
    np.testing.assert_array_equal(record["baseline"], np.resize(history.iloc[-7:].to_numpy(), 11)[-7:])


def test_preperiod_calibration_boundaries(history, monkeypatch):
    fitted, predicted = [], []
    def fake_fit(train):
        fitted.append(train.index[-1])
        return None, train.index[0]
    def fake_forecast(model, origin, train, target, bias=0):
        assert train.index[-1] == target - pd.Timedelta(days=5)
        predicted.append((target, bias))
        return np.zeros(7) + bias, np.zeros(7)
    monkeypatch.setattr(p, "fit", fake_fit)
    monkeypatch.setattr(p, "forecast", fake_forecast)
    bias, radius = p.calibrate(history)
    assert len(fitted) == 8 and len(predicted) == 8
    assert max(d for d, _ in predicted) + pd.Timedelta(days=6) <= history.index[-1]
    assert all(b == 0 for _, b in predicted[:4])
    assert all(b == bias for _, b in predicted[4:]) and radius >= 0


@pytest.fixture
def report(pilot, history):
    store, spec, sha, model = pilot
    forward = p.freeze_forecast(store, spec, sha, model, history, START, ISSUED)
    actual = pd.Series(60., index=pd.date_range(START, periods=7))
    evaluation = p.evaluate(store, spec, sha, actual, ISSUED + timedelta(weeks=2))
    return store, spec, evaluation, forward


def test_html_chart_and_forward_table(report):
    store, spec, evaluation, forward = report
    html, png = mail.render(evaluation, forward, spec["interval_label"])
    assert 'cid:forecast-chart' in html and "MASE" in html
    assert all(d in html for d in forward["dates"])
    assert png.startswith(b'\x89PNG')
    assert "katerina@" not in html


def test_email_disabled_never_connects(report, monkeypatch):
    monkeypatch.delenv("EMAIL_DELIVERY_ENABLED", raising=False)
    monkeypatch.setattr(mail, "connection", lambda _: pytest.fail("Disabled email connected"))
    with pytest.raises(Withheld, match="disabled"):
        mail.deliver_report(*report)


def test_test_only_recipient_and_no_duplicate_send(report, monkeypatch):
    store, spec, evaluation, forward = report
    config = {"SMTP_FROM": "sender@example.test"}
    monkeypatch.setenv("EMAIL_DELIVERY_ENABLED", "true")
    monkeypatch.setenv("EMAIL_TO", "katerina@hrinnovate.org")  # Must have no effect.
    monkeypatch.setattr(mail, "configuration", lambda: config)
    store.create('test-pilot/smtp-verified.json', encoded({"configuration_sha256": mail.fingerprint(config)}))
    sent = []
    class Server:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def send_message(self, message, **kwargs):
            sent.append((message, kwargs))
            return {}
    monkeypatch.setattr(mail, "connection", lambda _: Server())
    mail.deliver_report(*report)
    assert sent[0][0]["To"] == "kevinbrown.dc@gmail.com"
    assert sent[0][1]["to_addrs"] == ["kevinbrown.dc@gmail.com"]
    assert sent[0][0]["Cc"] is None and sent[0][0]["Bcc"] is None
    with pytest.raises(Withheld, match="already attempted"):
        mail.deliver_report(*report)
    assert len(sent) == 1


class Response:
    def __init__(self, code, obj): self.status_code, self.obj = code, obj
    def json(self): return self.obj


def test_public_archive_rejected():
    class Session:
        headers = {}
        def request(self, *a, **k): return Response(200, {"private": False})
    with pytest.raises(Withheld, match="private repository"):
        GitHubArchive("owner/public", "fake-token", session=Session())


def test_archive_modified_record_rejected():
    class Session:
        headers = {}
        def request(self, method, url, **kwargs):
            if url.endswith('/repos/owner/private'): return Response(200, {"private": True})
            if url.endswith('/commits'): return Response(200, [{}, {}])
            return Response(200, {"sha": "abc"})
    store = GitHubArchive("owner/private", "fake-token", session=Session())
    with pytest.raises(Withheld, match="modified"):
        store.read("pilot/forecast.json")


def test_archive_create_never_updates_existing():
    archive = object.__new__(GitHubArchive)
    archive.read = lambda _: (b"existing", ISSUED)
    with pytest.raises(Withheld, match="replacement prohibited"):
        archive.create("pilot/week.json", b"new")


def test_archive_create_has_no_update_sha_or_timestamp(monkeypatch):
    archive = object.__new__(GitHubArchive)
    archive.branch = "main"
    reads = iter([None, (b"new", ISSUED)])
    archive.read = lambda _: next(reads)
    calls = []
    archive.request = lambda *args, **kwargs: (calls.append(kwargs) or Response(201, {}))
    archive.create("pilot/week.json", b"new")
    assert set(calls[0]["json"]) == {"message", "branch", "content"}


def test_no_public_artifact_or_email_recipient_configuration():
    root = Path(__file__).resolve().parents[3]
    workflow = (root / '.github/workflows/ga4_weekly_pilot.yml').read_text()
    assert 'upload-artifact' not in workflow and 'pull_request_target' not in workflow
    assert "vars.PILOT_ENABLED == 'true'" in workflow
    assert "secrets.GA4_CREDENTIALS_JSON" in workflow
    assert "secrets.FORECAST_ARCHIVE_TOKEN" in workflow
    assert "EMAIL_TO" not in workflow and "katerina@" not in workflow


def test_unverified_email_never_connects(report, monkeypatch):
    monkeypatch.setenv("EMAIL_DELIVERY_ENABLED", "true")
    monkeypatch.setattr(mail, "configuration", lambda: {"SMTP_FROM": "sender@example.test"})
    monkeypatch.setattr(mail, "connection", lambda _: pytest.fail("Unverified SMTP connected"))
    with pytest.raises(Withheld, match="verification"):
        mail.deliver_report(*report)


def test_ambiguous_smtp_failure_blocks_retry(report, monkeypatch):
    store, spec, evaluation, forward = report
    config = {"SMTP_FROM": "sender@example.test"}
    monkeypatch.setenv("EMAIL_DELIVERY_ENABLED", "true")
    monkeypatch.setattr(mail, "configuration", lambda: config)
    store.create('test-pilot/smtp-verified.json', encoded({"configuration_sha256": mail.fingerprint(config)}))
    def fail(_):
        raise TimeoutError("Simulated timeout")
    monkeypatch.setattr(mail, "connection", fail)
    with pytest.raises(TimeoutError):
        mail.deliver_report(*report)
    with pytest.raises(Withheld, match="already attempted"):
        mail.deliver_report(*report)
    assert not any(k.endswith('.sent.json') for k in store.data)


def test_real_estimator_full_pilot_and_reporting_tail(history):
    # Genuine RF fitting/calibration on synthetic data, with one frozen model for all ten issues.
    store = MemoryArchive()
    p.bootstrap(store, "integration", START, history, ISSUED)
    spec, sha, model = p.load_pilot(store, "integration")
    original_weights = digest(pickle_bytes := p.pickle.dumps(model))
    full_dates = pd.date_range(history.index[0], periods=len(history) + 70)
    full = pd.Series(50 + np.arange(len(full_dates)) % 7, index=full_dates, dtype=float)
    for i in range(10):
        now = ISSUED + timedelta(weeks=i)
        store.now = now
        available = full.loc[:pd.Timestamp(p.finalized_through(now))]
        record = p.freeze_forecast(store, spec, sha, model, available, START + timedelta(weeks=i), now)
        assert (record['kind'] == 'pilot') == (i < 8)
        if i < 2:
            with pytest.raises(Withheld, match="No finalized"):
                p.evaluate(store, spec, sha, available, now)
        else:
            evaluation = p.evaluate(store, spec, sha, available, now)
            assert len(evaluation['weeks']) == i - 1
    assert evaluation['model']['mape_n'] == 56
    assert digest(p.pickle.dumps(model)) == original_weights
    assert len([k for k in store.data if '/forecasts/' in k]) == 10
    assert evaluation['baseline']['mae'] == 0


@pytest.mark.parametrize("timezone_name,thresholded", [("UTC", False), ("Asia/Nicosia", True)])
def test_ga4_quality_gates(monkeypatch, timezone_name, thresholded):
    from google.analytics import data_v1beta
    from google.oauth2 import service_account
    monkeypatch.setenv("GA4_PROPERTY_ID", "311711993")
    monkeypatch.setenv("GA4_CREDENTIALS_JSON", '{"type":"service_account"}')
    monkeypatch.setattr(service_account.Credentials, "from_service_account_info", lambda *a, **k: object())
    response = SimpleNamespace(metadata=SimpleNamespace(time_zone=timezone_name,
        subject_to_thresholding=thresholded, data_loss_from_other_row=False, sampling_metadatas=[]))
    monkeypatch.setattr(data_v1beta, "BetaAnalyticsDataClient", lambda **k:
                        SimpleNamespace(run_report=lambda *a, **k: response))
    with pytest.raises(Withheld, match="quality gate"):
        p.fetch_daily(START, START)
