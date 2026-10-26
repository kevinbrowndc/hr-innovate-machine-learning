"""Executive HTML email, private inline chart, and a single hard-coded test recipient."""
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import parseaddr
from html import escape
import io
import os
import smtplib
import ssl

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from pilot_archive import Withheld, digest, encoded

TEST_RECIPIENT = "kevinbrown.dc@gmail.com"


def configuration():
    keys = ("SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM")
    config = {k: os.environ.get(k, "") for k in keys}
    if not all(config.values()) or any("\n" in v or "\r" in v for v in config.values()):
        raise Withheld("SMTP secrets missing or invalid")
    if config["SMTP_PORT"] not in ("465", "587"):
        raise Withheld("Only TLS SMTP ports 465 and 587 are supported")
    if parseaddr(config["SMTP_FROM"])[1] != config["SMTP_FROM"] or "@" not in config["SMTP_FROM"]:
        raise Withheld("SMTP_FROM must be one plain email address")
    return config


def fingerprint(config):
    return digest(encoded({k: v for k, v in config.items() if k != "SMTP_PASSWORD"}))


def connection(config):
    context = ssl.create_default_context()
    if config["SMTP_PORT"] == "465":
        server = smtplib.SMTP_SSL(config["SMTP_HOST"], 465, timeout=30, context=context)
    else:
        server = smtplib.SMTP(config["SMTP_HOST"], 587, timeout=30)
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
    try:
        server.login(config["SMTP_USERNAME"], config["SMTP_PASSWORD"])
    except Exception:
        server.close()
        raise
    return server


def verify_transport():
    config = configuration()
    with connection(config):
        pass
    return fingerprint(config)


def fmt(value, suffix=""):
    return "N/A" if value is None else f"{value:.2f}{suffix}"


def render(evaluation, forward, interval_label):
    if not evaluation.get("weeks") or len(forward.get("dates", [])) != 7:
        raise Withheld("Complete evaluation and forward forecast required")
    week = evaluation["weeks"][-1]
    record = week["forecast"]
    x = np.arange(7)
    fig, ax = plt.subplots(figsize=(10, 5.2), facecolor="black")
    ax.set_facecolor("black")
    for offset, values, color, label in [(-.18, record["predicted"], "#238bff", "Predicted"),
                                          (.18, week["actual"], "#24b76a", "Actual (GA4)")]:
        bars = ax.bar(x + offset, values, .36, color=color, label=label)
        ax.bar_label(bars, fmt="%.1f", color="white", padding=4)
    labels = [datetime.fromisoformat(d).strftime("%a %d %b") for d in record["dates"]]
    ax.set_xticks(x, labels, color="white")
    ax.tick_params(axis="y", colors="white")
    ax.set_ylim(0, max(1, max(record["predicted"] + week["actual"])) * 1.22)
    ax.grid(axis="y", linestyle="--", alpha=.35)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.legend(facecolor="black", labelcolor="white")
    ax.set_title(f"HR Innovate | Saved forecast vs actual sessions\n{record['dates'][0]} to {record['dates'][-1]}", color="white")
    fig.tight_layout()
    out = io.BytesIO()
    fig.savefig(out, format="png", dpi=130, facecolor="black")
    plt.close(fig)
    m, b = evaluation["model"], evaluation["baseline"]
    score_rows = "".join(f"<tr><td>{label}</td><td>{fmt(values['mae'])}</td><td>{fmt(values['mape'], '%')}</td>"
                         f"<td>{fmt(values['mase'])}</td><td>{fmt(values['bias'])}</td></tr>"
                         for label, values in [("Frozen Random Forest", m), ("Saved seasonal-naive", b)])
    forward_rows = "".join(f"<tr><td>{escape(d)}</td><td>{p:.1f}</td><td>{low:.1f}–{high:.1f}</td></tr>"
                           for d, p, low, high in zip(forward["dates"], forward["predicted"], forward["lower"], forward["upper"]))
    html = f"""<!doctype html><html><body style="margin:0;background:#f1f4f8;font-family:Arial,sans-serif;color:#152439">
    <main style="max-width:800px;margin:auto;padding:28px;background:white">
    <p style="color:#52637b">TEST DELIVERY · HR INNOVATE · CYPRUS LOCAL DATES</p>
    <h1>Weekly website traffic forecast</h1>
    <p><strong>{len(evaluation['weeks'])} of 8 finalized pilot weeks</strong> scored from forecasts archived before their target dates.</p>
    <p>Latest evaluated week: {record['dates'][0]}–{record['dates'][-1]}. The current unfinished week is not scored.</p>
    <table cellpadding="9" cellspacing="0" border="1" style="border-collapse:collapse;width:100%">
    <tr><th>Model</th><th>MAE sessions</th><th>MAPE</th><th>MASE</th><th>Daily bias</th></tr>{score_rows}</table>
    <p>Scores above cover all finalized pilot weeks. MAPE uses {m['mape_n']} nonzero-actual days and excludes {m['zero_days']} zero days.
    MASE uses the fixed pre-pilot seven-day seasonal scale; N/A means the scale was zero or invalid. Positive bias means overforecasting.</p>
    <img src="cid:forecast-chart" alt="Saved predicted and actual daily sessions" style="width:100%;max-width:760px">
    <p>Latest-week interval coverage: {week['interval_coverage']:.0%}. {escape(interval_label)}.</p>
    <h2>Forward seven-day outlook</h2><p>{escape(forward['kind'])}. Expected total: <strong>{sum(forward['predicted']):.1f} sessions</strong>.</p>
    <table cellpadding="9" cellspacing="0" border="1" style="border-collapse:collapse;width:100%">
    <tr><th>Cyprus date</th><th>Expected sessions</th><th>Prediction interval</th></tr>{forward_rows}</table>
    <p>Forward predictions were saved before the target period. They are not observed traffic. GA4 actuals may still be revised after the 72-hour readiness buffer.</p>
    <p style="font-size:12px;color:#52637b">Test recipient only: {TEST_RECIPIENT}. No organizational delivery is enabled.</p>
    </main></body></html>"""
    return html, out.getvalue()


