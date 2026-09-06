"""Freeze temporal cohorts and evaluate B0 only on development tuning outcomes."""
import argparse
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from baseline import FEATURES, MedianRatioBaseline, select_features


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def lines(p,df):
    Path(p).write_text('\n'.join(json.dumps(r,allow_nan=False) for r in df.to_dict('records'))+('\n' if len(df) else ''),encoding='utf-8')


def assign_roles(d,plan,protocol,delay_days=None):
    delay=plan['label_reporting_delay_days'] if delay_days is None else delay_days
    label=d.sold_date+pd.Timedelta(days=delay)
    jan=pd.Timestamp(plan['training_label_cutoff_exclusive'])
    mar=pd.Timestamp(plan['tuning_end_exclusive'])
    may=pd.Timestamp(plan['calibration_end_exclusive'])
    end=pd.Timestamp(plan['dataset_end_inclusive'])+pd.Timedelta(days=1)
    roles=pd.Series('excluded',index=d.index)
    reason=pd.Series('outcome crosses development boundary or seizure predates its role',index=d.index)
    train=label<jan
    if protocol=='retrospective':
        tune=label.ge(jan)&label.lt(mar)
        calibration=label.ge(mar)&label.lt(may)
        test=label.ge(may)&label.lt(end)
    elif protocol=='operational':
        tune=d.seizure_date.ge(jan)&d.seizure_date.lt(mar)&label.lt(mar)
        calibration=d.seizure_date.ge(mar)&d.seizure_date.lt(may)&label.lt(may)
        test=d.seizure_date.ge(may)&d.seizure_date.lt(end)&label.lt(end)
    else:raise ValueError('Unknown protocol')
    masks={'train':train,'tuning':tune,'calibration':calibration,'final_test':test}
    if sum(m.astype(int) for m in masks.values()).gt(1).any():raise AssertionError('Overlapping roles')
    for name,mask in masks.items():roles.loc[mask]=name;reason.loc[mask]='included'
    return roles,reason,label


def metrics(actual,pred):
    y=np.asarray(actual,float);p=np.asarray(pred,float);e=p-y
    return {'n':len(y),'mae_inr':float(np.abs(e).mean()),'rmse_inr':float(np.sqrt(np.square(e).mean())),
            'mape_percent':float((np.abs(e)/y).mean()*100),'median_absolute_error_inr':float(np.median(np.abs(e))),
            'mean_signed_error_inr':float(e.mean()),'wape_percent':float(np.abs(e).sum()/y.sum()*100)}


