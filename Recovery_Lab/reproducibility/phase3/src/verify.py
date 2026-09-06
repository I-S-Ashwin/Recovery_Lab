"""Verify saved quantile model, data lineage, selection and reserved-role separation."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import numpy as np
import pandas as pd
from valuation import FEATURES,prepare,ordered,Valuator


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def verify(p1,p2,out):
    results=[]
    def check(name,condition):
        if not condition:raise AssertionError(name)
        results.append({'check':name,'result':'passed'})
    def rejects(name,fn):
        try:fn()
        except ValueError:check(name,True)
        else:check(name,False)
    summary=json.loads((out/'reports/summary.json').read_text())
    plan=json.loads((out/'configs/search_plan.json').read_text())
    lock=json.loads((out/'experiment_lock.json').read_text())
    provenance=json.loads((out/'models/training_provenance.json').read_text())
    trials=json.loads((out/'reports/trials.json').read_text())
    check('Phase 1 canonical data unchanged',sha(p1/'data/canonical_records.jsonl')==lock['canonical_sha256'])
    check('Search plan unchanged since training began',sha(out/'configs/search_plan.json')==lock['search_plan_sha256'])
    for file,h in lock['source_code_sha256'].items():check('Training source hash '+file,sha(out/'src'/file)==h)
    check('Saved model hash',sha(out/'models/catboost_quantiles.cbm')==summary['model_sha256'])
    check('Exactly six predeclared trials',len(trials)==6 and [r['trial_id'] for r in trials]==[r['trial_id'] for r in plan['candidates']])
    chosen=min(trials,key=lambda r:r['mae_inr'])
    check('Winner minimizes declared operational median MAE',chosen['trial_id']==summary['winner'])
    check('No calibration/final-test result claimed',summary['calibration_performed'] is False and summary['final_test_scored'] is False)
    d=pd.read_json(p1/'data/canonical_records.jsonl',lines=True).set_index('agreement_id',drop=False)
    op=pd.read_json(p2/'data/operational_split_manifest.jsonl',lines=True)
    trained=set(provenance['trained_ids']);selected=set(provenance['selection_ids'])
    check('Fit IDs exactly frozen operational training',trained==set(op.loc[op.role.eq('train'),'agreement_id']) and len(trained)==9767)
    check('Selection IDs exactly frozen operational tuning',selected==set(op.loc[op.role.eq('tuning'),'agreement_id']) and len(selected)==576)
    reserved=set(op.loc[op.role.isin(['calibration','final_test']),'agreement_id'])
    check('No reserved IDs used for fitting or selection',not reserved.intersection(trained|selected))
    check('Fit and selection IDs disjoint',not trained.intersection(selected))
    check('Training labels before Jan 1',pd.to_datetime(d.loc[list(trained),'sold_date']).lt('2026-01-01').all())
    check('Selection labels before Mar 1',pd.to_datetime(d.loc[list(selected),'sold_date']).lt('2026-03-01').all())
    model=Valuator(out/'models/catboost_quantiles.cbm')
    check('Saved tree count equals selected trial',model.model.tree_count_==chosen['tree_count'])
    check('Saved seed fixed',model.model.get_all_params()['random_seed']==plan['random_seed'])
    check('Saved depth equals selected trial',model.model.get_all_params()['depth']==chosen['depth'])
    check('Exactly nine permitted model features',model.model.feature_names_==FEATURES)
    for protocol,h in lock['phase2_split_hashes'].items():
        check(protocol+' split unchanged',sha(p2/f'data/{protocol}_split_manifest.jsonl')==h)
        manifest=pd.read_json(p2/f'data/{protocol}_split_manifest.jsonl',lines=True)
        ids=manifest.loc[manifest.role.eq('tuning'),'agreement_id'].tolist()
        pred=pd.read_json(out/f'data/{protocol}_tuning_predictions.jsonl',lines=True).set_index('agreement_id')
        check(protocol+' only tuning predictions exported',set(pred.index)==set(ids) and pred.index.is_unique)
        subset=d.loc[pred.index]
        check(protocol+' actual sale matches source tuning label',np.allclose(pred.actual_sale,subset.sale_amount,atol=1e-8,rtol=0))
        q=model.predict(subset[FEATURES])
        stored=pred[['ordered_q10','ordered_q50','ordered_q90']].to_numpy()
        check(protocol+' native saved model reproduces every output',np.allclose(q,stored,rtol=0,atol=1e-6))
        raw=pred[['raw_q10','raw_q50','raw_q90']].to_numpy()
        check(protocol+' postprocessing matches raw outputs',np.allclose(ordered(raw),stored,rtol=0,atol=1e-8))
        check(protocol+' finite ordered nonnegative predictions',np.isfinite(q).all() and (q>=0).all() and (np.diff(q,axis=1)>=0).all())
        y=pred.actual_sale.tolist();point=pred.ordered_q50.tolist()
        errors=[p-a for p,a in zip(point,y)]
        ref=next(x for x in summary['comparison'] if x['protocol']==protocol)
        check(protocol+' independent MAE',math.isclose(sum(abs(e) for e in errors)/len(errors),ref['catboost']['mae_inr'],abs_tol=1e-7))
        check(protocol+' independent RMSE',math.isclose(math.sqrt(sum(e*e for e in errors)/len(errors)),ref['catboost']['rmse_inr'],abs_tol=1e-7))
        check(protocol+' independent median absolute error',math.isclose(statistics.median(abs(e) for e in errors),ref['catboost']['median_absolute_error_inr'],abs_tol=1e-7))
        baseline=pd.read_json(p2/f'data/{protocol}_tuning_predictions.jsonl',lines=True).set_index('agreement_id').loc[pred.index]
        check(protocol+' baseline predictions unchanged',np.allclose(baseline.baseline_prediction,pred.baseline_prediction,atol=1e-7,rtol=0))
        for j,a in enumerate([.1,.5,.9]):
            pin=sum(max(a*(value-p), (a-1)*(value-p)) for value,p in zip(y,q[:,j]))/len(y)
            check(protocol+f' independent quantile loss {a}',math.isclose(pin,ref['quantile_diagnostics']['pinball_loss_inr'][str(a)],abs_tol=1e-7))
        coverage=sum(lo<=value<=hi for lo,value,hi in zip(q[:,0],y,q[:,2]))/len(y)
        check(protocol+' independent uncalibrated range coverage',math.isclose(coverage,ref['quantile_diagnostics']['ordered_central_range_coverage'],abs_tol=1e-12))
    fixture=d.loc[[next(iter(selected))],FEATURES].copy()
    for col in ['sale_amount','sold_date','outstanding_balance_at_liquidation','realized_yard_days','asset_body_condition','agreement_id']:
        bad=fixture.copy();bad[col]=1
        rejects('Reject future/forbidden predictor '+col,lambda f=bad:model.predict(f))
    rejects('Reject missing required feature',lambda:model.predict(fixture.drop(columns='asset_model')))
    for col,value in [('asset_cost_at_disbursal',0),('months_since_agreement_at_seizure',-1),('asset_cost_at_disbursal',float('nan'))]:
        bad=fixture.copy();bad[col]=value
        rejects('Reject invalid numeric '+col+' '+str(value),lambda f=bad:model.predict(f))
    unseen=fixture.copy();unseen['asset_model']='__UNSEEN_VERIFICATION_ONLY__'
    check('Unknown category yields finite supported numeric output',np.isfinite(model.predict(unseen)).all())
    missing=fixture.copy();missing['asset_model']=None
    check('Missing category has deterministic token',prepare(missing).asset_model.iloc[0]=='__MISSING__')
    check('Crossing correction independent example',ordered([[30,10,20],[-5,2,1]]).tolist()==[[10.,20.,30.],[0.,1.,2.]])
    check('Calibration still not performed',json.loads((out/'models/feature_contract.json').read_text())['calibrated'] is False)
    check('Canonical source hash remains unchanged',sha(p1/'data/canonical_records.jsonl')==lock['canonical_sha256'])
    output={'status':'passed','check_count':len(results),'checks':results,'calibration_or_final_test_scored':False}
    (out/'reports/verification.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps({k:v for k,v in output.items() if k!='checks'},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase1',type=Path,required=True);p.add_argument('--phase2',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();verify(a.phase1,a.phase2,a.output)
