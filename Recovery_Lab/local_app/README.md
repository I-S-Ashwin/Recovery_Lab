# Phase 8 — single-service local deployment

Open **http://127.0.0.1:8078/**. The API, model and built dashboard run in one Python process. Node.js and a cloud account are not needed to run the delivered build.

The app is restricted to this computer. It does not implement multi-user authentication and must not be exposed to a public network. The original workbook remains unchanged; historical lookup contains only the already-used calibration cohort.

## Start and stop

On this computer, run `start.ps1` from PowerShell. It finds the existing model dependencies or a local `.venv`, checks the port, starts a hidden process and waits for readiness. Run the script after installing dependencies in this folder. `stop.ps1` checks the recorded process ID, creation time and executable before stopping it. Both scripts leave audit data intact.

For another Windows computer, install Python 3.12, extract this package, and run:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.\start.ps1
```

If local policy prevents running PowerShell scripts, use a terminal command instead of changing the policy:

```powershell
.venv\Scripts\python.exe -m uvicorn service:app --app-dir api --host 127.0.0.1 --port 8078 --no-access-log --no-proxy-headers
```

Keep this terminal open; Ctrl+C stops the service. Use one worker for the demonstrated global request limit and inference queue. Interactive API documentation is available at http://127.0.0.1:8078/docs.

## Demo sequence

1. Run the default fictional vehicle. Its median model estimate is about ₹34,511. The three displayed reasons are native SHAP contributions for this prediction, not global feature importance or causal effects.
2. In lending, select **Phase 6 fictional example A**. With the default fictional income and obligations, base recommends ₹80,000, adverse ₹70,000 and severe no offer. These hand-authored anchors are visibly separate from the model.
3. Run severe portfolio stress at month zero. The fixed fictional book has ₹2,65,000 exposure and ₹1,21,880 conditional downside shortfall.
4. Open Model evidence and refresh the local audit trail. Requests have trace IDs, timestamps, statuses and processing times. The journal excludes raw request values.

## Explanations and failure behavior

SHAP contributions plus the SHAP reference value reconstruct the selected raw median output. The code chooses the correct raw output slot after sorting quantiles and checks the arithmetic. It does not describe these contributions as causal or as explanations of interval width.

If attribution alone fails, the estimate stays available and attribution is labeled unavailable. If the primary valuation fails, the frozen Phase 2 baseline provides an **uncalibrated review-only reference**. It has no interval, coverage claim or risk score, and the dashboard blocks lending from that fallback. If both engines fail, the API returns 503 with no value. A later successful primary prediction restores readiness. Invalid dates/inputs are rejected before fallback; artifact corruption prevents startup.

The unchanged lending endpoint still accepts explicit user-supplied scenario anchors for simulation. It is not an approval service and does not certify those inputs as model outputs.

## Audit storage

`runtime/audit.sqlite3` uses SQLite WAL and commits each event before a decision response is released. `runtime/audit.key` keys the request fingerprints; preserve it with the journal. Storage failures block decisions. For requests rejected before their body is fully read, the digest covers only the bytes read, possibly none. It is not a full request-replay log.

The audit table's processing duration excludes its own journal write. The HTTP benchmark includes model inference, SHAP and audit commit. No automatic retention deletion is enabled; monitor local disk space. Stop the service before copying the entire runtime folder for backup. Runtime files, keys and logs are excluded from the delivery archive.

## Verify or rebuild

The included static build is ready to run. To change the interface, install Node.js and run `npm ci`, `npx tsc --noEmit`, and `npm run build` inside `dashboard/`. The build script lets native Windows handles close normally after a successful export; it preserves failure exit codes. No dependency source is modified.

After an intentional model/config/code or dashboard-build update, run `python api/lock_bundle.py` as a release step, then restart. Never regenerate the manifest merely to accept an unexplained integrity failure.

With Python dependencies available:

```powershell
python api/verify_operations.py
python api/check_deployment.py
python api/benchmark.py
```

`verify_regression.py` additionally needs the earlier Phase 1, 2, 4, 5 and 6 folders as siblings. The tests use fictional requests and calibration features; they never evaluate the final-test outcomes.

## Remaining scope

This is a tested local POC deployment, not a production-approved lending system. Multi-user authentication, external hosting, distributed rate limiting, independent security review and production monitoring are outside this local deployment. Browser interaction/accessibility testing was not performed; validation covers compilation, HTTP/static assets, API contracts, numerical agreement and injected failures.

Phase 10 updates the evidence page with the frozen Phase 9 final evaluation: 1,244 operational cases, model MAE INR 7,052 and EV coverage 61.1% on 36 cases. Model weights, calibration and policy remain unchanged. Historical lookup continues to contain calibration cases only.
