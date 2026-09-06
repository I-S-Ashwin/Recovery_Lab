"""Fault injection, SHAP reconciliation, persistence and local deployment tests."""
import json
import os
from pathlib import Path
import shutil
import tempfile
from unittest.mock import patch
from fastapi.testclient import TestClient
import pandas as pd
from service import app, ROOT
from operations import AuditJournal, RateLimit, verify_bundle

def main():
    checks=[]
    def check(name,truth):
        if not truth:raise AssertionError(name)
        checks.append(name)
    cases=json.loads((ROOT/'data/calibration_lookup.json').read_text())
    features=cases['ASSET_40']['features']
    request={'request_id':'private-sentinel-do-not-store','mode':'seizure','as_of_date':'2026-09-06','features':features,
             'feature_sources':{k:{'available_on':'2026-09-06','source':'Fictional test metadata'} for k in features}}
    with tempfile.TemporaryDirectory() as temp:
        os.environ['TVS_RUNTIME_DIR']=str(Path(temp)/'runtime')
        with TestClient(app) as client:
            good=client.post('/v1/valuations',json=request)
            check('healthy inference',good.status_code==200)
            baseline=good.json()
            for asset in sorted(cases)[:5]:
                test={**request,'features':cases[asset]['features']}
                response=client.post('/v1/valuations',json=test).json()
                e=response['explanation']
                check('native SHAP available '+asset,e['method']=='Native CatBoost SHAP')
                check('SHAP all nine inputs '+asset,len(e['contributions'])==9)
                check('SHAP reconstructs median '+asset,abs(e['base_value_inr']+sum(x['contribution_inr'] for x in e['contributions'])-response['median_value_inr'])<.01)
                check('three individual reasons '+asset,len(e['sentences'])==3)
            with patch.object(app.state.valuator,'predict',side_effect=RuntimeError('simulated failure')):
                fallback=client.post('/v1/valuations',json=request).json()
                expected=app.state.baseline.predict(pd.DataFrame([features])).iloc[0]['prediction']
                check('frozen baseline fallback exact',abs(fallback['median_value_inr']-expected)<1e-8)
                check('fallback requires review',fallback['status']=='review_required')
                check('fallback has no interval',fallback['interval_lower_inr'] is None and fallback['interval_upper_inr'] is None)
                check('fallback has no coverage claim',fallback['nominal_coverage'] is None)
                check('degraded readiness',client.get('/ready').status_code==503)
                check('health survives model failure',client.get('/health').status_code==200)
                with patch.object(app.state.baseline,'predict',side_effect=RuntimeError('second failure')):
                    check('both models fail closed',client.post('/v1/valuations',json=request).status_code==503)
                bad={**request,'as_of_date':'2026-04-01'}
                check('invalid dates do not invoke fallback',client.post('/v1/valuations',json=bad).status_code==422)
            restored=client.post('/v1/valuations',json=request).json()
            check('recovered model exact',restored['median_value_inr']==baseline['median_value_inr'])
            check('readiness recovers',client.get('/ready').status_code==200)
            with patch('service.explain',side_effect=RuntimeError('SHAP unavailable')):
                result=client.post('/v1/valuations',json=request).json()
                check('attribution failure preserves estimate',result['median_value_inr']==baseline['median_value_inr'])
                check('attribution unavailable labeled',result['explanation']['method']=='unavailable')
            events=client.get('/v1/audit').json()
            check('audit endpoint reports events',events['summary']['recorded_requests']>0)
            check('raw request id absent',request['request_id'] not in json.dumps(events))
            check('raw inputs absent','asset_variant' not in json.dumps(events))
            check('fallback outcome auditable',any(x['decision_status']=='baseline_review' for x in events['recent']))
            key=app.state.audit.key;count=app.state.audit.summary()['recorded_requests']
            second=AuditJournal(Path(temp)/'runtime')
            check('audit persists across new connection',second.summary()['recorded_requests']==count)
            check('key persists across new instance',second.key==key)
            with patch.object(app.state.audit,'record',side_effect=OSError('disk full')):
                failed=client.post('/v1/valuations',json=request)
                check('audit failure blocks decision',failed.status_code==503 and 'median_value_inr' not in failed.text)
            app.state.rate_limit=RateLimit(limit=1)
            check('rate limit initial request',client.get('/v1/model-info').status_code==200)
            check('rate limit rejects excess',client.get('/v1/model-info').status_code==429)
            check('health unaffected by rate limit',client.get('/health').status_code==200)
            check('process is loopback only',TestClient(app,client=('203.0.113.10',1234)).get('/health').status_code==403)
        with TestClient(app) as restarted:
            check('clean lifecycle restart',restarted.get('/ready').status_code==200)
            check('audit survives lifecycle restart',restarted.get('/v1/audit').json()['summary']['recorded_requests']>=count)
        clone=Path(temp)/'bundle';clone.mkdir()
        (clone/'model.bin').write_bytes(b'wrong')
        (clone/'bundle_lock.json').write_text(json.dumps({'model.bin':'0'*64}))
        try:verify_bundle(clone)
        except RuntimeError:checks.append('tampered artifact rejected')
        else:raise AssertionError('Tampered artifact accepted')
    (ROOT/'reports/operations_verification.json').write_text(json.dumps({'passed':len(checks),'failed':0,'checks':checks},indent=2)+'\n')
    print(json.dumps({'operations_checks_passed':len(checks)}))

if __name__=='__main__':main()
