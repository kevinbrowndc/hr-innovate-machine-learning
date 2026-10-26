# Eight-week prospective traffic pilot

Status: implemented and tested with synthetic data; **not activated**. No private archive or SMTP credentials have been configured, no prospective results exist, and no email has been sent by this implementation. Existing V3 files and predictions remain unchanged. Never use reconstructed historical predictions as prospective evidence.

## Model and evaluation protocol

The selected benchmark is the V3 Random Forest (160 trees, minimum leaf size 5, max features 0.8, random seed 42). The pilot reuses its feature and recursive prediction helpers without invoking the historical script's main routine. Initialization fits the weights once. Weights, feature/code identity, numerical-library versions, bias, interval radius and MASE scale are frozen together in a single private manifest for eight Monday–Sunday weeks. Weekly observations update lag inputs; weights are never retrained or reselected. Code/version mismatch withholds processing; do not upgrade a running pilot.

GA4 uses the existing `GA4_CREDENTIALS_JSON` Actions secret and `GA4_PROPERTY_ID` repository variable (311711993). The GA4 property timezone must be `Asia/Nicosia`. Extraction rejects incomplete dates, duplicates, invalid counts, sampling, thresholding and other-row data loss. Missing observations are never filled with zero. Only complete local days ending at least 72 hours before issue time are used. This buffer reduces revision risk but cannot guarantee GA4 will never revise data.

Forecasts issue Sunday at 22:30 Cyprus time. Wednesday is therefore the latest eligible observation, and recursive forecasts bridge Thursday–Sunday before predicting Monday–Sunday. The seasonal-naive baseline repeats the last seven available observations through exactly the same gap. Both baseline and model predictions are saved before target Monday midnight, together with seven lower/upper interval bounds, model-manifest hash, history hash, generation time and GitHub persistence timestamp. Re-running reuses the existing record; it cannot replace it. Late or missing forecasts are never backfilled.

Before launch, eight historical weekly folds use this same observation gap. Four earlier folds estimate median forecast bias; four later folds estimate the 80th percentile absolute residual using the fixed bias. These calibrate a fixed symmetric radius, clipped at zero on the lower side. This is an approximate empirical 80% interval, not a coverage guarantee. Calibration is entirely before the prospective period.

Reports evaluate every fully matured pilot week, using only authentic saved predictions. Any missing/modified/late forecast, missing actual, model mismatch or failed privacy check withholds the entire report. The latest eligible week's chart has a black background, blue predictions, green actuals and white labels. Cumulative metrics compare model and persisted baseline:

- MAE: mean absolute daily error, in sessions.
- MAPE: mean absolute percentage error over strictly positive actuals; zero days are excluded and counted. All-zero actuals produce N/A.
- MASE: MAE divided by the mean absolute seven-day seasonal difference in pre-pilot training data. Zero/invalid denominators produce N/A.
- Bias: mean(predicted − actual), in sessions; positive means overforecasting.
- Latest-week interval coverage: proportion of actuals inside saved bounds.

With the readiness buffer, week 1 can first be reported on the Sunday before week 3. After eight pilot forecasts, two additional Sunday outlooks support delayed reporting through the final pilot week while still including a forward seven-day outlook. These two outlooks are explicitly excluded from pilot scores. Processing ends after that reporting tail. A missed pilot forecast makes the complete eight-week experiment unavailable; retain the evidence and start a new prospectively dated pilot if necessary.

## Private archive: no AWS service required

Create a separate **private GitHub repository**, initialized with a README on `main`, under your account or organization. Restrict its collaborators to authorized analytics users; public-code-repository access does not automatically grant archive access. Store no credentials in it. Set `FORECAST_ARCHIVE_REPO` to `owner/private-repository` and a fine-grained `FORECAST_ARCHIVE_TOKEN` Actions secret scoped only to that archive with Contents read/write and Metadata read. Choose an expiry beyond the ten-week pilot/reporting horizon. No public Actions artifacts or public Git commits contain forecasts, fitted models, charts, raw analytics or email bodies.

Every archive key is create-only through the GitHub Contents API: updates omit the required existing SHA, timestamps are not supplied by the caller, writes are read back, and reads reject files with multiple modification commits or mismatching blobs. The manifest and each forecast are content-hashed. Configure available repository rules to block force pushes/deletion and limit writes to the pipeline identity and trusted administrators. Do not add workflows or untrusted writers to the archive: its fitted-model pickle is executable trusted content.

**Trust boundary:** this is application-enforced append-only storage with tamper detection, not administrator-proof WORM storage. A GitHub owner/admin or archive write-token holder could rewrite history and Git timestamps. Its evidence is valid within the trusted GitHub administration boundary. If independently tamper-proof retention is required later, use an external signed timestamp/WORM service. GitHub storage and Actions use existing plan quotas; no new paid infrastructure is required by this design. Do not make the archive public.

