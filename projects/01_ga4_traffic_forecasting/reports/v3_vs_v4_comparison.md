# V3 versus V4 — execution status, October 20, 2026

V4 is implemented alongside the preserved V3 source, notebook, forecast CSV and historical reports. Live source-level GA4 data is unavailable in this environment. No business accuracy improvement, source behavior, or numeric V4 October prediction can be inferred from fixture tests.

## Data and authentication

Inspection found neither `GA4_PROPERTY_ID` nor `GOOGLE_APPLICATION_CREDENTIALS` in the execution environment, and no standard local Google ADC file. No private GA4 exports are in the repository. The original notebook uses the Google Analytics client with a service-account file; V3 uses the same client with ADC or a supplied service-account path. V4 reuses ADC, including its existing service-account environment variable; no new authentication system is introduced. Live requests were not attempted without a property configuration.

The extractor requests `date`, `sessionSource`, `sessionMedium`, `sessionDefaultChannelGroup` together with `sessions`, paginates in stable dimension order, and independently requests daily aggregate sessions for reconciliation. Thresholding, sampling and `(other)` data loss metadata fail closed. Reconciliation currently requires exact equality. Investigate real reporting differences before relaxing this gate; never silently rescale channels. Mock API tests do not establish live dimension compatibility or account access.

Source/medium/channel remain separate input fields. Exclusive classification prioritizes LinkedIn, then Direct, Organic Search, Paid Search, Referral and Other. Paid LinkedIn remains LinkedIn. Other includes unrecognized and missing sources. This is channel-level modeling derived from acquisition sources, not a separate model for every raw referral hostname. Genuine source rankings, weekday patterns, LinkedIn fluctuations, unusual-day contributions and structural changes await live data; the notebook supplies those analyses.

## Fair evaluation protocol

Both approaches receive the same reconciled history and nonoverlapping seven-day outer test windows. Inside each outer origin, earlier seven-day windows select the model. V3's median residual bias correction is also estimated solely inside that origin. V4 selects one model family (seasonal, Ridge, Random Forest or Histogram Gradient Boosting) and a low-volume grouping threshold (0% or 2%) by inner aggregate MAE. Channel membership and shares are recalculated using training history at every inner cutoff. Zero-volume, future-only categories cannot enter training. Each channel is forecast recursively using past or previously predicted values, then summed without rounding.

The default is eight inner and eight outer weeks, requiring 168 continuous days. Larger historical windows are welcome. All dates at or after October 18 are excluded before preprocessing for the October 17 simulation. Explicit missing aggregate days, duplicate joint dimension keys, invalid counts and reconciliation mismatches fail validation. Absent source cells become zero only after reconciliation with complete aggregate dates. The known incomplete opening period should be excluded explicitly with `--start 2022-05-16`; V4 never silently treats those days as zero.

V3 has a checked-in literal `\\n` syntax defect in `main()`. The V4 compatibility adapter corrects that exact typo **in memory**, loads only imports, the feature constant and four pure model helpers, and never runs V3's output-writing code. Its estimators, hyperparameters, recursive features, selection ranking and median bias calculation are retained. The adapter is tested against independently extracted V3 helper functions. Results are labeled **V3 adapted**, not an exact reproduction of the original fitted model or its historical reported metrics. V3's output routine also writes the current forecast before copying it to the previous forecast; the adapter avoids that path entirely.

MAE is in sessions, MAPE excludes actual-zero days and reports their count, bias is predicted minus actual, and weekly percentage error uses **actual** weekly sessions as denominator. This differs from the old report's 17.4% figure, which used predicted sessions. Report signed and absolute weekly errors rather than presenting the overall multiweek percentage as a weekly score. Weekday and acquisition-channel diagnostics are included; grouped Other is conditional on the fold's selected threshold.

