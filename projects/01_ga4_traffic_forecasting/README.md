# GA4 Traffic Forecasting

**Status:** Implemented.

Daily sessions forecasting with the GA4 Data API and optional offline CSV input. Feature engineering uses calendar, lagged traffic, and rolling history. Random Forest, Histogram Gradient Boosting, and Ridge models are compared with walk-forward seven-day validation. The selected model forecasts a week of sessions with approximate 80% empirical error bounds and renders a whisker chart.

**Code:** `src/forecast_v3_ga4.py`

**Configuration:** `GA4_PROPERTY_ID` and Google Application Default Credentials. Do not commit JSON credentials or private GA4 exports.

**Outputs:** CSV forecasts and local PNG charts; outputs are excluded from Git tracking.