def deliver_report(store, spec, evaluation, forward):
    if os.environ.get("EMAIL_DELIVERY_ENABLED") != "true":
        raise Withheld("Delivery disabled; forecasts retained privately")
    config = configuration()
    verified = store.json(f"{spec['pilot_id']}/smtp-verified.json")
    if verified is None or verified[0].get("configuration_sha256") != fingerprint(config):
        raise Withheld("SMTP configuration has not passed verification")
    html, chart = render(evaluation, forward, spec["interval_label"])
    key = f"{spec['pilot_id']}/deliveries/{forward['dates'][0]}"
    if store.read(key + ".claim.json"):
        raise Withheld("Delivery already attempted; no automatic duplicate or ambiguous retry")
    message = EmailMessage()
    message["From"] = config["SMTP_FROM"]
    message["To"] = TEST_RECIPIENT
    message["Subject"] = "[TEST] HR Innovate weekly traffic pilot"
    message.set_content("Private test report. Open the HTML version for the saved-forecast comparison and forward outlook.")
    message.add_alternative(html, subtype="html")
    message.get_payload()[-1].add_related(chart, maintype="image", subtype="png", cid="<forecast-chart>")
    store.create(key + ".claim.json", encoded({"attempted_at": datetime.now(timezone.utc).isoformat(),
                 "recipient": TEST_RECIPIENT, "report_sha256": digest(html.encode())}))
    with connection(config) as server:
        refused = server.send_message(message, from_addr=config["SMTP_FROM"], to_addrs=[TEST_RECIPIENT])
        if refused:
            raise Withheld("SMTP recipient rejected")
    store.create(key + ".sent.json", encoded({"accepted_at": datetime.now(timezone.utc).isoformat(),
                                             "recipient": TEST_RECIPIENT}))
