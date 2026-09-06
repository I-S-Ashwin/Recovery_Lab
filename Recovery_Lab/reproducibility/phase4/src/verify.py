"""Calibration math, provenance and inference tests; no final-test scoring."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
from calibrated import CalibratedValuator,fit_correction,expand
from frozen_valuation import FEATURES,Valuator


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def verify(p1,p2,p3,out):
    checks=[]
    def require(name,condition):
        if not condition:raise AssertionError(name)
        checks.append({'check':name,'result':'passed'})
    def rejects(name,fn):
        try:fn()
        except ValueError:require(name,True)
        else:require(name,False)
    lock=json.loads((out/'calibration_lock.json').read_text())
    summary=json.loads((out/'reports/summary.json').read_text())
    plan=json.loads((out/'configs/calibration_plan.json').read_text())
    prov=json.loads((out/'models/calibration_provenance.json').read_text())
    cal=json.loads((out/'models/calibration.json').read_text())
    d=pd.read_json(p1/'data/canonical_records.jsonl',lines=True).set_index('agreement_id',drop=False)
    split=pd.read_json(p2/'data/operational_split_manifest.jsonl',lines=True)
    predicted=pd.read_json(out/'data/calibration_predictions.jsonl',lines=True).set_index('agreement_id')
    require('Canonical data hash unchanged',sha(p1/'data/canonical_records.jsonl')==lock['canonical_sha256'])
    require('Temporal split hash unchanged',sha(p2/'data/operational_split_manifest.jsonl')==lock['split_sha256'])
    require('Phase 3 model unchanged',sha(p3/'models/catboost_quantiles.cbm')==lock['model_sha256'])
    require('Bundled model is exact frozen copy',sha(out/'models/catboost_quantiles.cbm')==lock['model_sha256'])
    require('Correction bound to exact model',cal['model_sha256']==lock['model_sha256'])
    require('Plan unchanged after fitting',sha(out/'configs/calibration_plan.json')==lock['plan_sha256'])
    for file,h in lock['code_sha256'].items():require('Code hash '+file,sha(out/'src'/file)==h)
    require('Frozen inference identical to Phase 3',sha(out/'src/frozen_valuation.py')==sha(p3/'src/valuation.py'))
    ids=set(split.loc[split.role.eq('calibration'),'agreement_id'])
    require('Exactly 583 allocated calibration IDs',len(ids)==583 and ids==set(predicted.index)==set(prov['calibration_ids']))
    prior=json.loads((p3/'models/training_provenance.json').read_text())
    require('Calibration disjoint from training and selection',not ids.intersection(set(prior['trained_ids'])|set(prior['selection_ids'])))
    reserved=set(split.loc[split.role.eq('final_test'),'agreement_id'])
    require('No final-test ID in calibration predictions',not ids.intersection(reserved))
    require('All 1244 final-test cases remain reserved',len(reserved)==prov['operational_final_test_records_reserved']==1244)
    source=d.loc[predicted.index]
    require('Calibration labels match source',np.allclose(source.sale_amount,predicted.actual_sale,rtol=0,atol=1e-8))
    require('All labels precede version availability',pd.to_datetime(source.sold_date).lt(cal['available_from']).all())
    require('All calibration seizures follow model selection period',pd.to_datetime(source.seizure_date).ge('2026-03-01').all())
    model=Valuator(p3/'models/catboost_quantiles.cbm')
    q=model.predict(source[FEATURES])
    require('Saved base quantiles reproduce',np.allclose(q,predicted[['base_lower','median','base_upper']],rtol=0,atol=1e-6))
    y=predicted.actual_sale.to_numpy()
    independent_scores=[max(float(lo-a),float(a-hi),0.) for a,lo,hi in zip(y,q[:,0],q[:,2])]
    require('Every score independently reconciles',np.allclose(independent_scores,predicted.nonconformity_score,rtol=0,atol=1e-6))
    rank=(4*(len(y)+1)+4)//5
    independent_correction=sorted(independent_scores)[rank-1]
    require('Finite-sample integer rank is 468',rank==cal['rank_one_based']==468)
    require('No interpolated quantile used',math.isclose(independent_correction,cal['correction_inr'],abs_tol=1e-6))
    expected=np.array([[max(0,lo-independent_correction),median,hi+independent_correction] for lo,median,hi in q])
    adjusted=predicted[['calibrated_lower','median','calibrated_upper']].to_numpy()
    require('All interval endpoints independently reconcile',np.allclose(expected,adjusted,rtol=0,atol=1e-6))
    require('Median prediction unchanged',np.array_equal(adjusted[:,1],q[:,1]))
    require('Finite nonnegative ordered final intervals',np.isfinite(adjusted).all() and (adjusted>=0).all() and (np.diff(adjusted,axis=1)>=0).all())
    require('Intervals expand, never shrink',(adjusted[:,0]<=q[:,0]).all() and (adjusted[:,2]>=q[:,2]).all())
    for name,array in [('raw_on_calibration',q),('adjusted_on_fit_data',adjusted)]:
        count=sum(lo<=a<=hi for a,lo,hi in zip(y,array[:,0],array[:,2]))
        ref=summary[name]
        require(name+' independent coverage',count==ref['covered'] and math.isclose(count/len(y),ref['coverage'],abs_tol=1e-12))
        width=sum(hi-lo for lo,hi in zip(array[:,0],array[:,2]))/len(y)
        require(name+' independent width',math.isclose(width,ref['mean_width_inr'],abs_tol=1e-6))
    fits=set(prov['diagnostic_fit_ids']);held=set(prov['diagnostic_check_ids'])
    require('Diagnostic roles disjoint and exhaustive',not fits.intersection(held) and fits|held==ids and len(fits)==408 and len(held)==175)
    ordered_ids=sorted(ids,key=lambda x:hashlib.sha256((plan['diagnostic_split']['seed']+':'+x).encode()).hexdigest())
    require('Diagnostic membership follows predetermined ID hash',fits==set(ordered_ids[:408]) and held==set(ordered_ids[408:]))
    fit_scores=[s for name,s in zip(predicted.index,independent_scores) if name in fits]
    diag_correction=sorted(fit_scores)[(4*(len(fit_scores)+1)+4)//5-1]
    require('Diagnostic correction uses fit subset only',math.isclose(diag_correction,summary['heldback_diagnostic']['correction']['correction_inr'],abs_tol=1e-6))
    checkframe=pd.read_json(out/'data/heldback_diagnostic_predictions.jsonl',lines=True)
    require('Only held-back IDs in diagnostic predictions',set(checkframe.agreement_id)==held)
    covered=sum(lo<=actual<=hi for lo,actual,hi in zip(checkframe.diagnostic_lower,checkframe.actual_sale,checkframe.diagnostic_upper))
    require('Held-back coverage reconciles',covered==summary['heldback_diagnostic']['adjusted_on_check']['covered'])
    require('Refit fit-coverage not called validation',summary['adjusted_fit_coverage_is_not_validation'] is True)
    require('Final model not retrained or final-test scored',summary['model_retrained'] is False and summary['final_test_scored'] is False)
    sold=pd.to_datetime(source.sold_date);seized=pd.to_datetime(source.seizure_date)
    prior_counts=[sum(a<t for a in sold) for t in seized]
    require('Forward-replay sample availability reconciles',max(prior_counts)==summary['forward_replay']['max_prior_calibration_labels'])
    require('No unsupported online-validation claim',sum(n>=200 for n in prior_counts)==summary['forward_replay']['eligible_calibration_seizures']==0)
    # Small explicit examples test the mathematics independently of the source data.
    toy=np.array([[10.,15.,20.]]*5)
    fitted,_=fit_correction([15,21,22,23,24],toy,alpha=.2,min_count=1)
    require('Toy finite-rank correction equals four',fitted['rank_one_based']==5 and fitted['correction_inr']==4)
    require('Zero-floor expansion example',expand([[1,2,3]],4).tolist()==[[0.,2.,7.]])
    zero,_=fit_correction([15]*5,toy,alpha=.2,min_count=1)
    require('Already covered toy has zero expansion',zero['correction_inr']==0)
    rejects('Insufficient finite-rank sample rejected',lambda:fit_correction([15]*3,toy[:3],min_count=1))
    rejects('Below configured sample minimum rejected',lambda:fit_correction([15]*5,toy,min_count=200))
    rejects('Invalid alpha rejected',lambda:fit_correction([15]*5,toy,alpha=1,min_count=1))
    rejects('Crossing quantiles rejected',lambda:fit_correction([15]*5,np.array([[20,15,10]]*5),min_count=1))
    rejects('Negative correction rejected',lambda:expand(toy,-1))
    rejects('Nonfinite correction rejected',lambda:expand(toy,float('nan')))
    wrapper=CalibratedValuator(out/'models')
    # Reproduction only, not a prospective test on these already consumed calibration cases.
    require('Versioned wrapper reproduces bundle outputs',np.allclose(wrapper.predict(source[FEATURES],'2026-05-01'),adjusted,atol=1e-6,rtol=0))
    rejects('Unavailable historical version rejected',lambda:wrapper.predict(source[FEATURES].iloc[:1],'2026-04-30'))
    bad=source[FEATURES].iloc[:1].copy();bad['sale_amount']=1
    rejects('Target leakage rejected by wrapper',lambda:wrapper.predict(bad,'2026-05-01'))
    result={'status':'passed','check_count':len(checks),'checks':checks,'final_test_scored':False}
    (out/'reports/verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='checks'},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for a in ['phase1','phase2','phase3','output']:p.add_argument('--'+a,type=Path,required=True)
    a=p.parse_args();verify(a.phase1,a.phase2,a.phase3,a.output)
