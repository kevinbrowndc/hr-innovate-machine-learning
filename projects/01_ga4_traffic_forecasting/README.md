# GA4 Traffic Forecasting

**Status:** Implemented.

Daily sessions forecasting with the GA4 Data API and optional offline CSV input. Feature engineering uses calendar, lagged traffic, and rolling history. Random Forest, Histogram Gradient Boosting, and Ridge models are compared with walk-forward seven-day validation. The selected model forecasts a week of sessions with approximate 80% empirical error bounds and renders a whisker chart.

**Code:** `src/forecast_v3_ga4.py`

**Configuration:** `GA4_PROPERTY_ID` and Google Application Default Credentials. Do not commit JSON credentials or private GA4 exports.

**Outputs:** CSV forecasts and local PNG charts; outputs are excluded from Git tracking.

## V4 acquisition-source comparison

V4 is an experimental companion to V3, with exclusive acquisition categories, independently reconciled GA4 totals, nested seven-day walk-forward evaluation, and a seasonal baseline. **Live comparison completed:** eight matched holdout weeks gave V4 MAE 30.52 / MAPE 27.79%, versus adapted V3 MAE 29.74 / MAPE 24.40%. V4 did not improve accuracy; keep V3 alongside it. The October V4 retrospective forecast totals 840.73 sessions. See [execution report](reports/v3_vs_v4_comparison.md). The original V3 source and artifacts are preserved; comparisons use a documented in-memory syntax adapter.

From the repository root, install `projects/01_ga4_traffic_forecasting/requirements-v4-dev.txt` in an isolated Python environment. For the exact Python 3.12 verification environment use `requirements-v4-lock.txt` in the same directory. Run:

```text
python -m pytest projects/01_ga4_traffic_forecasting/tests -q
python projects/01_ga4_traffic_forecasting/src/forecast_v4_ga4.py --fixture --cutoff 2026-10-17 --outer-weeks 4 --inner-weeks 2 --output local-v4/demo
```

The demo is artificial test data, not HR Innovate evidence. Each output directory must be new. For live extraction, reuse `GA4_PROPERTY_ID` and `GOOGLE_APPLICATION_CREDENTIALS` (or existing ADC), then run:

```text
python projects/01_ga4_traffic_forecasting/src/forecast_v4_ga4.py --start 2022-05-16 --cutoff 2026-10-17 --reconciliation-tolerance 2 --output local-v4/oct17-retrospective
```

For private offline data, supply `--sources-csv local-v4/sources.csv --aggregate-csv local-v4/aggregate.csv`. Source columns: `date,sessionSource,sessionMedium,sessionDefaultChannelGroup,sessions`. Aggregate columns: `date,sessions`, independently exported, one row per calendar day. Dates must be ISO daily dates, counts nonnegative integers. Do not concatenate reports with overlapping dimensions. Missing aggregate dates and unreconciled source totals stop the run. Exact equality is the default; the reviewed live extract has small reported-count differences, so the command above explicitly permits up to two sessions per day without rescaling. The report documents the reconciliation evidence. Keep private CSVs, outputs and executed notebooks under ignored `local-v4/`.

Open [V4 notebook](notebooks/HR_Innovate_GA4_V4.ipynb) using this environment. It defaults to clearly labeled synthetic fixtures, provides source EDA, nested evaluation and the requested black/blue/green comparison chart. Set `GA4_V4_SOURCES_CSV` and `GA4_V4_AGGREGATE_CSV` to private input paths, plus `GA4_V4_RECONCILIATION_TOLERANCE=2` for the reviewed extract. Optionally set `GA4_V4_RUN` to the matching private run directory to reuse results after cutoff, tolerance and input-hash checks. Do not commit executed live outputs. No uncertainty coverage or improvement toward 15%/10% is asserted without real holdout evidence.

Outputs include total and channel forecasts, model selections, daily backtest rows, MAE/MAPE/bias, weekly percentage errors, weekday errors and channel errors. V4 considers seasonal, Ridge, Random Forest and Gradient Boosting with training-only 0%/2% small-channel grouping. Default eight inner/eight outer weeks need at least 168 daily observations. The report explains zero-day handling, the V3 adapter, retrospective limitations and the protocol for freezing a prospective pair.
