# Original GA4 forecasting model — October 10, 2026

## Provenance

This document records the **original design** of the seven-day GA4 forecast, based on the contemporaneous *HR Innovate GA4 Executive Forecast — October 2026* presentation. It is **not** a recovered source-code file or a claim that the original fitted model has been reproduced.

## Model

- **Estimator:** Random Forest regression with **seven direct outputs** (one output for each forecast day), rather than recursive one-day predictions.
- **Source:** Google Analytics 4 Data API; observed daily sessions, active users, and page views.
- **Historical range:** May 10, 2022 through October 10, 2026. The incomplete opening period was excluded; May 11–15, 2022 were missing.
- **Predictors:** Lagged sessions at 1, 7, and 14 days; rolling statistics over 7 and 28 days; calendar inputs.
- **Leakage precaution:** No actual sessions from the future forecast week were used as model inputs.

## Original seven-day forecast

| Date | Predicted sessions |
|---|---:|
| October 11, 2026 | 75 |
| October 12, 2026 | 150 |
| October 13, 2026 | 170 |
| October 14, 2026 | 162 |
| October 15, 2026 | 188 |
| October 16, 2026 | 123 |
| October 17, 2026 | 68 |
| **Total** | **936** |

See [original forecast vs. actual results](initial_forecast_oct11_17_2026.md) for evaluation and [the V3 source](../src/forecast_v3_ga4.py) for the later implemented pipeline.

## Reproducibility status

The original notebook or exact Python source has not been recovered. Hyperparameters, training window construction, and random seed cannot be verified from the presentation. Reconstructing this model would be a **new reimplementation**, not the original code. The archived seven daily predictions remain the original recorded output.
