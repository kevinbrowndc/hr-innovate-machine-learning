# Initial seven-day forecast: October 11–17, 2026

This is the first recorded live evaluation of the HR Innovate daily sessions forecasting project. Publication of these aggregate business metrics was authorized by the project owner.

## Predicted vs. actual sessions

| Date | Day | Predicted | Actual | Error (predicted − actual) |
|---|---|---:|---:|---:|
| 2026-10-11 | Sunday | 75 | 83 | -8 |
| 2026-10-12 | Monday | 150 | 141 | +9 |
| 2026-10-13 | Tuesday | 170 | 116 | +54 |
| 2026-10-14 | Wednesday | 162 | 150 | +12 |
| 2026-10-15 | Thursday | 188 | 123 | +65 |
| 2026-10-16 | Friday | 123 | 102 | +21 |
| 2026-10-17 | Saturday | 68 | 58 | +10 |
| **Total** | | **936** | **773** | **+163** |

- Weekly total overforecast: **163 sessions**, or **17.4% of predicted sessions**.
- Daily mean absolute error: **25.6 sessions**.
- Daily mean absolute percentage error (MAPE): **approximately 23.0%**.
- Largest daily absolute error: **65 sessions on Thursday, October 15**.

## Lessons learned

The initial model reproduced broad weekday/weekend patterns but overestimated most days, with the largest misses midweek. This prompted additional evaluation of model bias and forecast uncertainty.

## Follow-on model (Version 3)

The later pipeline compares Random Forest, Histogram Gradient Boosting, and Ridge models using walk-forward seven-day blocks. The October 18–24 forecast selected Random Forest; its historical backtest yielded MAE 29.8 sessions and MAPE 26.6%, with a bias adjustment of -9.2 sessions and an approximate empirical 80% error radius of ±41.9 sessions. The expected total for October 18–24 was **780 sessions**.

**Important:** These backtest metrics cannot be compared directly to the initial live-week MAPE as proof of improvement. Prospective out-of-sample evaluation on the same periods is needed to establish whether Version 3 is more accurate. The interval is empirical and not guaranteed to achieve 80% coverage.

The original model source code is not yet archived in this repository; these are the documented historical predictions and observed outcomes.
