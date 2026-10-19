# ML methodology

The GA4 project forecasts daily website sessions using calendar features, lagged sessions, and rolling means. Three estimators are compared: Random Forest, Histogram Gradient Boosting, and standardized Ridge regression. Walk-forward validation evaluates seven-day forecast blocks to reduce look-ahead bias. Historical residuals inform a bias adjustment and an approximate 80% empirical error interval. Coverage is not guaranteed and should be measured prospectively.

**Portfolio policy:** Public code and methodology only; do not publish credentials, private analytics exports, candidate data, or confidential client information.
