# Experiment 02: Does Acquisition-Source Modeling Improve Website Traffic Forecasting?

**Organization:** HR Innovate

**Evidence:** verified live analysis at commit `5243166`

**Outcome:** hypothesis not supported; V3 remains the forecasting benchmark.

This case study presents the completed experiment for portfolio readers. The [verified technical evaluation](v3_vs_v4_comparison.md) is preserved as the detailed record. No models were changed or retrained, and no new forecasts were generated for this publication.

## Business question and research hypothesis

Can forecasting sessions independently by acquisition source improve seven-day website traffic predictions compared with forecasting aggregate sessions directly?

Traffic sources can have different calendar patterns and changing relative importance. The experiment tested whether modeling that additional detail improves the total forecast. It did not assume that a more complex approach would be more accurate.

**Version 3 — Aggregate forecasting:** predicts total daily sessions using historical traffic, calendar patterns, lagged values, rolling averages and machine learning. Candidate estimators are standardized Ridge regression, Random Forest and Histogram Gradient Boosting. Model selection and median residual bias adjustment use earlier validation periods.

**Version 4 — Acquisition-source forecasting:** forecasts Direct, LinkedIn, Organic Search, Paid Search, Referral and Other separately, then sums those predictions into total daily sessions. It evaluates the same estimator families plus a seasonal alternative and training-only small-channel grouping policies. It selects one model family for the panel, rather than independently selecting a different estimator for every bucket.

The buckets are mutually exclusive custom acquisition categories derived from source, medium and channel group. They are not identical to GA4's default channel groups. LinkedIn takes precedence, including paid LinkedIn; the technical report documents the remaining rules.

## Real dataset and reconciliation

| Attribute | Verified dataset |
|---|---|
| Organization | HR Innovate |
| Platform | Google Analytics 4 Data API |
| Historical period | May 16, 2022–October 17, 2026 |
| Historical observations | 1,616 continuous days |
| Source/medium/channel rows | 16,777 |
| Evaluation period | August 23–October 17, 2026 |
| Historical test windows | Eight nonoverlapping seven-day periods |
| Evaluation observations | 56 days |

The source report jointly retrieves `date`, `sessionSource`, `sessionMedium`, `sessionDefaultChannelGroup` and `sessions`. A separate daily report supplies aggregate sessions. Both models are evaluated against these **independently retrieved aggregate totals**. The reports passed sampling, thresholding and high-cardinality data-loss checks, and the historical calendar has no missing dates.

Reconciliation found small source-sum versus aggregate differences on **66 days**: at most **two sessions per day**, with a net difference of **54 sessions**, approximately **0.027% overall**. The live run explicitly permitted a two-session daily discrepancy. Exact equality remains the default for other runs. There was **no rescaling or silent modification of source counts**. The technical report explains the reporting-approximation context and retains the distinction between source counts and aggregate evaluation targets.

Raw GA4 exports and authentication information are private. The public repository provides code, synthetic fixtures, derived results and documentation; access to the authorized historical extract is required to reproduce the business metrics exactly. Later GA4 extracts may contain revisions.

## Controlled experimental design

1. Use the same historical coverage, seven-day forecast horizon and outer test windows for both models.
2. At each outer cutoff, use eight earlier seven-day inner windows to select models. Estimate V3's bias correction and V4's grouping decisions using only the available training history.
3. Forecast recursively: each target day's features use past observations or previous predictions, never actual future traffic.
4. Score both total forecasts against the same independent aggregate actuals. Include a seasonal baseline that repeats the previous seven days.
5. Report overall, weekly, weekday and acquisition-bucket errors without selecting a favorable test window after seeing its outcome.

“V3 adapted” uses the original pure model helpers through an in-memory repair of a narrow syntax defect in the preserved script. It is an adapted reproduction of the implementation, **not an exact reproduction of a previously fitted historical model**. The original source, notebook and forecast files remain unchanged.

The original October 11–17 forecasting exercise is [documented separately](initial_forecast_oct11_17_2026.md). Its live-week results must not be treated as an equivalent comparison with this eight-week historical experiment.

## Verified results

| Model | MAE | MAPE | Daily bias |
|---|---:|---:|---:|
| V3 adapted | 29.745 | 24.395% | -4.566 |
| V4 | 30.516 | 27.787% | +5.010 |
| Seasonal baseline | 39.893 | 34.044% | +1.750 |

**MAE** is average absolute prediction error in sessions. **MAPE** is average absolute percentage prediction error; it excludes actual-zero days, of which there were none in the aggregate holdouts. **Bias** is average predicted minus actual sessions per day: negative means underprediction and positive means overprediction.

**V3 outperformed V4 overall on both MAE and MAPE.** V4's MAE was approximately **2.59% higher**, and it won **four of the eight** individual weeks by MAE. Both machine learning approaches outperformed the seasonal baseline on MAE and MAPE. Neither reached the 15% MAPE objective in this evaluation.

