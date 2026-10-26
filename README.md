# Applied Machine Learning Portfolio

Public portfolio of applied machine learning projects, including website traffic forecasting and planned CRM analytics.

## GA4 traffic forecasting

### Prospective weekly pilot (prepared; not activated)

The [eight-week pilot setup guide](projects/01_ga4_traffic_forecasting/docs/weekly_pilot.md) describes the frozen Random Forest, private create-only forecast archive, genuine saved-forecast evaluation, Cyprus scheduling, and gated Kevin-only test emails. Archive and SMTP configuration are still required. Historical files below are preserved and are not imported into prospective scoring.

Implemented: live GA4 API retrieval, calendar and lag features, Random Forest, Gradient Boosting, Ridge regression, seven-day walk-forward evaluation, bias adjustment, and approximate 80% prediction intervals.

Source: `projects/01_ga4_traffic_forecasting/src/forecast_v3_ga4.py`

Install dependencies with `pip install -r requirements.txt`. Set `GA4_PROPERTY_ID` and configure Google Application Default Credentials, then run the source script.

### Live forecast evaluation: October 18–24, 2026

**Interim results through October 22 (five days):** 613 predicted sessions versus 627 observed sessions, a net underforecast of 14 sessions (**2.3% relative to the predicted total**). Mean absolute percentage error (MAPE) across individual days: **15.1%**. Aggregate accuracy must not be confused with daily forecast accuracy: over- and underpredictions cancel in the aggregate.

| Date | Predicted | Actual | Absolute percentage error |
| --- | ---: | ---: | ---: |
| Oct 18 | 57 | 48 | 18.8% |
| Oct 19 | 145 | 120 | 20.8% |
| Oct 20 | 137 | 139 | 1.4% |
| Oct 21 | 149 | 142 | 4.9% |
| Oct 22 | 125 | 178 | 29.8% |

[Machine-readable results](projects/01_ga4_traffic_forecasting/reports/v3_actuals_oct18_22_2026.csv) · [Original seven-day forecast](projects/01_ga4_traffic_forecasting/reports/v3_forecast_oct18_24_2026.csv)

Thursday's result may still be revised by GA4. Friday and Saturday are pending. Predictions are held fixed to preserve honest out-of-sample evaluation. The interval bounds visible in earlier charts are approximate, so interval coverage is not yet formally validated.

### Historical evaluation

The first live forecast (October 11–17, 2026) predicted 936 sessions versus 773 actual, an overforecast of 163 sessions. [Daily comparison and lessons learned](projects/01_ga4_traffic_forecasting/reports/initial_forecast_oct11_17_2026.md).

## Recruit CRM analytics

Planned. No CRM model has been implemented yet.

## Privacy

Never commit service account credentials, private analytics exports, candidate data, or other confidential records. Public code is intended to be reusable without company datasets.