No calibrated forecast intervals are claimed. A small fixture or a handful of overlapping fitted histories cannot justify business confidence intervals or statistical significance. Before adoption, require repeated live seven-day holdouts, stable improvement over both V3 and seasonal baselines, and a paired block analysis over enough forecast weeks. Freeze methodology before scoring the next prospective period; measure interval coverage on separate periods if intervals are introduced.

## October 18–24, 2026

The original V3 predictions remain **57, 145, 137, 149, 125, 109, 58**, total **780**. The new comparison CSV contains blank V4 values with `blocked_no_live_source_data`, not zeros or synthetic predictions. A run with genuine source history through October 17 will produce a **retrospective simulation**. Even with a strict date cutoff, historical GA4 data fetched later may have been revised; it is not proof that identical data was available on October 17. Record extraction time and retain a private frozen input snapshot for audit.

On October 20 the target week is unfinished. Do not manufacture October 20–24 actuals or score an incomplete week as complete. The original V3 forecast is a frozen historical artifact; an adapted V3 re-fit belongs in a separate column and must never replace it.

## Prospective comparison

Using the GA4 property's timezone, choose the last fully finalized reporting day and verify its availability before running. If GA4 latency means the first forecast dates have already passed, label the run as-of/retrospective; do not call it prospective. For a genuine prospective comparison, freeze both forecasts before the first target day starts, keep the same cutoff, and retain the new run directory, manifest, dependency versions and private extraction snapshot. Re-run only into a new directory. After all seven target days finalize, join actuals by date and use the same metrics for both models. Do not tune on that week before scoring it.

## Remaining live work

Configure the existing property and credential environment on an authorized machine, retrieve and reconcile historical data, execute the full nested backtest and notebook, inspect source diagnostics, produce October's retrospective numbers, and freeze the next genuinely prospective pair. No new credentials were requested and no private raw analytics were published.

## Executed synthetic verification

The seeded 196-day fixture ending October 17 was evaluated on four outer weeks (September 20–October 17), with two inner weeks at each origin. These are **artificial test results**, not GA4 metrics and not evidence of real improvement:

| Model | MAE (sessions) | MAPE | Mean bias (sessions) | Overall total error |
|---|---:|---:|---:|---:|
| Seasonal | 11.143 | 14.020% | +1.929 | +2.500% |
| V3 adapted | 8.725 | 11.603% | +1.905 | +2.470% |
| V4 | 6.938 | 9.030% | +1.342 | +1.739% |

All 28 fixture actuals are positive. The last column is the overall four-week error, not mean weekly error; individual weekly metrics are in the local run output. Synthetic forecasts are deliberately omitted from the business October comparison file.

The environment is Python 3.12 on Windows; exact installed packages are captured in `requirements-v4-lock.txt`. Use that lock to reproduce this run; the existing unpinned V3 requirements remain unchanged. The lock is an execution record, not a claim of dependency vulnerability certification.

## Validation and security review

- All 25 tests passed. The final suite initially passed 24 tests with one temporary-directory setup error imposed by the sandbox; that test passed when rerun with a workspace-local `--basetemp`. The earlier 23-test suite also passed in full.
- The 11-cell notebook executed successfully in the isolated environment with an explicit inline plotting backend. All three rendered chart outputs were generated; the requested black-background prediction chart was visually checked. Only the clean, unexecuted notebook is tracked.
- Python compilation and Git whitespace checks passed. Git comparisons verified that the original V3 source, notebook and historical report/forecast files are unchanged from base commit `463a370`.
- Tracked-file checks cover private keys, common token patterns, credential filenames, ignored credential/private-output paths, and saved outputs in the new notebook. Manual review checked ADC reuse, lack of credential logging, independent reconciliation, no raw analytics publication, and immutable output directories. No embedded credentials or private GA4 exports were found in the staged changes. This is a targeted review, not a comprehensive security audit.
- Live authentication, real API compatibility/reconciliation, real-source EDA, live backtest metrics, business October V4 predictions and meaningful improvement remain unverified for the reasons above.
