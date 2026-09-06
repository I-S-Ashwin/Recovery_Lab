"""Independent numerical reconciliation and frozen-protocol checks."""
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import statistics
import numpy as np
import pandas as pd
from calibrated import CalibratedValuator
from frozen_baseline import MedianRatioBaseline
from frozen_valuation import FEATURES
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT.parent
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def lines(p):return [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines()]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    checks=[]
    def check(name,truth):
        if not truth:raise AssertionError(name)
        checks.append(name)
    def near(name,a,b):check(name,math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-6))
    result=read(ROOT/'reports/final_metrics.json');lock=read(ROOT/'configs/evaluation_lock.json')
    check('protocol locked before evaluation',datetime.fromisoformat(lock['locked_at_utc'])<datetime.fromisoformat(result['evaluation_started_utc']))
    check('evaluation lock checksum',sha(ROOT/'configs/evaluation_lock.json')==result['evaluation_lock_sha256'])
    for path,digest in lock['artifact_sha256'].items():check('frozen artifact '+path,sha(OUT/path)==digest)
    for local,source in [('models/catboost_quantiles.cbm','phase4/models/catboost_quantiles.cbm'),('models/calibration.json','phase4/models/calibration.json'),('models/B0_median_ratio.json','phase2/models/B0_median_ratio.json'),('src/calibrated.py','phase8/api/calibrated.py'),('src/frozen_valuation.py','phase8/api/frozen_valuation.py'),('src/frozen_baseline.py','phase8/api/frozen_baseline.py')]:
        check('unchanged local inference '+local,sha(ROOT/local)==sha(OUT/source))
    canonical={r['agreement_id']:r for r in lines(OUT/'phase1/data/canonical_records.jsonl')}
    correction=read(ROOT/'models/calibration.json')['correction_inr'];predictions={}
    dev={r['agreement_id'] for r in lines(OUT/'phase2/data/operational_split_manifest.jsonl') if r['role'] in ['train','tuning','calibration']}
    model=CalibratedValuator(ROOT/'models');base=MedianRatioBaseline.load(ROOT/'models/B0_median_ratio.json')
    for protocol in ['operational','retrospective']:
        rows=lines(ROOT/f'data/{protocol}_final_predictions.jsonl');predictions[protocol]={r['agreement_id']:r for r in rows};summary=result[protocol]
        manifest=lines(OUT/f'phase2/data/{protocol}_split_manifest.jsonl')
        expected={r['agreement_id'] for r in manifest if r['role']=='final_test'}
        check(protocol+' exact frozen IDs',set(predictions[protocol])==expected)
        check(protocol+' no duplicate ID',len(rows)==len(expected)==lock['expected_counts'][protocol])
        check(protocol+' no development overlap',not expected&dev)
        check(protocol+' positive source labels',all(r['actual_sale_inr']==canonical[r['agreement_id']]['sale_amount']>0 for r in rows))
        check(protocol+' ordered nonnegative bounds',all(0<=r['calibrated_lower_inr']<=r['base_lower_inr']<=r['median_inr']<=r['base_upper_inr']<=r['calibrated_upper_inr'] for r in rows))
        check(protocol+' exact frozen expansion',all(abs(r['calibrated_lower_inr']-max(0,r['base_lower_inr']-correction))<1e-8 and abs(r['calibrated_upper_inr']-r['base_upper_inr']-correction)<1e-8 for r in rows))
        if protocol=='operational':check('operational model available at each seizure',all(r['seizure_date']>='2026-05-01' for r in rows))
        for name,column in [('model','median_inr'),('baseline','baseline_inr')]:
            errors=[r[column]-r['actual_sale_inr'] for r in rows]
            near(protocol+name+' MAE',statistics.mean(map(abs,errors)),summary[name]['mae_inr'])
            near(protocol+name+' RMSE',math.sqrt(statistics.mean(e*e for e in errors)),summary[name]['rmse_inr'])
            near(protocol+name+' bias',statistics.mean(errors),summary[name]['mean_signed_error_inr'])
            near(protocol+name+' median AE',statistics.median(map(abs,errors)),summary[name]['median_absolute_error_inr'])
        for name,lo,hi in [('base_interval','base_lower_inr','base_upper_inr'),('calibrated_interval','calibrated_lower_inr','calibrated_upper_inr')]:
            covered=sum(r[lo]<=r['actual_sale_inr']<=r[hi] for r in rows)
            below=sum(r['actual_sale_inr']<r[lo] for r in rows);above=sum(r['actual_sale_inr']>r[hi] for r in rows)
            check(protocol+name+' outcome partition',covered+below+above==len(rows))
            check(protocol+name+' covered count',covered==summary[name]['covered'])
            near(protocol+name+' coverage',covered/len(rows),summary[name]['coverage'])
            near(protocol+name+' width',statistics.mean(r[hi]-r[lo] for r in rows),summary[name]['mean_width_inr'])
            scores=[r[hi]-r[lo]+10*max(r[lo]-r['actual_sale_inr'],0)+10*max(r['actual_sale_inr']-r[hi],0) for r in rows]
            near(protocol+name+' interval score',statistics.mean(scores),summary[name]['mean_interval_score_inr'])
        segments=read(ROOT/f'reports/{protocol}_segments.json')
        for field in lock['segments']:
            parts=[s for s in segments if s['field']==field]
            check(protocol+field+' counts reconcile',sum(s['n'] for s in parts)==len(rows))
            near(protocol+field+' weighted MAE reconciles',sum(s['n']*s['model']['mae_inr'] for s in parts)/len(rows),summary['model']['mae_inr'])
            check(protocol+field+' small-group flags',all(s['small_sample']==(s['n']<30) for s in parts))
        # Independent persisted-prediction check on deterministic sample, no outcome-based sampling.
        sample=rows[::max(1,len(rows)//12)]
        x=pd.DataFrame([{k:canonical[r['agreement_id']][k] for k in FEATURES} for r in sample])
        q=model.predict(x,'2026-05-01');b=base.predict(x)
        check(protocol+' frozen model rescore sample',all(abs(r['median_inr']-float(q[i,1]))<1e-8 and abs(r['calibrated_lower_inr']-float(q[i,0]))<1e-8 for i,r in enumerate(sample)))
        check(protocol+' frozen baseline rescore sample',all(abs(r['baseline_inr']-float(b.iloc[i]['prediction']))<1e-8 for i,r in enumerate(sample)))
    shared=set(predictions['operational'])&set(predictions['retrospective'])
    check('overlap disclosed',len(shared)==result['cohort_overlap']['intersection']==1244)
    check('cohorts not counted as independent',result['cohort_overlap']['independent_replications'] is False)
    check('identical predictions for shared IDs',all(predictions['operational'][i]['median_inr']==predictions['retrospective'][i]['median_inr'] for i in shared))
    rows=list(predictions['operational'].values())
    differences=np.array([abs(r['baseline_inr']-r['actual_sale_inr'])-abs(r['median_inr']-r['actual_sale_inr']) for r in rows])
    rng=np.random.default_rng(lock['paired_mae_bootstrap']['seed'])
    samples=np.array([differences[rng.integers(0,len(rows),size=len(rows))].mean() for _ in range(2000)])
    check('paired bootstrap seed and bounds reproducible',np.allclose(np.quantile(samples,[.025,.975]),result['paired_mae_bootstrap']['percentile_95_inr'],atol=1e-8))
    check('all 49 dictionary fields accounted for',len(read(ROOT/'configs/data_dictionary.json'))==49)
    check('only nine permitted model features',len(FEATURES)==9 and 'sale_amount' not in FEATURES and 'realized_yard_days' not in FEATURES)
    check('no retraining/recalibration/policy change',not any(result[k] for k in ['model_retrained','calibration_refitted','policy_changed']))
    save={'passed':len(checks),'failed':0,'checks':checks,'scope':'Numerical and provenance validation; does not turn statistical estimates into guarantees'}
    (ROOT/'reports/verification.json').write_text(json.dumps(save,indent=2)+'\n')
    print(json.dumps({'passed':len(checks),'failed':0}))

if __name__=='__main__':main()
