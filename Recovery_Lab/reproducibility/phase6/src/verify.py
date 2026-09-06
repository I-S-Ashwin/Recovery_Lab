"""Independent arithmetic, rejection, provenance and integration checks."""
import copy
import json
from decimal import Decimal
from run_phase6 import ROOT, OUT, read, save, digest
from projection import factor, project, aggregate, stress_asset
from frozen_policy import simulate


def main():
    checks=[]
    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)
    def rejects(name, call):
        try:
            call()
        except ValueError:
            checks.append(name); return
        raise AssertionError(name+' did not reject')
    cfg=read(ROOT/'configs/scenarios.json'); anchors=cfg['factor_anchors']
    a=read(ROOT/'examples/fictional_portfolio.json')[0]
    base,adverse,severe=cfg['scenarios']
    check('exact month12 factor',factor(12,anchors)==Decimal('.8'))
    check('linear month6 factor',factor(6,anchors)==Decimal('.9'))
    check('linear month39 factor',factor(39,anchors)==Decimal('.475'))
    check('month42 boundary',factor(42,anchors)==Decimal('.45'))
    for m in [-1,True,1.5,43]:
        rejects('invalid month '+str(m),lambda m=m:factor(m,anchors))
    rejects('duplicate anchors',lambda:factor(1,[{'month':0,'factor':1},{'month':0,'factor':.8}]))
    rejects('increasing factors',lambda:factor(1,[{'month':0,'factor':1},{'month':12,'factor':1.1}]))
    rejects('missing month zero',lambda:factor(1,[{'month':1,'factor':1}]))
    for invalid in [float('nan'),float('inf'),-1,True]:
        bad={**a,'downside_anchor_inr':invalid}
        rejects('invalid anchor '+str(invalid),lambda bad=bad:project(bad,12,base,anchors))
    rejects('reversed anchors',lambda:project({**a,'downside_anchor_inr':90000},12,base,anchors))
    rejects('invalid date',lambda:project({**a,'valuation_date':'invalid'},12,base,anchors))
    rejects('invalid delay',lambda:stress_asset(a,80000,0,{**base,'recovery_delay_months':-1},anchors))
    rejects('unsupported delayed recovery',lambda:stress_asset(a,80000,42,severe,anchors))
    p=project(a,12,adverse,anchors)
    check('independent downside product',p['downside_value_inr']==50400)
    check('independent median product',p['median_value_inr']==61200)
    check('no future coverage claim',p['future_coverage_guaranteed'] is False)
    rows=[{'exposure_inr':100,'downside_shortfall_inr':0},{'exposure_inr':900,'downside_shortfall_inr':450}]
    check('weighted aggregation not mean ratios',aggregate(rows)['exposure_weighted_shortfall_ratio']==.45)
    check('empty portfolio ratio undefined',aggregate([])['exposure_weighted_shortfall_ratio'] is None)
    locked=read(ROOT/'source_lock.json')
    for path,sha in locked['source_files'].items():
        check('source unchanged '+path,digest(OUT/path)==sha)
    check('frozen engine identical',digest(ROOT/'src/frozen_policy.py')==digest(OUT/'phase5/src/engine.py'))
    check('original canonical hash',digest(OUT/'phase1/data/canonical_records.jsonl')=='34a903573d80aed79b58da9bc59a11e3764c2f7ada5ac030e99536b8efe50be0')
    for item in read(ROOT/'results/monthly_projections.json'):
        values=item['monthly_values']
        check('bounded complete path '+item['asset_id']+item['scenario'],[x['month'] for x in values]==list(range(43)))
        check('nonincreasing nonnegative '+item['asset_id']+item['scenario'],all(0<=b['downside_value_inr']<=aa['downside_value_inr'] for aa,b in zip(values,values[1:])))
    book=read(ROOT/'results/fixed_book_stress.json')
    for h in [0,12,24,36]:
        slices=[next(x for x in book if x['default_month']==h and x['scenario']==s['name']) for s in cfg['scenarios']]
        check('constant fixed exposure '+str(h),len({x['exposure_inr'] for x in slices})==1)
        check('stress monotonic '+str(h),slices[0]['downside_shortfall_inr']<=slices[1]['downside_shortfall_inr']<=slices[2]['downside_shortfall_inr'])
    initial=next(x for x in book if x['default_month']==0 and x['scenario']=='base')
    check('independent initial exposure',initial['exposure_inr']==265000)
    check('individual deficits summed',initial['downside_shortfall_inr']==62000)
    policy=read(ROOT/'configs/demo_policy.json')
    for asset in ['DEMO-A','DEMO-B','DEMO-C']:
        principals=[]
        for s in cfg['scenarios']:
            req=read(ROOT/f'examples/{asset}-{s["name"]}.json')
            result=simulate(req,policy)
            check('reproducible offer '+req['request_id'],result==read(ROOT/f'results/offers/{req["request_id"]}.json'))
            check('path support '+req['request_id'],not any('missing_value' in r for c in result['candidates'] for r in c['constraint_failures']))
            principals.append(result['recommended_offer']['principal_inr'] if result['recommended_offer'] else 0)
        check('offer principal under stress '+asset,principals[0]>=principals[1]>=principals[2])
    req=read(ROOT/'examples/DEMO-A-base.json');req['downside_value_path']=[]
    check('empty future support cannot approve',simulate(req,policy)['status']!='feasible_offer')
    history=read(ROOT/'results/historical_price_stress.json')
    check('583 historical records',all(len(x['assets'])==583 for x in history))
    pred_ids={json.loads(x)['agreement_id'] for x in (OUT/'phase4/data/calibration_predictions.jsonl').read_text().splitlines()}
    check('only calibration ids',all({x['agreement_id'] for x in s['assets']}==pred_ids for s in history))
    check('historical stress monotonic',history[0]['downside_shortfall_inr']<=history[1]['downside_shortfall_inr']<=history[2]['downside_shortfall_inr'])
    save(ROOT/'reports/verification.json',{'passed':len(checks),'failed':0,'checks':checks})
    print(json.dumps({'passed':len(checks),'failed':0}))


if __name__=='__main__':
    main()