These are descriptive results from eight test weeks, not a claim of statistical significance. Overlapping training histories, a short evaluation period and the absence of a new prospective comparison limit generalization. No calibrated forecast intervals are claimed for V4.

## What the acquisition analysis showed

Shares below use source-report sessions as the denominator; small rounding differences may prevent column totals from equaling exactly 100%.

| Source | Full-history share | Last 56 days |
|---|---:|---:|
| Direct | 37.94% | 34.82% |
| Organic Search | 26.38% | 15.45% |
| LinkedIn | 16.33% | 23.77% |
| Paid Search | 13.36% | 19.12% |
| Referral | 5.20% | 4.11% |
| Other | 0.80% | 2.73% |

LinkedIn's recent share increased while Organic Search's relative share declined. These are changes in the traffic mix, not proof of a structural break or a causal explanation for any particular prediction error. A declining share does not by itself establish a decline in absolute traffic.

LinkedIn was difficult to forecast under this V4 design: its bucket MAE was **17.213 sessions** and MAPE **107.995%**, the largest of the six bucket errors on both measures. These errors and the observed weekday/weekend variation highlight volatility and prediction difficulty; they do not isolate its cause. Percentage errors can be large on low-volume days, so they must be read alongside absolute errors.

## Why V4 did not outperform V3 overall

The error diagnostics show where the tested approach fell short. V4's average total bias was **+5.010 sessions/day**, compared with V3's **-4.566**. Its Saturday MAE was **17.756**, versus **8.527** for V3, despite some weekday improvements. Bucket errors also show that predicting the acquisition components is not uniformly easy.

A plausible explanation is that independent channel forecasts introduce estimation noise that does not cancel when summed. Changing source shares may also make historical patterns harder to extrapolate. **These are hypotheses for further testing, not established causes.** This comparison does not isolate the effects of segmentation, model selection and V3's bias correction through separate ablation experiments.

The lesson is methodological: additional detail must earn its place through controlled evaluation. Source-level analysis is informative, but its descriptive value did not translate into lower total forecast error for this implementation.

## October 18–24, 2026 forecast

| Date | V3 original | V4 simulation |
|---|---:|---:|
| October 18 | 57 | 70.81 |
| October 19 | 145 | 168.05 |
| October 20 | 137 | 152.14 |
| October 21 | 149 | 146.99 |
| October 22 | 125 | 122.51 |
| October 23 | 109 | 110.54 |
| October 24 | 58 | 69.69 |
| Total | 780 | 840.73 |

These values are **predictions, not observed traffic**. The original V3 forecast is frozen. V4 is a **retrospective simulation with a strict October 17, 2026 cutoff**: October 18 or later data was excluded from training, preprocessing, model selection and feature construction. Historical data retrieved later may have been revised, so this is not proof of what was available in an original October 17 snapshot.

V4 values are rounded to two decimals here; the total uses unrounded predictions. The [comparison CSV](v4_forecast_oct18_24_2026.csv) also distinguishes the original V3 values from its adapted re-fit. The [original V3 CSV](v3_forecast_oct18_24_2026.csv) is preserved. No final-week accuracy is calculated here; that requires the reporting period to end and finalized actual sessions to be available.

## Conclusion: Hypothesis Not Supported

Acquisition-source modeling did not improve overall forecasting accuracy during the historical evaluation. This is a valid research finding about the particular V4 approach under the tested conditions, not evidence that acquisition-source information is useless.

**Retain V3 as the current forecasting benchmark. Preserve V4 as a reproducible experimental alternative.** The experiment provides a documented negative result, data-quality checks and a clearer basis for deciding what to test next.

## Future Work: Hybrid Forecasting

The proposed next experiment would preserve V3's direct prediction of total sessions and introduce selected historical acquisition-source features. It would investigate lagged LinkedIn and Organic Search trends and whether they improve aggregate prediction without requiring a separate forecast for every source.

Feature selection and all preprocessing would stay within the same leakage-controlled inner evaluation framework. The hybrid model would be compared against both V3 and the seasonal baseline on matched seven-day holdouts, followed by a frozen prospective comparison. Any source features needed beyond the cutoff would have to be constructed from cutoff-available history or predictions, never actual future counts.

**This is proposed future work, not an implemented or validated improvement. No V5 development is part of this publication.**

## Reproduce and inspect

Start with the [project guide](../README.md), [V4 notebook](../notebooks/HR_Innovate_GA4_V4.ipynb) and [V4 implementation](../src/forecast_v4_ga4.py). The notebook defaults to explicitly labeled synthetic fixtures. The [technical report](v3_vs_v4_comparison.md) documents the live procedure, environment, reconciliation, detailed errors and limitations; the [metrics CSV](v4_live_backtest_metrics.csv) contains the verified aggregate scores. The implementation's 30 passing tests and live notebook execution were recorded in the verified run. This documentation task does not rerun training or generate forecasts.
