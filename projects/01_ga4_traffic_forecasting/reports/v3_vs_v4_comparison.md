# V3 versus V4 — verified live GA4 analysis

Live extraction, reconciliation review, eight-week nested backtesting and the October 18–24 retrospective forecast completed. This supersedes the earlier credential-blocked fixture-only report. **V4 MAE is 2.59% higher than adapted V3 on these matched historical holdouts**, and V4 wins 4 of eight weeks by MAE. This is a short retrospective comparison, not proof of statistical significance or prospective performance. Keep V3 alongside V4 until a genuinely prospective comparison is completed.

The 15% MAPE target was not met on these holdouts.

## Data access and reconciliation

The existing local service-account file was loaded without exposing its contents. `GA4_PROPERTY_ID` and `GOOGLE_APPLICATION_CREDENTIALS` were set only in the extraction process. No credential contents, credential identity, local credential path or raw private analytics are published. The ignored private extract was saved at 2026-10-20T20:52:23.941751+00:00.

History covers **May 16, 2022–October 17, 2026: 1,616 continuous days**, with 16,777 joint source/medium/channel rows. Separate reports retrieved daily sessions by `date,sessionSource,sessionMedium,sessionDefaultChannelGroup` and independent `date` totals. Both passed the sampling, thresholding and high-cardinality data-loss metadata checks. There were no missing dates.

Source sums differed from independent daily totals on **66 days**, with a maximum absolute difference of **2 sessions/day** and net difference of **54 sessions (0.02655%)**. Maximum relative daily difference was 2.2727%; the recent 112 days had four one-session differences. This is consistent with, but does not prove, the documented approximate session counting in Google's [Data API reporting expectations](https://developers.google.com/analytics/devguides/reporting/data/v1/reporting-data-expectations).

Exact matching remains the software default. This reviewed run explicitly uses `--reconciliation-tolerance 2`: fail if any daily discrepancy exceeds two sessions, still reject missing positive-traffic source dates, duplicates and invalid counts. **No source values were rescaled or silently replaced.** Source training and channel diagnostics retain reported source counts; V4's inner model selection and both models' outer total evaluation use the independent aggregate series. The complete reconciliation ledger remains private under `local-v4/`.

## Historical comparison

Eight nonoverlapping seven-day outer holdouts cover **August 23–October 17, 2026** (56 actual days). At each origin, eight earlier seven-day inner windows select models; all training, grouping and V3 bias correction stop before the outer target week. The long training history is the same for both approaches. No actual-zero aggregate days occurred in these holdouts.

| Model | MAE (sessions) | MAPE | Bias (sessions/day) | 56-day total error |
|---|---|---|---|---|
| Seasonal | 39.893 | 34.044% | +1.750 | +1.522% |
| V3 adapted | 29.745 | 24.395% | -4.566 | -3.970% |
| V4 | 30.516 | 27.787% | +5.010 | +4.357% |

Bias is predicted minus actual. MAPE excludes actual-zero days; MAE includes them. Total percentage error uses actual totals as denominator. The final column above is the **overall 56-day** error, not mean weekly error. Signed weekly percentage errors are shown below and retained in the private run output. These matched scores must not be compared as if equivalent to V3's older reported 26.6% MAPE or the original live-week 23% result.

| Training cutoff | V3 adapted MAE | V4 MAE | Seasonal MAE | V3 weekly error | V4 weekly error |
|---|---|---|---|---|---|
| 2026-08-22 | 31.350 | 29.394 | 52.571 | -17.245% | -10.469% |
| 2026-08-29 | 31.558 | 30.060 | 38.714 | +18.664% | +13.391% |
| 2026-09-05 | 17.176 | 31.644 | 26.571 | +16.553% | +31.644% |
| 2026-09-12 | 49.504 | 48.932 | 47.143 | -13.826% | +0.272% |
| 2026-09-19 | 21.431 | 25.309 | 39.143 | +16.579% | +22.544% |
| 2026-09-26 | 29.429 | 32.637 | 35.571 | -0.999% | +12.030% |
| 2026-10-03 | 47.781 | 34.637 | 41.429 | -33.280% | -21.684% |
| 2026-10-10 | 9.730 | 11.514 | 38.000 | -1.855% | +3.331% |

### Error by weekday

| Weekday | V3 adapted MAE | V4 MAE |
|---|---|---|
| Monday | 50.422 | 48.185 |
| Tuesday | 49.789 | 42.964 |
| Wednesday | 27.352 | 29.980 |
| Thursday | 29.420 | 31.166 |
| Friday | 29.460 | 30.545 |
| Saturday | 8.527 | 17.756 |
| Sunday | 13.243 | 13.016 |

### V4 acquisition-bucket errors

| Acquisition bucket | MAE | MAPE | Bias sessions/day | Actual-zero days |
|---|---|---|---|---|
| Direct | 13.057 | 38.519% | +4.115 | 0 |
| LinkedIn | 17.213 | 107.995% | +1.932 | 0 |
| Organic Search | 4.792 | 31.590% | -0.767 | 0 |
| Other | 1.822 | 71.320% | -0.146 | 3 |
| Paid Search | 4.746 | 30.035% | -0.607 | 0 |
| Referral | 2.689 | 90.785% | +0.448 | 2 |

