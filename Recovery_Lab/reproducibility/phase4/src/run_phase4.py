"""Separate diagnostic calibration check, then frozen pooled final correction."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import numpy as np
import pandas as pd
from frozen_valuation import FEATURES,Valuator
from calibrated import fit_correction,expand


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def lines(p,df):Path(p).write_text(''.join(json.dumps(r,allow_nan=False)+'\n' for r in df.to_dict('records')),encoding='utf-8')
def interval_metrics(actual,q):
    y=np.asarray(actual,float)
    covered=(y>=q[:,0])&(y<=q[:,2]);width=q[:,2]-q[:,0]
    return {'n':len(y),'covered':int(covered.sum()),'coverage':float(covered.mean()),
            'below':int((y<q[:,0]).sum()),'above':int((y>q[:,2]).sum()),
            'mean_width_inr':float(width.mean()),'median_width_inr':float(np.median(width)),
            'median_mae_inr':float(np.abs(y-q[:,1]).mean())}


def run(p1,p2,p3,out):
    for f in ['models','data','reports']:(out/f).mkdir(parents=True,exist_ok=True)
    plan=json.loads((out/'configs/calibration_plan.json').read_text())
    previous=json.loads((p3/'reports/summary.json').read_text())
    p2summary=json.loads((p2/'reports/summary.json').read_text())
    data=p1/'data/canonical_records.jsonl';split=p2/'data/operational_split_manifest.jsonl';modelpath=p3/'models/catboost_quantiles.cbm'
    assert sha(data)==p2summary['input_sha256']
    assert sha(split)==p2summary['split_manifest_hashes']['operational']
    assert sha(modelpath)==previous['model_sha256']
    assert sha(out/'src/frozen_valuation.py')==sha(p3/'src/valuation.py')
    lock={'canonical_sha256':sha(data),'split_sha256':sha(split),'model_sha256':sha(modelpath),
          'plan_sha256':sha(out/'configs/calibration_plan.json'),
          'code_sha256':{n:sha(out/'src'/n) for n in ['calibrated.py','run_phase4.py','frozen_valuation.py']},
          'locked_utc':datetime.now(timezone.utc).isoformat()}
    if (out/'calibration_lock.json').exists():
        old=json.loads((out/'calibration_lock.json').read_text())
        for k in lock:
            if k!='locked_utc' and lock[k]!=old[k]:raise ValueError('Frozen calibration experiment changed: '+k)
    else:save(out/'calibration_lock.json',lock)
    manifest=pd.read_json(split,lines=True)
    ids=manifest.loc[manifest.role.eq('calibration'),'agreement_id'].tolist()
    assert len(ids)==583
    all_data=pd.read_json(data,lines=True).set_index('agreement_id',drop=False)
    d=all_data.loc[ids].copy()
    assert pd.to_datetime(d.seizure_date).ge('2026-03-01').all()
    assert pd.to_datetime(d.sold_date).lt(plan['final_artifact_available_from']).all()
    fit_before=set(json.loads((p3/'models/training_provenance.json').read_text())['trained_ids'])
    select_before=set(json.loads((p3/'models/training_provenance.json').read_text())['selection_ids'])
    assert not set(ids)&(fit_before|select_before)
    # Freeze internal diagnostic membership using IDs only, before predicting/using labels.
    seed=plan['diagnostic_split']['seed']
    sorted_ids=sorted(ids,key=lambda x:hashlib.sha256((seed+':'+x).encode()).hexdigest())
    nfit=int(len(ids)*plan['diagnostic_split']['fit_fraction'])
    fit_ids=set(sorted_ids[:nfit]);check_ids=set(sorted_ids[nfit:])
    roles=['diagnostic_fit' if x in fit_ids else 'diagnostic_check' for x in ids]
    internal=pd.DataFrame({'agreement_id':ids,'diagnostic_role':roles})
    lines(out/'data/diagnostic_split.jsonl',internal)
    model=Valuator(modelpath);q=model.predict(d[FEATURES]);y=d.sale_amount.to_numpy()
    fitmask=np.array([x in fit_ids for x in ids]);checkmask=~fitmask
    diagnostic,_=fit_correction(y[fitmask],q[fitmask],plan['alpha'],plan['minimum_fit_records'])
    check_ranges=expand(q[checkmask],diagnostic['correction_inr'])
    diagnostic_result={'fit_n':nfit,'check_n':int(checkmask.sum()),'correction':diagnostic,
                       'raw_on_check':interval_metrics(y[checkmask],q[checkmask]),
                       'adjusted_on_check':interval_metrics(y[checkmask],check_ranges),
                       'scope':'Static held-back diagnostic within calibration population; not forward-time validation',
                       'not_validation_of_final_refit':True}
    save(out/'reports/diagnostic_check.json',diagnostic_result)
    # No parameters changed after diagnostic inspection; fit the predeclared correction on all calibration rows.
    final,scores=fit_correction(y,q,plan['alpha'],plan['minimum_fit_records'])
    adjusted=expand(q,final['correction_inr'])
    final.update({'version':'phase4-operational-80-v1','model_sha256':sha(modelpath),
                  'available_from':plan['final_artifact_available_from'],'fit_role':'operational.calibration',
                  'method':'nonnegative conformal quantile expansion','calibration_scope':'pooled observed sold assets',
                  'coverage_assumption':'Exchangeability not established; no guaranteed temporal or per-segment coverage',
                  'lower_upper_are_not_individually_calibrated_quantiles':True})
    save(out/'models/calibration.json',final)
    shutil.copyfile(modelpath,out/'models/catboost_quantiles.cbm')
    shutil.copyfile(p3/'models/feature_contract.json',out/'models/base_feature_contract.json')
    pred=pd.DataFrame({'agreement_id':ids,'diagnostic_role':roles,'actual_sale':y,
                       'base_lower':q[:,0],'median':q[:,1],'base_upper':q[:,2],
                       'nonconformity_score':scores,'calibrated_lower':adjusted[:,0],'calibrated_upper':adjusted[:,2]})
    lines(out/'data/calibration_predictions.jsonl',pred)
    checkdf=pred.loc[checkmask,['agreement_id','actual_sale','base_lower','median','base_upper']].copy()
    checkdf['diagnostic_lower']=check_ranges[:,0];checkdf['diagnostic_upper']=check_ranges[:,2]
    lines(out/'data/heldback_diagnostic_predictions.jsonl',checkdf)
    segments=[]
    for field in ['asset_fuel_type','asset_model','customer_region']:
        for key in sorted(d[field].unique()):
            m=d[field].eq(key).to_numpy()
            segments.append({'field':field,'segment':str(key),'weak_sample':int(m.sum())<100,
                             'raw':interval_metrics(y[m],q[m]),'adjusted_fit_diagnostic':interval_metrics(y[m],adjusted[m]),
                             'independent_validation':False})
    save(out/'reports/segment_diagnostics.json',segments)
    sold=pd.to_datetime(d.sold_date);seized=pd.to_datetime(d.seizure_date)
    available_counts=[int((sold<t).sum()) for t in seized]
    replay={'minimum_required':plan['minimum_fit_records'],'max_prior_calibration_labels':max(available_counts),
            'eligible_calibration_seizures':sum(v>=plan['minimum_fit_records'] for v in available_counts),
            'calibration_seizures':len(d),'reason':'Counts use strictly earlier sold dates; no outcome-order replay mislabelled as seizure-time testing'}
    save(out/'reports/forward_replay_feasibility.json',replay)
    provenance={'calibration_ids':ids,'diagnostic_fit_ids':sorted(fit_ids),'diagnostic_check_ids':sorted(check_ids),
                'max_label_date_proxy':str(sold.max().date()),'min_seizure_date':str(seized.min().date()),
                'max_seizure_date':str(seized.max().date()),'source_model_sha256':sha(modelpath),
                'operational_final_test_records_reserved':int(manifest.role.eq('final_test').sum())}
    save(out/'models/calibration_provenance.json',provenance)
    summary={'phase':4,'calibration_records':len(d),'final_correction':final,
             'raw_on_calibration':interval_metrics(y,q),'adjusted_on_fit_data':interval_metrics(y,adjusted),
             'adjusted_fit_coverage_is_not_validation':True,'heldback_diagnostic':diagnostic_result,
             'forward_replay':replay,'final_test_scored':False,'model_retrained':False}
    save(out/'reports/summary.json',summary)
    raw=summary['raw_on_calibration'];fit=summary['adjusted_on_fit_data'];before=diagnostic_result['raw_on_check'];after=diagnostic_result['adjusted_on_check']
    report=['# Phase 4: uncertainty calibration','','The frozen Phase 3 CatBoost model was calibrated using only the 583 operational calibration cases. Model weights, input features and final-test reservation are unchanged.','',
            '## Fitted interval adjustment','',f'- Target central coverage: {1-plan["alpha"]:.0%}.',
            f'- Calibration records: {len(d):,}; finite-sample order statistic: {final["rank_one_based"]} of {len(d)}.',
            f'- Expand each raw range by INR {final["correction_inr"]:,.2f} on each side, flooring the lower endpoint at zero.',
            '- The median prediction is unchanged. Adjusted endpoints are interval bounds, not individually calibrated P10/P90 values.',
            '- Earliest version availability: 1 May 2026 under the sale-date arrival assumption. The inference wrapper rejects requests dated before this version was available.','',
            '## Diagnostics — interpret each row separately','','| Evidence | Records | Raw coverage | Adjusted coverage | Raw mean width INR | Adjusted mean width INR |',
            '|---|---:|---:|---:|---:|---:|',
            f'| Held-back static check; correction fitted on {nfit} other cases | {after["n"]} | {before["coverage"]:.2%} | {after["coverage"]:.2%} | {before["mean_width_inr"]:,.0f} | {after["mean_width_inr"]:,.0f} |',
            f'| Final correction on its own fitting records; NOT independent validation | {fit["n"]} | {raw["coverage"]:.2%} | {fit["coverage"]:.2%} | {raw["mean_width_inr"]:,.0f} | {fit["mean_width_inr"]:,.0f} |','',
            'The internal diagnostic split was fixed by a seeded hash of agreement IDs before using labels: 70% fit and 30% check. It is not a random train/test split for model selection: the existing temporal model/cohort roles stay fixed. It is also not a prospective seizure-time test. No alpha, subgroup or correction rule was changed after seeing its result.',
            'The final saved correction then used all 583 calibration cases, including the diagnostic check cases. Therefore that check does not validate the final refit independently. Its role is a limited diagnostic of the predeclared procedure within this selected population. Final forward-period performance remains reserved for Phase 9.','',
            '## Method','','For each calibration sale y and the model\'s ordered lower/upper estimates, compute s=max(lower-y,y-upper,0). For n scores take the ceil((n+1)*0.8)-th smallest score without interpolation. Add that correction to the upper endpoint and subtract it from the lower endpoint, with a zero floor. This implementation expands only; it does not shrink initially over-wide intervals.',
            'Conformal coverage theory requires assumptions such as exchangeability. These data are time-dependent, sold-only and incomplete for unsold seizures, so nominal coverage is not a guaranteed future or per-segment probability. A central 80% interval also does not establish 90% one-sided protection for its lower bound.','',
            '## Temporal validation limitation','',
            f'Within the reserved calibration cohort, the largest number of labels observed before any calibration seizure is {replay["max_prior_calibration_labels"]}. With the predeclared minimum {plan["minimum_fit_records"]}, {replay["eligible_calibration_seizures"]} seizures support a genuine sequential calibration replay.',
            'We therefore do not claim an operational online-validation result here. Sorting outcomes by sale date and using them to score earlier seizures would introduce hindsight. Phase 9 can evaluate the frozen May-available bundle on the reserved later seizure cohort, with its end-of-file follow-up limitation disclosed.','',
            '## Segment and population limits','','One pooled correction is used. Segment coverage and widths are fitting diagnostics with sample counts, not segment guarantees. Sparse EV results are flagged. There are no unsold seizures or full-book default outcomes. These intervals concern eventual liquidation proceeds in the observed sample, not verified retail values, default probability or 12/24/36-month projections.','',
            '## Handoff','','Use models/calibration.json with its exact bound model hash and src/calibrated.py. Replacing the point model invalidates the correction. Preserve this version for Phase 5 lending simulations and Phase 9 final evaluation. If making lower-tail risk probability claims later, add separately designed and validated one-sided calibration rather than reinterpreting this central interval.',
            'Adaptive updating remains a future extension; no online algorithm or market-shift guarantee has been implemented.','',
            '## References','','Conformalized Quantile Regression, Romano, Patterson and Candes (2019): https://arxiv.org/abs/1905.03222 . The implemented nonnegative score is an expansion-only variant.',
            'Gibbs and Candes (2024), adaptive conformal inference under distribution shifts: https://www.jmlr.org/papers/v25/22-1218.html . This is context for a future extension, not a capability claimed for this fixed correction.']
    (out/'reports/Phase_4_Report.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for arg in ['phase1','phase2','phase3','output']:p.add_argument('--'+arg,type=Path,required=True)
    a=p.parse_args();run(a.phase1,a.phase2,a.phase3,a.output)
