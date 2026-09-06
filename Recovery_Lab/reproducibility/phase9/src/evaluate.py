"""Frozen final evaluation. This script never trains, selects or calibrates a model."""
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
from calibrated import CalibratedValuator, expand
from frozen_baseline import MedianRatioBaseline,duration_bin
from frozen_valuation import FEATURES

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT.parent
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def lines(path):return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines()]
def save(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def wilson(success,n,z=1.959963984540054):
    p=success/n;den=1+z*z/n
    center=(p+z*z/(2*n))/den
    half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0,center-half),min(1,center+half)]

def point(y,p):
    error=p-y;ae=np.abs(error);sst=float(np.sum((y-y.mean())**2))
    return {'n':len(y),'mae_inr':float(ae.mean()),'rmse_inr':float(np.sqrt(np.mean(error**2))),
            'median_absolute_error_inr':float(np.median(ae)),'mape_percent':float(np.mean(ae/y)*100),
            'wape_percent':float(ae.sum()/y.sum()*100),'r2':1-float(np.sum(error**2))/sst if sst>0 else None,
            'mean_signed_error_inr':float(error.mean())}

def interval(y,lo,hi,alpha=.2):
    cover=(y>=lo)&(y<=hi);n=len(y);width=hi-lo
    score=width+2/alpha*np.maximum(lo-y,0)+2/alpha*np.maximum(y-hi,0)
    return {'n':n,'covered':int(cover.sum()),'coverage':float(cover.mean()),
            'wilson_95':wilson(int(cover.sum()),n),'below':int((y<lo).sum()),'above':int((y>hi).sum()),
            'mean_width_inr':float(width.mean()),'median_width_inr':float(np.median(width)),
            'mean_interval_score_inr':float(score.mean()),'alpha':alpha}