def run(phase1,out):
    phase1=phase1.resolve();out=out.resolve()
    for x in ['data','models','reports']: (out/x).mkdir(parents=True,exist_ok=True)
    plan_path=out/'configs/split_plan.json';plan=json.loads(plan_path.read_text())
    source=phase1/'data/canonical_records.jsonl'
    m1=json.loads((phase1/'manifest.json').read_text())
    assert sha(source)==m1['files']['data/canonical_records.jsonl'],'Phase 1 input hash changed'
    d=pd.read_json(source,lines=True)
    assert d.agreement_id.is_unique and len(d)==15000
    for col in ['agreement_date','seizure_date','sold_date']:d[col]=pd.to_datetime(d[col])
    fpolicy=json.loads((phase1/'configs/feature_policy.json').read_text())
    assert FEATURES==fpolicy['seizure_core_candidate_features']
    assert d.sold_date.lt(pd.Timestamp(plan['dataset_end_inclusive'])+pd.Timedelta(days=1)).all()
    lock={'input_sha256':sha(source),'split_plan_sha256':sha(plan_path),'feature_policy_sha256':sha(phase1/'configs/feature_policy.json'),
          'frozen_before_baseline_fit_utc':datetime.now(timezone.utc).isoformat(),'feature_columns':FEATURES,
          'evaluated_role':'tuning','reserved_roles':['calibration','final_test'],'baseline_min_count':plan['baseline_min_group_count']}
    lock_path=out/'split_lock.json'
    if lock_path.exists():
        old=json.loads(lock_path.read_text())
        for key in ['input_sha256','split_plan_sha256','feature_policy_sha256']:
            if old[key]!=lock[key]:raise ValueError('Frozen plan/input changed; use a new version/output folder')
    else:save(lock_path,lock)
    all_metrics=[];segments=[];counts={};cohort_notes={};fallbacks={};split_hashes={}
    for protocol in ['operational','retrospective']:
        roles,reason,label=assign_roles(d,plan,protocol)
        manifest=pd.DataFrame({'agreement_id':d.agreement_id,'source_excel_row':d.source_excel_row,'role':roles,'reason':reason,
                               'seizure_date':d.seizure_date.dt.strftime('%Y-%m-%d'),
                               'label_available_date_proxy':label.dt.strftime('%Y-%m-%d')})
        split_path=out/f'data/{protocol}_split_manifest.jsonl';lines(split_path,manifest);split_hashes[protocol]=sha(split_path)
        counts[protocol]={role:int(roles.eq(role).sum()) for role in ['train','tuning','calibration','final_test','excluded']}
        train=d.loc[roles.eq('train')];tune=d.loc[roles.eq('tuning')]
        assert len(train) and len(tune)
        assert (label.loc[train.index]<pd.Timestamp(plan['training_label_cutoff_exclusive'])).all()
        if protocol=='operational':assert train.sold_date.max()<tune.seizure_date.min()
        # The two protocols share the same training data; fit a single state and reuse it.
        if protocol=='operational':
            model=MedianRatioBaseline(plan['baseline_min_group_count'],plan['duration_bin_lower_bounds_months'])
            model.fit(select_features(train),train.sale_amount)
            model.save(out/'models/B0_median_ratio.json')
        pred=model.predict(select_features(tune))
        global_pred=model.predict(select_features(tune),global_only=True)
        for name,values in [('B0_model_duration',pred.prediction),('B00_global_ratio',global_pred.prediction)]:
            all_metrics.append({'protocol':protocol,'role':'tuning','model':name,**metrics(tune.sale_amount,values)})
        result=pd.DataFrame({'agreement_id':tune.agreement_id,'source_excel_row':tune.source_excel_row,
                             'actual_sale':tune.sale_amount,'baseline_prediction':pred.prediction,
                             'global_ratio_prediction':global_pred.prediction,'fallback_level':pred.fallback_level,
                             'reference_count':pred.reference_count,'reference_ratio':pred.reference_ratio})
        lines(out/f'data/{protocol}_tuning_predictions.jsonl',result)
        fallbacks[protocol]={str(k):int(v) for k,v in pred.fallback_level.value_counts().items()}
        for field in ['asset_fuel_type','asset_model','customer_region']:
            for key,g in tune.groupby(field):
                segments.append({'protocol':protocol,'field':field,'segment':str(key),'weak_sample':len(g)<100,
                                 **metrics(g.sale_amount,pred.loc[g.index,'prediction'])})
        months=[]
        for month,g in tune.groupby(tune.seizure_date.dt.strftime('%Y-%m')):
            months.append({'seizure_month':month,'records':len(g)})
        cohort_notes[protocol]={'training_sale_min':str(train.sold_date.min().date()),'training_sale_max':str(train.sold_date.max().date()),
                                'tuning_seizure_min':str(tune.seizure_date.min().date()),'tuning_seizure_max':str(tune.seizure_date.max().date()),
                                'tuning_sale_min':str(tune.sold_date.min().date()),'tuning_sale_max':str(tune.sold_date.max().date()),
                                'tuning_seizure_month_counts':months}
    sensitivity=[]
    for days in [0,7,30]:
        roles,_,_=assign_roles(d,plan,'operational',delay_days=days)
        sensitivity.append({'assumed_label_delay_days':days,'counts':{x:int(roles.eq(x).sum()) for x in ['train','tuning','calibration','final_test','excluded']}})
    save(out/'reports/baseline_metrics.json',all_metrics)
    save(out/'reports/segment_metrics.json',segments)
    save(out/'reports/split_counts.json',counts)
    save(out/'reports/cohort_notes.json',cohort_notes)
    save(out/'reports/fallback_counts.json',fallbacks)
    save(out/'reports/label_delay_sensitivity.json',sensitivity)
    summary={'phase':2,'split_counts':counts,'metrics':all_metrics,'reserved_outcomes_scored':False,
             'input_sha256':sha(source),'split_manifest_hashes':split_hashes,'baseline_state_sha256':sha(out/'models/B0_median_ratio.json')}
    save(out/'reports/summary.json',summary)
    report=['# Phase 2: temporal cohorts and valuation baseline','','Phase 2 is implemented. The baseline was fitted on training outcomes only and scored on development tuning sets. Calibration and final-test prediction errors have not been computed.','',
            '## Frozen split membership','','| Protocol | Train | Tuning | Calibration reserved | Final test reserved | Excluded |','|---|---:|---:|---:|---:|---:|']
    for name,c in counts.items():report.append('| '+name+' | '+' | '.join(f'{c[k]:,}' for k in ['train','tuning','calibration','final_test','excluded'])+' |')
    report+=['','Training labels are available before 1 January 2026. Tuning ends before 1 March; calibration ends before 1 May; final testing is reserved for the remaining observed period through 31 July. The plan was saved and hashed before fitting the baseline.','',
             '## Two different questions','','- **Operational:** could a seizure-time prediction use only labels already available before that development period? Seizures must occur inside their allocated period, and outcomes must arrive before its end. This stricter rule leaves delayed outcomes and older seizures excluded from those roles.',
             '- **Retrospective:** does a model fitted on older sold records generalize to later sale cohorts? Some tuning vehicles were seized before training finished, so this is not a deployable-at-seizure claim.',
             '- These are alternative experiments on the same source, not independent datasets. Compare future models within the same protocol, never across protocols to claim improvement.','',
             '## Baseline','','B0 predicts original cost multiplied by the training median sale-to-original-cost ratio for model and elapsed-agreement-duration bin. Fixed lower bounds are 0, 6, 12, 18, 24, 36, 48 and 60 months; each interval includes its lower bound and excludes the next. The last interval is 60+ months. This is not confirmed vehicle age.',
             'Groups need at least 30 training records. Back off to model, then fuel, then the global training median. B00 always uses the global training ratio. No hyperparameters or bin boundaries were tuned against final-test results.','',
             '## Development results','','| Protocol | Model | Records | MAE INR | RMSE INR | MAPE | Median absolute error INR |','|---|---|---:|---:|---:|---:|---:|']
    for r in all_metrics:report.append(f'| {r["protocol"]} | {r["model"]} | {r["n"]:,} | {r["mae_inr"]:,.0f} | {r["rmse_inr"]:,.0f} | {r["mape_percent"]:.2f}% | {r["median_absolute_error_inr"]:,.0f} |')
    report+=['','MAE is the average absolute difference between estimated and actual sale amounts. MAPE averages percentage errors relative to each actual sale amount; it is not an accuracy percentage. These are development results, not final-test evidence.','',
             '## Sample limitations','','The operational tuning sample includes only vehicles sold before its boundary. It therefore favors sufficiently rapid recoveries; unsold seizures are absent from the source entirely. Do not generalize its errors to all seized assets. Operational final testing has a similar end-of-file follow-up limit. No population coverage denominator is available.',
             'Sale date is used as a proxy for label arrival, with strict date cutoffs. Actual arrival timestamps are missing. A 7- and 30-day reporting-lag sensitivity is supplied as cohort counts only; these are assumptions, not measured lags.',
             'Full-file descriptive profiling occurred in Phase 1. The reserved test is a model-development holdout, not an external dataset that nobody has seen. Do not examine its prediction errors until the planned final evaluation.',
             'Agreement IDs are unique, but true customer/vehicle IDs are missing, so cross-agreement entity independence cannot be certified. Per-field timestamp provenance remains an explicit assumption.','',
             '## Fallback use on tuning sets','','| Protocol | Level | Records |','|---|---|---:|']
    for p,levels in fallbacks.items():
        for k,v in levels.items():report.append(f'| {p} | {k} | {v:,} |')
    report+=['','## Phase 3 handoff','','- Train CatBoost only on the frozen training role and tune on the matching tuning role.',
             '- Use the Phase 1 whitelist; do not feed the entire audit table to a model.',
             '- Compare against the matching B0 predictions and preserve agreement membership.',
             '- Reserve calibration for interval calibration and final-test outcomes for the frozen final evaluation.',
             '- Refit on additional development labels only after model selection, with a separate version and release date before the subsequent prediction cohort. Never evaluate that refit on labels it has consumed.',
             '- Keep both protocol names, sample counts and selection limitations with every result.',
             '- No risk classifier, lending policy or future-value forecast was fitted in Phase 2.','',
             '## Verification','','verification.json records executed boundary, fallback, leakage and artifact checks. The canonical Phase 1 input is verified against its original hash. Split manifests contain IDs, role, dates and reasons; they contain no target sale values. Tuning prediction exports contain targets only for tuning agreements.']
    (out/'reports/Phase_2_Report.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase1',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.phase1,a.output)
