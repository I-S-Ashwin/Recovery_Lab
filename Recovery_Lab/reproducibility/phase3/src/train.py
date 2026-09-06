"""Fixed-budget CatBoost development search. No calibration or final-test scoring."""
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import time

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor,Pool
from valuation import FEATURES,CATEGORICAL,prepare,ordered


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,obj):Path(p).write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def jlines(p,df):Path(p).write_text(''.join(json.dumps(r,allow_nan=False)+'\n' for r in df.to_dict('records')),encoding='utf-8')
def metrics(y,p):
    y=np.asarray(y,float);p=np.asarray(p,float);e=p-y
    return {'n':len(y),'mae_inr':float(np.abs(e).mean()),'rmse_inr':float(np.sqrt(np.square(e).mean())),
            'mape_percent':float((np.abs(e)/y).mean()*100),'median_absolute_error_inr':float(np.median(np.abs(e))),
            'mean_signed_error_inr':float(e.mean())}
def qmetrics(y,raw,q):
    y=np.asarray(y,float);pin={}
    for i,a in enumerate([.1,.5,.9]):
        error=y-q[:,i];pin[str(a)]=float(np.maximum(a*error,(a-1)*error).mean())
    return {'pinball_loss_inr':pin,'raw_crossing_rows':int(np.any(np.diff(raw,axis=1)<0,axis=1).sum()),
            'ordered_central_range_coverage':float(((y>=q[:,0])&(y<=q[:,2])).mean()),
            'mean_range_width_inr':float((q[:,2]-q[:,0]).mean()),'calibrated':False}


