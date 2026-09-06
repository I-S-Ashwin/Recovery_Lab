"""Index and package the completed frozen evaluation without touching earlier phases."""
import hashlib
import json
from pathlib import Path
import zipfile
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8'))
verification=read(ROOT/'reports/verification.json');metrics=read(ROOT/'reports/final_metrics.json')
if verification['failed'] or verification['passed']<115:raise RuntimeError('Verification must pass')
for name in ['Phase_9_Report.md','Model_Card.md','Data_Dictionary.md','Final_Evaluation.png']:
    if not (ROOT/'reports'/name).is_file():raise RuntimeError('Missing deliverable: '+name)
op=metrics['operational'];segments=read(ROOT/'reports/operational_segments.json')
ev=next(x for x in segments if x['field']=='asset_fuel_type' and x['value']=='EV')
summary={'phase':9,'primary_final_cases':op['model']['n'],'model_mae_inr':op['model']['mae_inr'],
         'baseline_mae_inr':op['baseline']['mae_inr'],'mae_reduction_percent':op['mae_reduction_percent'],
         'calibrated_coverage':op['calibrated_interval']['coverage'],'mean_interval_width_inr':op['calibrated_interval']['mean_width_inr'],
         'ev_final_cases':ev['n'],'ev_calibrated_coverage':ev['calibrated_interval']['coverage'],
         'verification_checks_passed':verification['passed'],'model_changed':False,'calibration_changed':False,
         'final_outcomes_now_inspected':True,'ready_for_production_underwriting':False}
(ROOT/'reports/summary.json').write_text(json.dumps(summary,indent=2)+'\n')
files=sorted(p for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='package_index.json')
index={p.relative_to(ROOT).as_posix():{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in files}
(ROOT/'package_index.json').write_text(json.dumps(index,indent=2)+'\n')
target=ROOT.parent/'TVS_Credit_Phase_9.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
    for p in files+[ROOT/'package_index.json']:z.write(p,p.relative_to(ROOT.parent).as_posix())
with zipfile.ZipFile(target) as z:
    if z.testzip():raise RuntimeError('Archive integrity failed')
print(json.dumps({'archive':str(target),'files':len(files)+1,'bytes':target.stat().st_size,'integrity':'passed'}))
