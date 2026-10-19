# HR Innovate Machine Learning

Public portfolio of applied machine learning projects.

## GA4 traffic forecasting
Implemented: live GA4 API retrieval, calendar and lag features, Random Forest, Gradient Boosting, Ridge regression, seven-day walk-forward evaluation, bias adjustment, and approximate 80% prediction intervals.

Source: `projects/01_ga4_traffic_forecasting/src/forecast_v3_ga4.py`

Install dependencies with `pip install -r requirements.txt`. Set `GA4_PROPERTY_ID` and configure Google Application Default Credentials, then run the source script.

## Recruit CRM analytics
Planned. No CRM model has been implemented yet.

## Privacy
Never commit service account credentials, private analytics exports, candidate data, or other confidential records. Public code is intended to be reusable without company datasets.

## Historical forecast evaluation

The first live forecast (October 11–17, 2026) predicted 936 sessions versus 773 actual, an overforecast of 163 sessions. [Read the daily comparison and lessons learned](projects/01_ga4_traffic_forecasting/reports/initial_forecast_oct11_17_2026.md). The subsequent V3 forecast and uncertainty ranges are [archived here](projects/01_ga4_traffic_forecasting/reports/v3_forecast_oct18_24_2026.csv).