References: [GitHub create/update file API](https://docs.github.com/en/rest/repos/contents?apiVersion=2022-11-28#create-or-update-file-contents), [scheduled workflow behavior](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

## Configuration and activation checklist

1. Review and merge the code into `main`. Scheduled workflows only run on the default branch; secret-bearing pilot and connection-test jobs also require `main`. Create the `ga4-pilot` Actions environment and restrict deployments to `main`. Leave `PILOT_ENABLED` and `EMAIL_DELIVERY_ENABLED` absent or `false` during setup. No current repository settings are changed by this commit.
2. Configure the private archive and token above. Existing GA4 secret/variable are reused. Set `PILOT_ID` to a unique lowercase identifier such as `prospective-01`; do not reuse an earlier pilot directory. Choose a future Monday as `PILOT_START_DATE` (`YYYY-MM-DD`). No retrospective cutoff can initialize a valid pilot.
3. Run the GA4 Connection Test from `main`. It reports only pass/fail, timezone and coverage readiness, never sessions or credential contents. A failure must be resolved before launch; do not weaken missing-data gates.
4. On the Sunday before the chosen start, enable `PILOT_ENABLED=true` and manually dispatch **GA4 prospective weekly pilot → initialize** during 22:30–22:59 Cyprus time. Initialization can take several minutes. It freezes the model and creates the first forecast before midnight. Confirm private `PILOT_ID/pilot.json` and `PILOT_ID/forecasts/START.json` exist. The first run intentionally exits WITHHELD because no prospective week has matured; this does not undo a saved forecast. Do not initialize twice. If saving failed before midnight, retry within the window; after midnight never reconstruct the missed forecast.
5. Subsequent Sundays run automatically. Two UTC schedules (19:30 and 20:30) cover summer/winter; the `Asia/Nicosia` gate accepts only local 22:30–22:59, including DST transitions. GitHub schedules can be delayed or dropped. A delayed run outside the gate skips; manually run `weekly` inside the window if needed. Observe Actions status every Sunday. There is deliberately no catch-up after target midnight.
6. Configure SMTP separately as below. Forecast generation works with email disabled. Missing report data or disabled email exits with a safe WITHHELD message after any valid forward forecast has been persisted. Do not interpret a withheld report as a delivered email or a lost forecast; inspect private records.
7. At the end retain the archive and disable `PILOT_ENABLED`. Evaluate the eight-week evidence before deciding whether to retrain or replace the model.

## SMTP setup and test-only delivery

Add Actions secrets `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, and `SMTP_FROM`. Port must be 465 (implicit TLS) or 587 (STARTTLS); certificates are verified and authentication is required. Use a provider-supported application password/token, not a password pasted into chat or committed to Git. `SMTP_FROM` must be a single authorized sender address.

With `EMAIL_DELIVERY_ENABLED=false`, manually run `verify-email`. This tests TLS/login **without sending** and records the non-password configuration hash privately. A changed host/account/from configuration requires a new verification record/pilot; existing records cannot be overwritten. Verification does not prove mailbox delivery. Password rotation is authenticated on the next connection. Only after successful verification should an authorized operator set `EMAIL_DELIVERY_ENABLED=true`; no activation has been performed here.

Actual test sends also require complete genuine saved-forecast evaluation plus a persisted forward forecast. Recipient and envelope are hard-coded to **kevinbrown.dc@gmail.com**, with no CC/BCC or recipient environment override. **katerina@hrinnovate.org is not permitted**; adding organizational delivery requires new explicit approval and a reviewed code change. Preview tests use synthetic data and mocked SMTP only.

A private create-only delivery claim is written before sending. SMTP acceptance creates a separate receipt; acceptance is not proof of inbox delivery. Any failure after the claim (including ambiguous SMTP timeout) blocks automatic duplicate retries. Check the sender/provider and Kevin's mailbox privately before deciding on recovery; never delete evidence or automatically resend. Missing SMTP secrets, verification, archive access or report inputs withhold delivery.

## Tests and privacy

Install `requirements-pilot.txt` in Python 3.12, plus pytest, then run:

```text
python -m pytest projects/01_ga4_traffic_forecasting/tests/test_weekly_pilot.py -q
```

Tests use synthetic series, in-memory storage and mocked email only; no credentials or network are required. They cover DST, data gaps, frozen-model reuse, observation-gap alignment, delayed/modified/missing forecasts, baseline metrics, zero actuals, private archive enforcement, create-only writes, delivery gating and Kevin-only delivery. Test CI has no secrets. Local previews belong only in ignored `local-pilot/`; private historical work remains in ignored `local-v4/`. Never enable debug HTTP/SMTP logging, upload private run artifacts, or stage raw data/model/credential files.
