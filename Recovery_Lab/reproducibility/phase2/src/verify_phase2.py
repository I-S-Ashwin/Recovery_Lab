"""Independent cohort, numerical and leakage checks; never scores reserved labels."""
import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path
import pandas as pd
from baseline import MedianRatioBaseline,duration_bin,select_features
from run_phase2 import assign_roles


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def readlines(p):return [json.loads(x) for x in Path(p).read_text().splitlines() if x]


def verify(phase1,out):
    results=[]
    def check(name,condition):
        if not condition:raise AssertionError(name)
        results.append({'check':name,'result':'passed'})
    def rejects(name,fn):
        try:fn()
        except ValueError:check(name,True)
        else:check(name,False)
    d=pd.read_json(phase1/'data/canonical_records.jsonl',lines=True)
    for c in ['sold_date','seizure_date']:d[c]=pd.to_datetime(d[c])
    summary=json.loads((out/'reports/summary.json').read_text())
    plan=json.loads((out/'configs/split_plan.json').read_text())
    lock=json.loads((out/'split_lock.json').read_text())
    check('Canonical input unchanged',sha(phase1/'data/canonical_records.jsonl')==lock['input_sha256'])
    check('Plan remains frozen',sha(out/'configs/split_plan.json')==lock['split_plan_sha256'])
    check('Feature policy unchanged',sha(phase1/'configs/feature_policy.json')==lock['feature_policy_sha256'])
    check('Baseline state unchanged',sha(out/'models/B0_median_ratio.json')==summary['baseline_state_sha256'])
    model=MedianRatioBaseline.load(out/'models/B0_median_ratio.json')
    target_metrics=json.loads((out/'reports/baseline_metrics.json').read_text())
    check('No metric references a reserved role',all(x['role']=='tuning' for x in target_metrics))
    for protocol in ['operational','retrospective']:
        path=out/f'data/{protocol}_split_manifest.jsonl'
        check(protocol+' manifest hash',sha(path)==summary['split_manifest_hashes'][protocol])
        manifest=pd.DataFrame(readlines(path));joined=d.merge(manifest[['agreement_id','role']],on='agreement_id',validate='one_to_one')
        check(protocol+' every input row assigned exactly once',len(manifest)==15000 and manifest.agreement_id.is_unique)
        check(protocol+' no target in split manifest','sale_amount' not in manifest and 'actual_sale' not in manifest)
        train=joined[joined.role=='train'];tune=joined[joined.role=='tuning'];cal=joined[joined.role=='calibration'];test=joined[joined.role=='final_test']
        check(protocol+' training labels predate release',train.sold_date.lt('2026-01-01').all())
        check(protocol+' tuning labels available before calibration',tune.sold_date.lt('2026-03-01').all())
        check(protocol+' calibration labels available before final release',cal.sold_date.lt('2026-05-01').all())
        if protocol=='operational':
            check('Operational tuning seizures follow training release',tune.seizure_date.ge('2026-01-01').all())
            check('Operational tuning seizures before March',tune.seizure_date.lt('2026-03-01').all())
            check('Operational calibration seizures in March-April',(cal.seizure_date.ge('2026-03-01')&cal.seizure_date.lt('2026-05-01')).all())
            check('Operational test seizures on/after May',test.seizure_date.ge('2026-05-01').all())
        else:
            check('Retrospective tuning labels in January-February',tune.sold_date.ge('2026-01-01').all())
            check('Retrospective calibration labels in March-April',cal.sold_date.ge('2026-03-01').all())
            check('Retrospective test labels on/after May',test.sold_date.ge('2026-05-01').all())
        pred=pd.DataFrame(readlines(out/f'data/{protocol}_tuning_predictions.jsonl'))
        check(protocol+' predictions are exactly tuning IDs',set(pred.agreement_id)==set(tune.agreement_id) and len(pred)==len(tune))
        check(protocol+' reserved IDs absent from prediction exports',not set(pred.agreement_id).intersection(set(cal.agreement_id)|set(test.agreement_id)))
        reference=pred.merge(tune[['agreement_id','sale_amount']],on='agreement_id',validate='one_to_one')
        check(protocol+' actual values are source tuning labels',(reference.actual_sale==reference.sale_amount).all())
        for model_name,prediction_col in [('B0_model_duration','baseline_prediction'),('B00_global_ratio','global_ratio_prediction')]:
            errors=[float(p-y) for p,y in zip(pred[prediction_col],pred.actual_sale)]
            expected=next(x for x in target_metrics if x['protocol']==protocol and x['model']==model_name)
            check(protocol+' '+model_name+' MAE reconciliation',math.isclose(sum(abs(x) for x in errors)/len(errors),expected['mae_inr'],abs_tol=1e-8))
            check(protocol+' '+model_name+' RMSE reconciliation',math.isclose(math.sqrt(sum(x*x for x in errors)/len(errors)),expected['rmse_inr'],abs_tol=1e-8))
        reloaded=model.predict(select_features(tune))
        byid=dict(zip(tune.agreement_id,reloaded.prediction))
        check(protocol+' saved baseline reproduces predictions',all(math.isclose(byid[r['agreement_id']],r['baseline_prediction'],abs_tol=1e-8) for r in pred.to_dict('records')))
        ratios=[float(y/c) for y,c in zip(train.sale_amount,train.asset_cost_at_disbursal)]
        check(protocol+' global median based on training only',math.isclose(statistics.median(ratios),model.state['global']['median_ratio'],abs_tol=1e-12))
        check(protocol+' baseline training count',model.state['n_training']==len(train)==9767)

    # Independent synthetic expectations exercise each fallback instead of mirroring its implementation.
    fixture=pd.DataFrame({'asset_model':['A','A','A','B','C','C'],'asset_fuel_type':['Petrol']*4+['EV']*2,
                          'asset_cost_at_disbursal':[100]*6,'months_since_agreement_at_seizure':[1,2,7,2,1,2]})
    b=MedianRatioBaseline(min_count=2).fit(fixture,[40,60,90,80,20,30])
    query=pd.DataFrame({'asset_model':['A','A','B','UNKNOWN'],'asset_fuel_type':['Petrol','Petrol','Petrol','UNKNOWN'],
                        'asset_cost_at_disbursal':[100]*4,'months_since_agreement_at_seizure':[1,8,2,2]})
    r=b.predict(query)
    check('Four independent fallback levels',r.fallback_level.tolist()==['model_duration','model','fuel','global'])
    check('Four independent fallback values',all(math.isclose(a,e,abs_tol=1e-10) for a,e in zip(r.prediction,[50,60,70,50])))
    check('Duration boundaries are left inclusive',[duration_bin(x,b.lower_bounds) for x in [0,5.99,6,12,59.9,60,90]]==[0,0,6,12,48,60,60])
    for c in ['sale_amount','sold_date','realized_yard_days','outstanding_balance_at_liquidation','asset_body_condition','agreement_id']:
        contaminated=query.copy();contaminated[c]=1
        rejects('Reject forbidden predictor '+c,lambda f=contaminated:b.predict(f))
    zero=query.copy();zero.loc[0,'asset_cost_at_disbursal']=0
    rejects('Reject zero asset cost',lambda:b.predict(zero))
    negative=query.copy();negative.loc[0,'months_since_agreement_at_seizure']=-1
    rejects('Reject negative duration',lambda:b.predict(negative))
    missing=query.drop(columns='asset_model')
    rejects('Reject missing required input',lambda:b.predict(missing))
    contaminated=d.copy();contaminated['sale_amount']=999999999;contaminated['sold_date']=pd.Timestamp('2099-01-01')
    check('Target/future-field changes cannot affect projected features',select_features(d).equals(select_features(contaminated)))

    boundaries=pd.DataFrame({'seizure_date':pd.to_datetime(['2025-12-01','2025-12-31','2026-01-01','2026-02-28','2026-03-01','2026-04-30','2026-05-01']),
                             'sold_date':pd.to_datetime(['2025-12-31','2026-01-01','2026-01-02','2026-03-01','2026-03-02','2026-05-01','2026-05-02'])})
    roles,_,_=assign_roles(boundaries,plan,'operational')
    check('Operational cutoff boundary examples',roles.tolist()==['train','excluded','tuning','excluded','calibration','excluded','final_test'])
    roles,_,_=assign_roles(boundaries,plan,'retrospective')
    check('Retrospective cutoff boundary examples',roles.tolist()==['train','tuning','tuning','calibration','calibration','final_test','final_test'])
    delayed,_,_=assign_roles(boundaries.iloc[:1],plan,'operational',delay_days=7)
    check('Delayed label is not prematurely available',delayed.iloc[0]=='excluded')
    check('Phase 1 file remains unchanged after checks',sha(phase1/'data/canonical_records.jsonl')==lock['input_sha256'])
    result={'status':'passed','check_count':len(results),'checks':results,'reserved_outcomes_scored':False}
    (out/'reports/verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='checks'},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase1',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();verify(a.phase1,a.output)