def paired_bootstrap(y,model,base,config):
    difference=np.abs(base-y)-np.abs(model-y)
    rng=np.random.default_rng(config['seed']);values=[]
    for _ in range(config['replicates']//100):
        indexes=rng.integers(0,len(y),size=(100,len(y)))
        values.extend(difference[indexes].mean(axis=1).tolist())
    return {'mean_mae_reduction_inr':float(difference.mean()),'percentile_95_inr':np.quantile(values,[.025,.975]).tolist(),
            'replicates':len(values),'seed':config['seed'],'positive_means_model_better':True,
            'caveat':'Case-resampling interval conditional on fixed models; ignores temporal, entity and training dependence'}

def metrics(rows):
    y=np.array([r['actual_sale_inr'] for r in rows]);p=np.array([r['median_inr'] for r in rows]);b=np.array([r['baseline_inr'] for r in rows])
    model=point(y,p);baseline=point(y,b)
    raw=interval(y,np.array([r['base_lower_inr'] for r in rows]),np.array([r['base_upper_inr'] for r in rows]))
    calibrated=interval(y,np.array([r['calibrated_lower_inr'] for r in rows]),np.array([r['calibrated_upper_inr'] for r in rows]))
    return {'model':model,'baseline':baseline,'mae_reduction_percent':100*(baseline['mae_inr']-model['mae_inr'])/baseline['mae_inr'],
            'base_interval':raw,'calibrated_interval':calibrated}

def main():
    lock=read(ROOT/'configs/evaluation_lock.json')
    for p,sha in lock['artifact_sha256'].items():
        if digest(OUT/p)!=sha:raise RuntimeError('Frozen source changed: '+p)
    start=datetime.now(timezone.utc).isoformat()
    canonical={r['agreement_id']:r for r in lines(OUT/'phase1/data/canonical_records.jsonl')}
    manifests={p:lines(OUT/f'phase2/data/{p}_split_manifest.jsonl') for p in ['operational','retrospective']}
    finals={p:sorted(r['agreement_id'] for r in manifest if r['role']=='final_test') for p,manifest in manifests.items()}
    development={r['agreement_id'] for r in manifests['operational'] if r['role'] in ['train','tuning','calibration']}
    for p,ids in finals.items():
        if len(ids)!=lock['expected_counts'][p] or development&set(ids):raise RuntimeError('Incorrect or contaminated final-test cohort')
    model=CalibratedValuator(ROOT/'models');base=MedianRatioBaseline.load(ROOT/'models/B0_median_ratio.json')
    contract=read(ROOT/'models/base_feature_contract.json');results={};all_rows={}
    for protocol,ids in finals.items():
        records=[canonical[i] for i in ids]
        x=pd.DataFrame([{k:r[k] for k in FEATURES} for r in records])
        # Phase 4 wrapper is reused without fitting anything; operational dates are checked separately.
        q=model.model.predict(x)
        calibrated=model.predict(x,lock['retrospective_as_of_date'])
        baseline=base.predict(x).to_dict('records')
        rows=[]
        for i,r in enumerate(records):
            if protocol=='operational' and r['seizure_date'][:10]<model.calibration['available_from']:
                raise RuntimeError('Model unavailable at operational decision time')
            warnings=[]
            for k,values in contract['training_category_values'].items():
                if str(r[k]).strip() not in values:warnings.append(k+': unseen category')
            for k,bounds in contract['training_numeric_bounds'].items():
                if not bounds['min']<=r[k]<=bounds['max']:warnings.append(k+': outside training range')
            row={'agreement_id':r['agreement_id'],'protocol':protocol,'role':'final_test',
                'seizure_date':r['seizure_date'][:10],'sold_date':r['sold_date'][:10],
                'seizure_month':r['seizure_date'][:7],'sale_month':r['sold_date'][:7],
                'asset_fuel_type':r['asset_fuel_type'],'asset_model':r['asset_model'],'customer_region':r['customer_region'],
                'agreement_duration_bin':str(duration_bin(r['months_since_agreement_at_seizure'],base.lower_bounds)),
                'actual_sale_inr':float(r['sale_amount']),'baseline_inr':float(baseline[i]['prediction']),
                'baseline_reference_level':baseline[i]['fallback_level'],
                'base_lower_inr':float(q[i,0]),'median_inr':float(q[i,1]),'base_upper_inr':float(q[i,2]),
                'calibrated_lower_inr':float(calibrated[i,0]),'calibrated_upper_inr':float(calibrated[i,2]),
                'model_available_at_seizure':r['seizure_date'][:10]>=model.calibration['available_from'],
                'support_warnings':warnings}
            rows.append(row)
        (ROOT/f'data/{protocol}_final_predictions.jsonl').write_text(''.join(json.dumps(r,allow_nan=False)+'\n' for r in rows),encoding='utf-8')
        all_rows[protocol]=rows
        summary=metrics(rows)
        summary.update({'protocol':protocol,'role':'final_test','seizure_date_range':[min(r['seizure_date'] for r in rows),max(r['seizure_date'] for r in rows)],
                        'sale_date_range':[min(r['sold_date'] for r in rows),max(r['sold_date'] for r in rows)],
                        'model_available_at_seizure_count':sum(r['model_available_at_seizure'] for r in rows),
                        'unsupported_input_count':sum(bool(r['support_warnings']) for r in rows),
                        'support_warning_counts':dict(Counter(w for r in rows for w in r['support_warnings']))})
        results[protocol]=summary
        segments=[]
        for field in lock['segments']:
            for value in sorted({r[field] for r in rows}):
                subset=[r for r in rows if r[field]==value]
                segments.append({'field':field,'value':value,'n':len(subset),'small_sample':len(subset)<lock['small_segment_flag_below_n'],**metrics(subset)})
        save(ROOT/f'reports/{protocol}_segments.json',segments)
    primary=all_rows['operational']
    y=np.array([r['actual_sale_inr'] for r in primary]);p=np.array([r['median_inr'] for r in primary]);b=np.array([r['baseline_inr'] for r in primary])
    results['paired_mae_bootstrap']=paired_bootstrap(y,p,b,lock['paired_mae_bootstrap'])
    results['cohort_overlap']={'intersection':len(set(finals['operational'])&set(finals['retrospective'])),
                               'unique_test_ids':len(set(finals['operational'])|set(finals['retrospective'])),
                               'independent_replications':False}
    median_error=float(np.median(np.abs(p-y)))
    examples=[{'selection':'Nearest median absolute error','case':min(primary,key=lambda r:(abs(abs(r['median_inr']-r['actual_sale_inr'])-median_error),r['agreement_id']))},
              {'selection':'Largest absolute error','case':min(primary,key=lambda r:(-abs(r['median_inr']-r['actual_sale_inr']),r['agreement_id']))}]
    misses=[r for r in primary if r['actual_sale_inr']<r['calibrated_lower_inr']]
    if misses:examples.append({'selection':'Largest calibrated downside miss','case':min(misses,key=lambda r:(-(r['calibrated_lower_inr']-r['actual_sale_inr']),r['agreement_id']))})
    unsupported=[r for r in primary if r['support_warnings']]
    if unsupported:examples.append({'selection':'First unsupported agreement ID','case':min(unsupported,key=lambda r:r['agreement_id'])})
    save(ROOT/'reports/diagnostic_examples.json',examples)
    results.update({'evaluation_started_utc':start,'evaluation_completed_utc':datetime.now(timezone.utc).isoformat(),
                    'model_retrained':False,'calibration_refitted':False,'policy_changed':False,
                    'evaluation_lock_sha256':digest(ROOT/'configs/evaluation_lock.json')})
    for path,sha in lock['artifact_sha256'].items():
        if digest(OUT/path)!=sha:raise RuntimeError('Source changed during evaluation')
    save(ROOT/'reports/final_metrics.json',results)
    print(json.dumps({p:{'n':results[p]['model']['n'],'mae':results[p]['model']['mae_inr'],
         'baseline_mae':results[p]['baseline']['mae_inr'],'mae_reduction_percent':results[p]['mae_reduction_percent'],
         'coverage':results[p]['calibrated_interval']['coverage']} for p in finals}))

if __name__=='__main__':main()
