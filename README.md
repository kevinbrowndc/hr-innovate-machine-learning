# HR Innovate Machine Learning

Applied machine learning for business decisions, with reproducible methods and transparent evaluation. The featured project uses **real Google Analytics 4 data** to forecast HR Innovate's website sessions seven days ahead and test whether acquisition-source modeling improves accuracy.

## Business problem

Website traffic varies with weekday patterns and acquisition activity. A dependable seven-day forecast can support marketing planning and help teams distinguish expected variation from unusual results. This project tests forecasting choices against observed traffic rather than assuming that a more detailed model will be better.

## Experiment 02: Does Acquisition-Source Modeling Improve Website Traffic Forecasting?

**Research question:** Can forecasting sessions independently by acquisition source improve seven-day website traffic predictions compared with forecasting aggregate sessions directly?

**V3 — Aggregate forecasting:** predicts total daily sessions from historical traffic, calendar patterns, lagged values and rolling averages.

**V4 — Acquisition-source forecasting:** separately predicts Direct, LinkedIn, Organic Search, Paid Search, Referral and Other traffic, then sums the predictions. The hypothesis is that additional source-level information improves total forecasting accuracy.

The controlled historical comparison uses **1,616 continuous days** of HR Innovate GA4 history (May 16, 2022–October 17, 2026), including **16,777 source/medium/channel rows**. Eight nonoverlapping seven-day test windows cover August 23–October 17, 2026: **56 evaluation days**. Both models are scored against independently retrieved aggregate GA4 sessions.

Model selection uses earlier inner validation windows at every forecast cutoff. Candidate estimators include Ridge regression, Random Forest and Histogram Gradient Boosting, with a seasonal baseline. Recursive forecasts use only past observations or prior predictions. Source grouping and V3 bias adjustment use training history only.

| Model | MAE (sessions) | MAPE | Daily bias (sessions) |
|---|---:|---:|---:|
| V3 adapted | 29.745 | 24.395% | -4.566 |
| V4 | 30.516 | 27.787% | +5.010 |
| Seasonal baseline | 39.893 | 34.044% | +1.750 |

MAE measures average absolute error; MAPE measures average percentage error; bias is predicted minus actual, so positive values indicate overprediction. MAPE excludes actual-zero days; none occurred in these aggregate holdouts.

**V3 outperformed V4 overall on both MAE and MAPE.** V4 had approximately **2.59% higher MAE** and won **four of eight weeks**. Both approaches beat the seasonal baseline on MAE and MAPE. Eight weeks do not establish statistical significance. “V3 adapted” is a documented reproduction of the implementation, not an exact reproduction of a previously fitted historical model.

### Conclusion: Hypothesis Not Supported

This V4 approach did not improve overall accuracy under the tested conditions. Retain V3 as the current forecasting benchmark and preserve V4 as a reproducible experimental alternative. The result does not establish that acquisition-source information is useless. LinkedIn's recent share increased while Organic Search's relative share declined; separate channel forecasts may introduce noise, but the experiment does not establish a causal explanation for the accuracy gap.

### Future Work: Hybrid Forecasting

The proposed next experiment keeps V3's direct total-session prediction and adds selected historical acquisition features, including LinkedIn and Organic Search trends. It would use the same leakage-controlled evaluation against V3 and the seasonal baseline. **This hybrid approach is proposed, not implemented or validated.**

Read the [experiment case study](projects/01_ga4_traffic_forecasting/reports/experiment_02_acquisition_source_forecasting.md) for data reconciliation, acquisition findings, the frozen October forecasts and limitations. The [verified technical evaluation](projects/01_ga4_traffic_forecasting/reports/v3_vs_v4_comparison.md) remains the detailed record of the live run.

## Technologies and reproducibility

Python, pandas, NumPy, scikit-learn, Matplotlib, Jupyter, pytest and the Google Analytics 4 Data API. The [project guide](projects/01_ga4_traffic_forecasting/README.md) documents setup, private data interfaces and offline fixtures; the [environment lock](projects/01_ga4_traffic_forecasting/requirements-v4-lock.txt) records the verified Python 3.12 dependencies. Synthetic fixtures demonstrate the pipeline without credentials; they do not reproduce the business metrics. Reproducing the live evaluation requires authorized access to the private data. The verified implementation passed 30 tests; this portfolio publication adds documentation only.

## Explore the project

| Resource | Purpose |
|---|---|
| [Original Jupyter notebook](projects/01_ga4_traffic_forecasting/notebooks/HR_Innovate_GA4_ML.ipynb) | Preserved original analysis |
| [V3 implementation](projects/01_ga4_traffic_forecasting/src/forecast_v3_ga4.py) | Archived aggregate forecasting code; see the technical report for the compatibility adapter |
| [V4 implementation](projects/01_ga4_traffic_forecasting/src/forecast_v4_ga4.py) | Acquisition forecasting, validation and controlled comparison |
| [V4 Jupyter notebook](projects/01_ga4_traffic_forecasting/notebooks/HR_Innovate_GA4_V4.ipynb) | Source analysis and model comparison; defaults to fixtures |
| [V3 versus V4 technical report](projects/01_ga4_traffic_forecasting/reports/v3_vs_v4_comparison.md) | Verified methodology, metrics and limitations |
| [October 18–24 forecast comparison](projects/01_ga4_traffic_forecasting/reports/v4_forecast_oct18_24_2026.csv) | Frozen original V3 values and V4 retrospective simulation; predictions, not actual traffic |

## Original forecasting exercise

The initial October 11–17, 2026 exercise predicted 936 sessions versus 773 actual sessions. Its [daily comparison and lessons learned](projects/01_ga4_traffic_forecasting/reports/initial_forecast_oct11_17_2026.md) describe a separate live-week evaluation, not the controlled V3-versus-V4 experiment above. Its metrics are not interchangeable with the later historical backtest. The [original V3 October 18–24 forecast](projects/01_ga4_traffic_forecasting/reports/v3_forecast_oct18_24_2026.csv) remains archived unchanged.

## Recruit CRM analytics

[Planned project](projects/02_recruit_crm_analytics/README.md). No CRM model has been implemented yet.

## Privacy

Public code, derived experiment results and documentation are provided without credentials or private raw GA4 exports. Service-account files, tokens, candidate data and confidential records must remain outside Git tracking. Private local inputs and executed analysis outputs stay in the ignored `local-v4/` directory.
