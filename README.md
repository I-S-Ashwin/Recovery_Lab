# Recovery Lab: final submission

[![Watch the video](https://drive.google.com/file/d/1ZkvQ5a_gS8gDgb9BXAGatQJhpJcOr3xo/view?usp=sharing)](https://drive.google.com/file/d/1uSZVB-btL5N6Wlo5NhxhNPAgJU4nGEeB/view?usp=sharing)

## Deliverables

| File or folder | Purpose |
|---|---|
| Recovery_Lab_Presentation_Final.pptx | 12 slides using the supplied event cover and content template; editable charts, tables and architecture |
| Executive_Summary.pdf | Two-page summary of measured results, assumptions and pilot gates |
| Recovery_Lab_POC.ipynb | Executed notebook reproducing frozen inference, calibration and business calculations |
| Demo_Script.md | Timed narration, controls, fallback plan and judge questions |
| Architecture.md | Editable Mermaid source and component boundaries |
| Model_Card.md / Data_Dictionary.md / Open_Definitions.md | Model scope, all 49 canonical fields and unresolved definitions |
| local_app/ | Complete Python service, compiled dashboard, source and frozen models |
| reproducibility/ | Phases 1–6 and 9, preserving source audit, training code, splits and evaluation evidence |
| verification.json / package_index.json | Final verification summary and file hashes |

## Run locally on another Windows computer

Install Python 3.12. Extract the complete ZIP before running it. From this submission folder:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.\local_app\start.ps1 -PythonExecutable (Resolve-Path .venv\Scripts\python.exe).Path
```

Open http://127.0.0.1:8078/ . Stop with `local_app/stop.ps1`. A single service supplies both predictions and the dashboard. The compiled dashboard does not require Node.js to run.

If PowerShell execution policy prevents scripts, run from this folder:

```powershell
.venv\Scripts\python.exe -m uvicorn service:app --app-dir local_app/api --host 127.0.0.1 --port 8078 --no-access-log --no-proxy-headers
```

Keep that terminal open and use Ctrl+C to stop. Do not run two services on port 8078. The current original workspace service may already occupy it.

## Reproduce the notebook

Open `Recovery_Lab_POC.ipynb` in a notebook editor using the environment above. Set the working directory to this submission folder and choose Run All. A standalone runner is also provided:

```powershell
.venv\Scripts\python.exe run_notebook.py
```

It creates `Recovery_Lab_POC_rerun.ipynb`, leaving the submitted executed notebook unchanged. The notebook uses the original workbook’s audited canonical records, checks their hash and does not retrain. Training code and earlier decisions are retained under `reproducibility/phase3`. Running training again is a new development experiment, not a fresh independent validation against the already-inspected final outcomes.

## Evidence and limits

The primary final cohort has 1,244 cases. Model MAE is INR 7,052 versus INR 8,343 baseline, a 15.5% reduction. Calibrated coverage is 80.5%. EV coverage is 61.1% on 36 cases and requires further validation. The 1,835-case retrospective cohort overlaps the primary cohort.

The model estimates seizure-time sale value within the supplied sold-only population. Future paths, offer policy and the fictional book stress are explicit assumptions. The package does not establish default probability, expected loss, causal profit or production underwriting approval.

The Phase 10 app changes evidence metadata and presentation only. Weights, calibration and policy remain unchanged. Earlier reports are retained as historical development records and may describe the final test as reserved; Phase 9 and this final submission supersede that status.

Runtime databases, keys, logs, installed dependencies and caches are excluded. The canonical dataset and historical identifiers are included for reproducibility: share the archive only within the data owner’s authorized competition scope. The original workbook remains unchanged and is not duplicated in this archive.

Before uploading, add actual team/presenter details if required and verify organizer-specific submission rules. Browser interaction and speaking rehearsal remain manual checks. The portable release was exercised using existing local dependencies; a clean-machine dependency install was not tested.
