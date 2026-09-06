"""API contract and cross-phase integration regression suite; no final-test labels."""
import copy
import hashlib
import json
from pathlib import Path
from fastapi.testclient import TestClient
import pandas as pd
from service import app, ROOT, read

def main():
    checks=[]
    def check(name,ok):
        if not ok: raise AssertionError(name)
        checks.append(name)
    features={'customer_branch':'HYDERABAD I','customer_region':'AP','customer_state':'AP','pincode_tier':'02 Megapolis (B)',
        'asset_variant':'TVS XL 100 HD ITS','asset_model':'MOPEDS','asset_fuel_type':'Petrol',
        'asset_cost_at_disbursal':81000,'months_since_agreement_at_seizure':18}
    request={'request_id':'verification-fictional','mode':'seizure','as_of_date':'2026-09-06','features':features,
             'feature_sources':{k:{'available_on':'2026-09-06','source':'Fictional verification fixture'} for k in features}}
    with TestClient(app) as client:
        def post(path,payload):return client.post(path,json=payload)
        check('health',client.get('/health').status_code==200)
        check('ready model loaded',client.get('/ready').json()['status']=='ready')
        check('OpenAPI documents endpoints',set(client.get('/openapi.json').json()['paths'])=={'/health','/ready','/v1/audit','/v1/model-info','/v1/demo-portfolio','/v1/calibration-cases/{agreement_id}','/v1/valuations','/v1/projections','/v1/lending-simulations','/v1/portfolio-scenarios'})
        response=post('/v1/valuations',request)
        check('valuation response',response.status_code==200)
        check('request trace',bool(response.headers.get('x-request-id')))
        check('no browser caching',response.headers.get('cache-control')=='no-store')
        value=response.json()
        expected=app.state.valuator.predict(pd.DataFrame([features]),'2026-09-06')[0]
        check('same calibrated model output',all(abs(value[k]-float(v))<1e-8 for k,v in zip(['interval_lower_inr','median_value_inr','interval_upper_inr'],expected)))
        check('ordered nonnegative interval',0<=value['interval_lower_inr']<=value['median_value_inr']<=value['interval_upper_inr'])
        for name,mutate in [
            ('forbidden outcome',lambda r:r['features'].update(sale_amount=100)),
            ('forbidden top field',lambda r:r.update(actual_sale=100)),
            ('missing feature',lambda r:r['features'].pop('customer_branch')),
            ('negative cost',lambda r:r['features'].update(asset_cost_at_disbursal=-1)),
            ('boolean cost',lambda r:r['features'].update(asset_cost_at_disbursal=True)),
            ('negative duration',lambda r:r['features'].update(months_since_agreement_at_seizure=-1)),
            ('blank category',lambda r:r['features'].update(asset_model='  ')),
            ('missing metadata',lambda r:r['feature_sources'].pop('asset_model')),
            ('future feature',lambda r:r['feature_sources']['asset_model'].update(available_on='2026-09-07')),
            ('unsupported mode',lambda r:r.update(mode='origination')),
            ('precalibration date',lambda r:(r.update(as_of_date='2026-04-30'),[x.update(available_on='2026-04-30') for x in r['feature_sources'].values()]))]:
            bad=copy.deepcopy(request);mutate(bad)
            check(name,post('/v1/valuations',bad).status_code==422)
        for key,v in [('asset_model','UNKNOWN'),('asset_cost_at_disbursal',500000)]:
            bad=copy.deepcopy(request);bad['features'][key]=v
            result=post('/v1/valuations',bad).json()
            check('support review '+key,result['status']=='review_required' and bool(result['support_warnings']))
        check('unknown endpoint',client.get('/v1/unknown').status_code==404)
        check('untrusted host',client.get('/health',headers={'host':'evil.example'}).status_code==400)
        check('cross-origin blocked',client.post('/v1/valuations',json=request,headers={'origin':'https://evil.example'}).status_code==403)
        check('non-json blocked',client.post('/v1/valuations',content='test',headers={'content-type':'text/plain'}).status_code==415)
        check('oversize blocked',client.post('/v1/valuations',content=' '*131073,headers={'content-type':'application/json'}).status_code==413)
        check('malformed json',client.post('/v1/valuations',content='{',headers={'content-type':'application/json'}).status_code==422)
        ref={'asset_id':'DEMO-A','valuation_date':'2026-09-06','downside_anchor_inr':70000,'median_anchor_inr':85000}
        projection=post('/v1/projections',{'reference':ref,'scenario':'adverse','months':[12,24,36]}).json()
        check('projection independent arithmetic',projection['values'][0]['downside_value_inr']==50400)
        check('unsupported horizon',post('/v1/projections',{'reference':ref,'months':[43]}).status_code==422)
        check('boolean horizon rejected',post('/v1/projections',{'reference':ref,'months':[True]}).status_code==422)
        check('string horizon rejected',post('/v1/projections',{'reference':ref,'months':['12']}).status_code==422)
        invalid_json=json.dumps(request).replace('81000','NaN')
        check('nonfinite value rejected safely',client.post('/v1/valuations',content=invalid_json,headers={'content-type':'application/json'}).status_code==422)
        check('reversed anchors',post('/v1/projections',{'reference':{**ref,'downside_anchor_inr':90000}}).status_code==422)
        lending={'request_id':'API-BASE','reference':ref,'scenario':'base','asset_reference_cost_inr':100000,
                 'verified_monthly_income_inr':30000,'existing_monthly_obligations_inr':5000,
                 'income_verified':True,'obligations_verified':True}
        for s in ['base','adverse','severe']:
            result=post('/v1/lending-simulations',{**lending,'scenario':s}).json()
            old=read(ROOT.parent/f'phase6/results/offers/DEMO-A-{s}.json')
            check('identical phase6 candidates '+s,result['candidates']==old['candidates'])
            check('identical phase6 offer '+s,result['recommended_offer']==old['recommended_offer'])
            check('no automatic approval '+s,result['automatic_approval'] is False)
        for key in ['income_verified','obligations_verified']:
            check('verification required '+key,post('/v1/lending-simulations',{**lending,key:False}).json()['status']=='review_required')
            check('string verification rejected '+key,post('/v1/lending-simulations',{**lending,key:'true'}).status_code==422)
        check('missing obligations',post('/v1/lending-simulations',{**lending,'existing_monthly_obligations_inr':None}).json()['status']=='review_required')
        check('zero income rejected',post('/v1/lending-simulations',{**lending,'verified_monthly_income_inr':0}).status_code==422)
        fixtures=client.get('/v1/demo-portfolio').json()['assets']
        assets=[{'reference':{k:a[k] for k in ['asset_id','valuation_date','downside_anchor_inr','median_anchor_inr']},
                 **{k:a[k] for k in ['existing_principal_inr','annual_nominal_rate','remaining_term_months']}} for a in fixtures]
        existing=read(ROOT.parent/'phase6/results/fixed_book_stress.json')
        for s in ['base','adverse','severe']:
            for h in [0,12,24,36]:
                result=post('/v1/portfolio-scenarios',{'assets':assets,'scenario':s,'default_month':h}).json()
                old=next(x for x in existing if x['scenario']==s and x['default_month']==h)
                check('same fixed book '+s+str(h),all(result[k]==old[k] for k in ['exposure_inr','downside_shortfall_inr','exposure_weighted_shortfall_ratio','assets']))
        check('duplicate portfolio asset',post('/v1/portfolio-scenarios',{'assets':[assets[0],assets[0]]}).status_code==422)
        bad=copy.deepcopy(assets);bad[0]['reference']['valuation_date']='2026-09-05'
        check('mixed dates rejected',post('/v1/portfolio-scenarios',{'assets':bad}).status_code==422)
        check('empty portfolio rejected',post('/v1/portfolio-scenarios',{'assets':[]}).status_code==422)
        case=client.get('/v1/calibration-cases/ASSET_40').json()
        check('lookup calibration label','Calibration fitting' in case['evidence_type'])
        check('lookup unknown ID',client.get('/v1/calibration-cases/MISSING').status_code==404)
        ids=set(read(ROOT/'data/calibration_lookup.json'))
        manifest=[json.loads(x) for x in (ROOT.parent/'phase2/data/operational_split_manifest.jsonl').read_text().splitlines()]
        final_ids={x['agreement_id'] for x in manifest if x.get('role') in ['test','final_test']}
        check('final test exclusion check nonempty',len(final_ids)==1244)
        check('calibration lookup only 583',len(ids)==583)
        expected_ids={x['agreement_id'] for x in map(json.loads,(ROOT.parent/'phase4/data/calibration_predictions.jsonl').read_text().splitlines())}
        check('exact calibration cohort',ids==expected_ids)
        check('no final-test lookup overlap',not ids&final_ids)
        for src,target in [('phase4/src/calibrated.py','api/calibrated.py'),('phase4/src/frozen_valuation.py','api/frozen_valuation.py'),('phase6/src/projection.py','api/projection.py'),('phase6/src/frozen_policy.py','api/frozen_policy.py')]:
            check('frozen code '+target,(ROOT.parent/src).read_bytes()==(ROOT/target).read_bytes())
        for p,sha in read(ROOT/'source_lock.json').items():
            check('source integrity '+p,hashlib.sha256((ROOT.parent/p).read_bytes()).hexdigest()==sha)
        save={'passed':len(checks),'failed':0,'checks':checks,'demo_valuation':value,'scope':'API and shared-engine integration; no browser interaction tests'}
        (ROOT/'reports/verification.json').write_text(json.dumps(save,indent=2)+'\n')
        (ROOT/'reports/openapi.json').write_text(json.dumps(app.openapi(),indent=2)+'\n')
        print(json.dumps({'passed':len(checks),'failed':0,'demo_median':value['median_value_inr']}))

if __name__=='__main__':main()
