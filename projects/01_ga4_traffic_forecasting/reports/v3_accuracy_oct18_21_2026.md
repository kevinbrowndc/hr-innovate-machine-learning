# V3 GA4 Forecast — Interim Accuracy (October 18–21, 2026)

This is a **four-day interim evaluation**, not a full seven-day result. The original V3 forecast in `v3_forecast_oct18_24_2026.csv` is preserved unchanged.

| Date | Predicted sessions | Actual sessions | Prediction − actual | Absolute error |
|---|---:|---:|---:|---:|
| 2026-10-18 | 57 | 48 | +9 | 9 |
| 2026-10-19 | 145 | 120 | +25 | 25 |
| 2026-10-20 | 137 | 139 | −2 | 2 |
| 2026-10-21 | 149 | 142 | +7 | 7 |
| **Total** | **488** | **449** | **+39** | **43** |

- **MAE:** 10.75 sessions per day (43 / 4).
- **MAPE:** 11.49% (mean of daily absolute percentage errors).
- **Aggregate forecast overprediction:** 39 sessions, or 8.69% of observed sessions.
- **Forecast-range coverage:** All four actuals fall inside the corresponding published V3 low–high ranges.
- **Status:** Interim, pending observed results for October 22–24.

The actual session counts (48, 120, 139, 142) were supplied by the project owner from GA4 reporting. The underlying GA4 export is not included in this public repository. These values have not been independently re-queried via the GA4 API in this update.

Source files:
- Original V3 predictions: `v3_forecast_oct18_24_2026.csv`
- Observations and daily errors: `v3_actuals_oct18_21_2026.csv`

For portfolio visualizations, label the chart **V3 predicted vs actual sessions (Oct 18–21, 2026)**, use blue for predictions and green for actuals, and do not present these interim results as full-week performance.