def train(p1,p2,out):
    p1=p1.resolve();p2=p2.resolve();out=out.resolve()
    for folder in ['models','reports','data']: (out/folder).mkdir(parents=True,exist_ok=True)
    plan=json.loads((out/'configs/search_plan.json').read_text())
    summary2=json.loads((p2/'reports/summary.json').read_text())
    data_path=p1/'data/canonical_records.jsonl'
    assert sha(data_path)==summary2['input_sha256']
    assert json.loads((p1/'configs/feature_policy.json').read_text())['seizure_core_candidate_features']==FEATURES
    for protocol,h in summary2['split_manifest_hashes'].items():
        assert sha(p2/f'data/{protocol}_split_manifest.jsonl')==h
    lock={'canonical_sha256':sha(data_path),'phase2_split_hashes':summary2['split_manifest_hashes'],
          'search_plan_sha256':sha(out/'configs/search_plan.json'),'frozen_before_fit_utc':datetime.now(timezone.utc).isoformat(),
          'source_code_sha256':{n:sha(out/'src'/n) for n in ['train.py','valuation.py']},
          'selection_role':'operational.tuning','reserved_outcomes_scored':False}
    lockfile=out/'experiment_lock.json'
    if lockfile.exists():
        old=json.loads(lockfile.read_text())
        for key in ['canonical_sha256','phase2_split_hashes','search_plan_sha256','source_code_sha256']:
            if old[key]!=lock[key]:raise ValueError('Locked experiment changed: '+key)
    else:save(lockfile,lock)
    d=pd.read_json(data_path,lines=True)
    manifests={p:pd.read_json(p2/f'data/{p}_split_manifest.jsonl',lines=True) for p in ['operational','retrospective']}
    idx=d.set_index('agreement_id',drop=False)
    def cohort(protocol,role):
        m=manifests[protocol]
        return idx.loc[m.loc[m.role.eq(role),'agreement_id']].copy()
    tr=cohort('operational','train');va=cohort('operational','tuning')
    assert len(tr)==9767 and len(va)==576 and not set(tr.agreement_id)&set(va.agreement_id)
    assert pd.to_datetime(tr.sold_date).lt('2026-01-01').all()
    assert pd.to_datetime(va.sold_date).lt('2026-03-01').all()
    x=prepare(tr[FEATURES]);vx=prepare(va[FEATURES])
    train_pool=Pool(x,tr.sale_amount,cat_features=CATEGORICAL)
    valid_pool=Pool(vx,va.sale_amount,cat_features=CATEGORICAL)
    trials=[];best_mae=float('inf');winner=None
    for candidate in plan['candidates']:
        config={k:v for k,v in candidate.items() if k!='trial_id'}
        model=CatBoostRegressor(**config,loss_function=plan['loss_function'],eval_metric=plan['early_stopping_metric'],
                               iterations=plan['iterations'],random_seed=plan['random_seed'],thread_count=plan['thread_count'],
                               task_type=plan['task_type'],allow_writing_files=False,verbose=False)
        start=time.perf_counter()
        model.fit(train_pool,eval_set=valid_pool,early_stopping_rounds=plan['early_stopping_rounds'],use_best_model=True)
        raw=np.asarray(model.predict(vx,thread_count=4));q=ordered(raw)
        row={**candidate,'tree_count':model.tree_count_,'best_iteration_zero_based':model.get_best_iteration(),
             'fit_seconds':time.perf_counter()-start,**metrics(va.sale_amount,q[:,1]),
             'quantile_diagnostics':qmetrics(va.sale_amount,raw,q)}
        trials.append(row);save(out/'reports/trials.json',trials)
        print(json.dumps({'trial':candidate['trial_id'],'trees':model.tree_count_,'mae_inr':row['mae_inr'],'seconds':row['fit_seconds']}),flush=True)
        if row['mae_inr']<best_mae:
            winner=candidate['trial_id'];best_mae=row['mae_inr']
            model.save_model(str(out/'models/catboost_quantiles.cbm'))
            save(out/'models/selected_parameters.json',model.get_all_params())
    best=CatBoostRegressor();best.load_model(str(out/'models/catboost_quantiles.cbm'))
    results=[];segment_results=[];support=[]
    for protocol in ['operational','retrospective']:
        c=cohort(protocol,'tuning');features=prepare(c[FEATURES]);raw=np.asarray(best.predict(features,thread_count=4));q=ordered(raw)
        baseline=pd.read_json(p2/f'data/{protocol}_tuning_predictions.jsonl',lines=True).set_index('agreement_id')
        assert set(baseline.index)==set(c.agreement_id)
        b=baseline.loc[c.agreement_id,'baseline_prediction'].to_numpy()
        cm=metrics(c.sale_amount,q[:,1]);bm=metrics(c.sale_amount,b)
        results.append({'protocol':protocol,'role':'tuning','catboost':cm,'baseline':bm,
                        'mae_reduction_percent':100*(bm['mae_inr']-cm['mae_inr'])/bm['mae_inr'],
                        'quantile_diagnostics':qmetrics(c.sale_amount,raw,q)})
        pred=pd.DataFrame({'agreement_id':c.agreement_id.to_numpy(),'actual_sale':c.sale_amount.to_numpy(),
                           'raw_q10':raw[:,0],'raw_q50':raw[:,1],'raw_q90':raw[:,2],
                           'ordered_q10':q[:,0],'ordered_q50':q[:,1],'ordered_q90':q[:,2],
                           'baseline_prediction':b})
        jlines(out/f'data/{protocol}_tuning_predictions.jsonl',pred)
        for col in ['asset_fuel_type','asset_model','customer_region']:
            for key in sorted(c[col].unique()):
                mask=c[col].eq(key).to_numpy()
                segment_results.append({'protocol':protocol,'field':col,'segment':str(key),'weak_sample':int(mask.sum())<100,
                                        'catboost':metrics(c.sale_amount.to_numpy()[mask],q[mask,1]),
                                        'baseline':metrics(c.sale_amount.to_numpy()[mask],b[mask])})
        support.append({'protocol':protocol,'unknown_category_rows_by_field':{col:int((~features[col].isin(set(x[col]))).sum()) for col in CATEGORICAL},
                        'numeric_training_bounds':{col:{'min':float(x[col].min()),'max':float(x[col].max())} for col in FEATURES[7:]}})
    importance=best.get_feature_importance(type='PredictionValuesChange')
    save(out/'reports/global_feature_importance.json',sorted([{'feature':f,'importance':float(v),'type':'PredictionValuesChange; global, not causal'} for f,v in zip(FEATURES,importance)],key=lambda r:-r['importance']))
    save(out/'reports/comparison.json',results);save(out/'reports/segment_metrics.json',segment_results);save(out/'reports/support.json',support)
    contract={'features':FEATURES,'categorical_features':CATEGORICAL,'target':'sale_amount','currency':'INR',
              'quantiles':[.1,.5,.9],'calibrated':False,'postprocessing':plan['postprocessing'],
              'category_missing_token':'__MISSING__','numeric_missing_policy':'reject','unknown_category_policy':'CatBoost accepts; review support',
              'training_category_values':{col:sorted(x[col].unique().tolist()) for col in CATEGORICAL},
              'training_numeric_bounds':support[0]['numeric_training_bounds']}
    save(out/'models/feature_contract.json',contract)
    versions={name:importlib.metadata.version(name) for name in ['catboost','numpy','pandas','scipy']}
    selected=next(r for r in trials if r['trial_id']==winner)
    final={'winner':winner,'selected_trial':selected,'training_records':len(tr),'operational_tuning_records':len(va),
           'hyperparameter_selection_earliest_available_date_proxy':'2026-03-01',
           'role':'candidate for Phase 4; not production approved','calibration_performed':False,'final_test_scored':False,
           'comparison':results,'python_version':platform.python_version(),'package_versions':versions,
           'training_feature_count':len(FEATURES),'model_sha256':sha(out/'models/catboost_quantiles.cbm'),
           'candidate_improves_operational_mae':best_mae<results[0]['baseline']['mae_inr']}
    save(out/'reports/summary.json',final)
    source={'phase1_data_sha256':sha(data_path),'phase2_manifests_sha256':summary2['split_manifest_hashes'],
            'trained_ids':tr.agreement_id.tolist(),'selection_ids':va.agreement_id.tolist(),
            'note':'IDs record fit/selection membership; no reserved prediction outcomes were scored.'}
    save(out/'models/training_provenance.json',source)
    report=['# Phase 3: CatBoost model development','','Six predeclared CatBoost quantile candidates were trained on the frozen training set. The winner was selected by operational tuning median MAE. These are tuning results, not unbiased final-test performance.','',
            f'Training rows: {len(tr):,}. Operational tuning rows: {len(va):,}. Predictors: {len(FEATURES)}. Selected trial: {winner}, {selected["tree_count"]} trees.','',
            '## Development comparison','','| Protocol | Rows | Baseline MAE INR | CatBoost MAE INR | MAE reduction | CatBoost RMSE INR |','|---|---:|---:|---:|---:|---:|']
    for r in results:report.append(f'| {r["protocol"]} | {r["catboost"]["n"]:,} | {r["baseline"]["mae_inr"]:,.0f} | {r["catboost"]["mae_inr"]:,.0f} | {r["mae_reduction_percent"]:.1f}% | {r["catboost"]["rmse_inr"]:,.0f} |')
    report+=['','MAE is average absolute error in rupees. A reduction here is a development improvement, not a profit uplift or a guaranteed future accuracy gain. The retrospective tuning set overlaps the operational tuning set and is diagnostic only. It was not used to select the winner.','',
             '## Fixed search','','| Trial | Depth | Learning rate | L2 | Trees retained | Operational MAE INR |','|---|---:|---:|---:|---:|---:|']
    for r in trials:report.append(f'| {r["trial_id"]} | {r["depth"]} | {r["learning_rate"]} | {r["l2_leaf_reg"]} | {r["tree_count"]} | {r["mae_inr"]:,.0f} |')
    report+=['','Early stopping uses MultiQuantile loss on operational tuning; candidate selection uses ordered median MAE on that same development set. Maximum 1,000 iterations, patience 80, fixed seed 2026, four CPU threads. No extra search was added after results.','',
             '## Uncertainty output','','The model outputs raw 0.10, 0.50 and 0.90 quantiles. The shared inference function sorts them per record and floors at zero. Sorting can change the middle prediction when quantiles cross; the same transformed median is used in every reported comparison. This is postprocessing, not calibration. Raw and ordered outputs are retained in tuning exports.',
             'The displayed lower/upper range is uncalibrated. Its development coverage and width are diagnostic only, particularly because the same cases drove early stopping and selection. Phase 4 must calibrate on the reserved calibration role.','',
             '## Time and population limitations','','Training sale labels precede 1 January 2026; the operational tuning outcomes precede 1 March. Model weights use only training outcomes, but settings and stopping iteration were selected using later tuning outcomes. Therefore the selected model can be treated as available no earlier than 1 March under the sale-date arrival assumption; its tuning performance is not an independently deployed January backtest.',
             'Only sold assets appear in the source. The operational tuning sample additionally requires sale by its development boundary, favoring faster recoveries. Field timestamps, real vehicle/customer IDs and operational label-arrival timestamps are missing. These limitations remain despite computational leakage checks.',
             'The original asset-age column is not used. The explicitly named agreement-to-seizure elapsed duration is used instead. Inspection/document/accident fields remain excluded pending source definitions. There is no customer-default model or long-horizon forecast here.','',
             '## Saved model and handoff','','The native CatBoost model, exact fitted parameters, feature contract, fit/selection IDs, versions and hashes are included. Inference rejects missing/extra fields and invalid cost/duration. Category novelty is recorded separately from prediction validity. Global feature importance is not a causal explanation or a per-customer reason.',
             'Freeze this model for Phase 4 before accessing calibration outcomes. Do not refit on calibration or final-test labels. A later refit needs a new model version and a new calibration design. The final-test roles remain unscored.','',
             '## Research and implementation reference','','CatBoost officially supports the MultiQuantile objective used here: https://catboost.ai/docs/en/concepts/loss-functions-regression . Its availability does not establish performance on this dataset; the measured development comparison above does.']
    (out/'reports/Phase_3_Report.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
    print(json.dumps({'winner':winner,'comparison':results,'versions':versions}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase1',type=Path,required=True);p.add_argument('--phase2',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();train(a.phase1,a.phase2,a.output)
