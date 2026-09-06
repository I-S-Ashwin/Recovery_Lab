"""Package the verified local deployment, including static assets but no runtime secrets."""
import hashlib
import json
import os
from pathlib import Path
import zipfile
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n',encoding='utf-8')
reg=read(ROOT/'reports/verification.json');ops=read(ROOT/'reports/operations_verification.json')
live=read(ROOT/'reports/deployment_checks.json');latency=read(ROOT/'reports/latency.json')
restart=read(ROOT/'reports/restart_check.json');audit=read(ROOT/'reports/npm_audit.json')
for result in [reg,ops,live]:
    if result['failed']:raise RuntimeError('Verification failed')
if not restart['restart_passed'] or not restart['audit_persisted']:raise RuntimeError('Restart not verified')
if audit['metadata']['vulnerabilities']['total']:raise RuntimeError('Frontend dependency audit has findings')
if not (ROOT/'dashboard/dist/client/index.html').exists():raise RuntimeError('Missing static dashboard')
save(ROOT/'reports/build_checks.json',{'typecheck_passed':True,'static_export_passed':True,'success_exit_preserved':True,
      'failure_exit_preserved':True,'native_dependencies_modified':False,
      'note':'The Windows build shutdown issue was resolved by allowing a successful CLI exit to drain pending handles. Failure exit code 7 and success exit code 0 were independently checked.'})
report=f'''# Phase 8 — local integration and deployment

The app is deployed at **http://127.0.0.1:8078/** as one Python service. It serves the prebuilt dashboard and all API routes; neither the Phase 7 development server nor a cloud account is needed. The original workbook and all frozen model/financial artifacts are unchanged.

## Delivered

- Native CatBoost SHAP explanations for the raw output slot that becomes the median after sorting. Contributions are checked for numerical reconciliation; three individual reasons are displayed. They are associations, not causal effects.
- Review-only fallback to the frozen Phase 2 baseline on primary prediction failure. No calibrated interval or lending from that fallback; simultaneous engine failures return no estimate.
- Startup integrity validation for the model, configuration, inference code and static dashboard assets.
- Persistent SQLite audit events, keyed fingerprints instead of raw request bodies, and a fail-closed response if audit storage is unavailable.
- Local-only host/client checks, bounded requests, a 120-requests-per-minute single-process API ceiling and a bounded model queue.
- A single-process static deployment with tested start/stop scripts, clean restart and preserved audit history.

## Verification

| Check group | Passed |
|---|---:|
| API / frozen-phase regression | {reg['passed']} |
| Explanations, fault injection and audit operations | {ops['passed']} |
| Deployed HTTP routes and static assets | {live['passed']} |

TypeScript checking and static export completed successfully. The build initially encountered an upstream Windows forced-exit shutdown crash after export; a small wrapper now lets successful exits drain handles naturally and preserves failure exit codes. The frontend dependency audit reports zero known vulnerabilities at this check. No dependency implementation was patched.

Fault injection covers primary failure, simultaneous primary/baseline failure, explanation failure, audit write failure, artifact tampering and rate-limit rejection. A real process stop/start also preserved the journal. No browser clicking, screenshot or accessibility checks were performed.

## Measured local latency

| Workload | Samples | Median | 95th percentile |
|---|---:|---:|---:|
| Sequential valuation requests | {latency['serial']['requests']} | {latency['serial']['p50_ms']:.1f} ms | {latency['serial']['p95_ms']:.1f} ms |
| Four concurrent clients | {latency['four_clients']['requests']} | {latency['four_clients']['p50_ms']:.1f} ms | {latency['four_clients']['p95_ms']:.1f} ms |

The first measured request took {latency['first_measured_request_ms']:.1f} ms. Measurements use a fixed fictional request over loopback HTTP and include model inference, SHAP and audit commit. There were no incorrect predictions or request timeouts in this sample. This is a local timing sample, not a production load certification.

## Interpretation and limits

The default fictional vehicle still returns about ₹34,511 median recovery. The Phase 6 fictional lending reference still recommends ₹80,000 under base assumptions and ₹70,000 under adverse assumptions; severe assumptions produce no feasible offer. The severe fixed fictional portfolio still has ₹1,21,880 conditional shortfall. These are integration checks, not new model-performance or causal-profit evidence.

Local binding is the access boundary; there is no multi-user login or external-network deployment. The journal is persisted locally, not backed up automatically. Fallback references are not calibrated. Future projections remain assumptions, and the sold-only dataset does not establish default probability or expected credit loss.

README.md contains restart, backup, test and rebuild instructions. The package includes the static dashboard, model, restricted calibration lookup, Python code and pinned dependencies. It excludes installed packages, runtime logs, the journal and its key. Keep this original-data package private.

The untouched final-test outcome evaluation remains Phase 9. This phase completes the requested local integration and deployment; it does not authorize production lending.
'''
(ROOT/'reports/Phase_8_Report.md').write_text(report,encoding='utf-8')
save(ROOT/'reports/summary.json',{'phase':8,'deployment':'single Python process on loopback','url':'http://127.0.0.1:8078/',
     'regression_checks':reg['passed'],'operations_checks':ops['passed'],'deployment_checks':live['passed'],
     'restart_verified':True,'audit_persisted':True,'serial_p95_ms':latency['serial']['p95_ms'],
     'concurrent_p95_ms':latency['four_clients']['p95_ms'],'final_test_used':False,'production_lending_approved':False})
excluded={'node_modules','runtime','__pycache__','.venv','.git','.wrangler','.vinext'}
files=[]
for folder,dirs,names in os.walk(ROOT):
    dirs[:]=[d for d in dirs if d not in excluded]
    for name in names:
        p=Path(folder)/name;relative=p.relative_to(ROOT)
        if relative.parts[:3]==('dashboard','dist','server'):continue
        if relative.parts[:3]==('dashboard','dist','.openai'):continue
        if name=='package_index.json' or name.endswith(('.pyc','.tsbuildinfo')):continue
        files.append(p)
files.sort()
save(ROOT/'package_index.json',{p.relative_to(ROOT).as_posix():{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in files})
target=ROOT.parent/'TVS_Credit_Phase_8.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
    for p in files+[ROOT/'package_index.json']:z.write(p,p.relative_to(ROOT.parent).as_posix())
with zipfile.ZipFile(target) as z:
    if z.testzip():raise RuntimeError('Archive integrity failed')
    if any('/runtime/' in name or '/node_modules/' in name for name in z.namelist()):raise RuntimeError('Private runtime accidentally included')
print(json.dumps({'archive':str(target),'files':len(files)+1,'bytes':target.stat().st_size,'integrity':'passed'}))