MAPE for sparse buckets is unstable and excludes zero days, so compare it with MAE and zero frequency. Bucket definitions are exclusive custom groupings, not identical to GA4 default channel groups: LinkedIn has priority including paid LinkedIn; remaining Direct, Organic Search, Paid Search and Referral are classified by the documented rules; unrecognized traffic goes to Other. Non-LinkedIn referral-medium traffic can fall into Referral even if GA4 gives it another default channel group.

## Acquisition observations

Full-history shares of source-report sessions were Direct 37.94%, Organic Search 26.38%, LinkedIn 16.33%, Paid Search 13.36%, Referral 5.20%, and Other 0.80%. In the final 56 days those shares were 34.82%, 15.45%, 23.77%, 19.12%, 4.11%, and 2.73%, respectively. These descriptive changes do not establish causes or structural breaks. LinkedIn has a stronger weekday/weekend pattern than Direct in this history; the private notebook shows the trends and unusual-day contributions. No causal channel attribution for forecast errors is asserted.

## October 18–24 retrospective simulation

**Every training row, selection window and feature is dated October 17 or earlier.** The target week's observations were not extracted or used for tuning. Later-fetched historical GA4 values may contain revisions, so this is not an original as-of snapshot. The original V3 forecast file and all its values remain unchanged; the adapted V3 re-fit is a separate column.

| Date | Original V3 | V4 simulation | V3 adapted re-fit |
|---|---|---|---|
| 2026-10-18 | 57 | 70.81 | 57.46 |
| 2026-10-19 | 145 | 168.05 | 144.55 |
| 2026-10-20 | 137 | 152.14 | 137.00 |
| 2026-10-21 | 149 | 146.99 | 148.92 |
| 2026-10-22 | 125 | 122.51 | 125.43 |
| 2026-10-23 | 109 | 110.54 | 109.47 |
| 2026-10-24 | 58 | 69.69 | 58.14 |
| Total | 780 | 840.73 | 780.98 |

Predictions remain fractional expected sessions; the table rounds to two decimals and the new CSV stores six decimals. Totals use unrounded forecasts. Final V4 selection: **Gradient Boosting**, small-channel share threshold **0%**, inner aggregate MAE **30.713**. Adapted V3 selected **Random Forest**, with median residual bias adjustment **-9.239 sessions**.

October 18–24 is incomplete on the October 20 execution date. No actual-week error or future actual traffic is invented. There are no claimed calibrated forecast intervals. Eight holdout weeks with overlapping training histories are insufficient to assert robust statistical or operational superiority; assess the magnitude, week-to-week consistency and future performance before adoption.

## Reproducibility and implementation notes

V3's checked-in `main()` contains literal newline escape syntax errors. Its file is preserved. V4's adapter repairs that narrow typo in memory and loads only the original pure model helpers, avoiding the historical output-overwriting routine. Original estimator settings, recursive lags, calendar and trend features, ranking by inner MAE and median residual bias correction are retained. Results are labeled **V3 adapted**, not a claim to reproduce a previously fitted model exactly.

V4 tests seasonal, Ridge, Random Forest and Histogram Gradient Boosting with fixed 0%/2% small-channel policies. Group membership is recalculated using only each training prefix. A bounded in-memory cache keys predictions by the complete dated training history, model and bias; it does not reuse predictions across different inputs. Cache equivalence and mutation isolation are tested. This accelerates repeated origins without altering estimators or forecast rules.

Use the existing Python 3.12 environment lock. To reproduce with the private frozen inputs, from the repository root:

```text
python projects/01_ga4_traffic_forecasting/src/forecast_v4_ga4.py --sources-csv local-v4/live-oct17-inputs/sources.csv --aggregate-csv local-v4/live-oct17-inputs/aggregate.csv --cutoff 2026-10-17 --outer-weeks 8 --inner-weeks 8 --reconciliation-tolerance 2 --output local-v4/new-live-run
```

For a fresh authorized extraction, use the existing credential environment, omit CSV flags and supply `--start 2022-05-16`. A later query may return revised history. Output directories must be new. Run manifests retain timestamps, dependency versions, input hashes, tolerance and fold selections; raw inputs and all detailed outputs stay ignored.

The notebook defaults to fixtures. For the private live analysis, set `GA4_V4_SOURCES_CSV`, `GA4_V4_AGGREGATE_CSV`, `GA4_V4_RECONCILIATION_TOLERANCE=2` and optionally `GA4_V4_RUN` to the completed run directory. It validates cutoff, tolerance and input hashes before reusing results. Do not commit executed notebook outputs.

## Verification and remaining limits

All **30 tests passed**, including API parsing/pagination, missing values/dates, exclusive classification, aggregation, nonnegative forecasts, temporal poisoning, reproducibility, explicit discrepancy bounds, missing-date rejection despite tolerance, cache equivalence, independent aggregate selection, credential exclusions, and end-to-end export generation. The private live notebook executed all cells successfully and rendered three charts; the requested prediction chart was visually checked. Independent checks recomputed the reported metrics, matched all actuals to the aggregate extract, checked cutoff boundaries and channel sums, and verified that the adapted V3 re-fit rounds to all seven archived V3 predictions. Only the clean notebook is tracked. The V3 source, original notebook and historical forecast remain unchanged. Credentials and private extracts remain outside tracked files.

Freeze a new pair of forecasts before their first target day begins, using a finalized cutoff in the GA4 property's timezone. If processing latency makes that impossible, label the forecast as-of/retrospective. Evaluate both against finalized seven-day actuals before tuning again. Live API access and historical extraction are now verified; prospective performance, October actual-week errors and calibrated uncertainty remain unverified.
