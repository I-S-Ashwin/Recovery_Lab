"""Independent numerical, policy and data-provenance verification for Phase 5."""
import argparse
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
from engine import schedule,recovery_risk,simulate,validate_policy


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def D(x):return Decimal(str(x))


def verify(p1,p4,out):
    results=[]
    def check(name,condition):
        if not condition:raise AssertionError(name)
        results.append({'check':name,'result':'passed'})
    def rejects(name,fn):
        try:fn()
        except ValueError:check(name,True)
        else:check(name,False)
    lock=json.loads((out/'policy_lock.json').read_text());policy=json.loads((out/'configs/demo_policy.json').read_text())
    check('Phase 1 data unchanged',sha(p1/'data/canonical_records.jsonl')==lock['phase1_data_sha256'])
    check('Phase 4 predictions unchanged',sha(p4/'data/calibration_predictions.jsonl')==lock['phase4_predictions_sha256'])
    check('Policy fixed and versioned',sha(out/'configs/demo_policy.json')==lock['policy_sha256'])
    for n,h in lock['source_code_sha256'].items():check('Code hash '+n,sha(out/'src'/n)==h)
    z=schedule(1000,0,3)
    check('Zero-interest exact final adjustment',[x['payment'] for x in z['rows'][1:]]==[333.33,333.33,333.34])
    check('Zero-interest total payments',z['total_payments']==1000 and z['total_interest']==0)
    one=schedule(1000,.12,1)
    check('One-month independent interest example',one['regular_emi']==1010 and one['total_interest']==10 and one['rows'][-1]['balance']==0)
    # Numerical bisection of a separate unrounded cash-flow recurrence, not the EMI formula.
    for principal,rate,months in [(12000,.12,12),(80000,.21,18),(100000,.23,36)]:
        low=0.;high=principal*(1+rate/12)
        for _ in range(90):
            guess=(low+high)/2;balance=float(principal)
            for _ in range(months):balance=balance*(1+rate/12)-guess
            if balance>0:low=guess
            else:high=guess
        payment=(low+high)/2;s=schedule(principal,rate,months)
        check(f'EMI matches numerical cash-flow root {months} months',abs(s['regular_emi']-payment)<=.005001)
        check(f'Principal reconciles to cents {months} months',sum(D(x['principal_paid']) for x in s['rows'])==D(principal))
        check(f'Payments reconcile {months} months',sum(D(x['payment']) for x in s['rows'])==D(principal)+D(s['total_interest']))
        check(f'Balances nonnegative and ending zero {months} months',all(x['balance']>=0 for x in s['rows']) and s['rows'][-1]['balance']==0)
    rejects('Reject negative principal',lambda:schedule(-1,.2,12))
    rejects('Reject percent rate mistakenly supplied as 21',lambda:schedule(1000,21,12))
    rejects('Reject zero tenure',lambda:schedule(1000,.2,0))
    rejects('Reject fractional tenure',lambda:schedule(1000,.2,12.5))
    rejects('Reject NaN principal',lambda:schedule(float('nan'),.2,12))
    risk=recovery_risk(100000,60000,75000,5000)
    check('Independent recovery shortfall example',risk['downside_net_recovery_inr']==55000 and risk['downside_shortfall_inr']==45000 and risk['median_shortfall_inr']==30000)
    check('Risk score and band example',risk['policy_risk_score']==45 and risk['risk_band']=='Medium')
    zero=recovery_risk(0,100,200,10)
    check('Zero exposure has no score',zero['policy_risk_score'] is None and zero['risk_band'] is None and zero['downside_shortfall_inr']==0)
    for lower,score,band in [(75,25,'Low'),(74.5,26,'Medium'),(50,50,'Medium'),(49.5,51,'High'),(25,75,'High'),(24.5,76,'Critical'),(0,100,'Critical')]:
        r=recovery_risk(100,lower,100,0)
        check(f'Half-up risk band boundary {lower}',r['policy_risk_score']==score and r['risk_band']==band)
    check('Recovery costs cannot make negative net recovery',recovery_risk(100,20,30,1000)['downside_net_recovery_inr']==0)
    check('Higher costs do not reduce risk',recovery_risk(100,60,70,20)['downside_shortfall_inr']>=recovery_risk(100,60,70,10)['downside_shortfall_inr'])
    check('Lower proceeds do not reduce risk',recovery_risk(100,50,70,10)['downside_shortfall_inr']>=recovery_risk(100,60,70,10)['downside_shortfall_inr'])
    rejects('Missing recovery cost not silently zero',lambda:recovery_risk(100,50,60,None))
    rejects('Crossed valuation inputs rejected',lambda:recovery_risk(100,70,60,0))
    base=json.loads((out/'examples/base.json').read_text())
    response=simulate(base,policy)
    check('Exactly 35 unique candidates',len(response['candidates'])==35 and len({x['candidate_id'] for x in response['candidates']})==35)
    check('Base example selects declared expected offer',response['recommended_offer']['principal_inr']==80000 and response['recommended_offer']['tenure_months']==18)
    check('Base pricing components match nominal rate',response['recommended_offer']['annual_nominal_rate']==.21 and response['recommended_offer']['annual_policy_premium']==.03)
    all_constraints=True;all_reasons=True;all_checkpoints=True;all_grid=True
    for c in response['candidates']:
        all_grid &= c['ltv'] in policy['ltv_candidates'] and c['tenure_months'] in policy['tenure_candidates_months']
        all_reasons &= c['feasible']==(len(c['constraint_failures'])==0)
        sc=schedule(c['principal_inr'],c['annual_nominal_rate'],c['tenure_months'])
        if c['feasible']:
            all_constraints &= (D(base['existing_monthly_obligations_inr'])+max(D(x['payment']) for x in sc['rows']))/D(base['verified_monthly_income_inr'])<=D(policy['maximum_foir'])
        for cp in c['checkpoints']:
            all_checkpoints &= cp['scheduled_principal_inr']==sc['rows'][cp['default_month']]['balance']
            if cp['status']=='evaluated' and c['feasible']:
                exposure=D(cp['scheduled_principal_inr'])
                low=next(D(x['value_inr']) for x in base['downside_value_path'] if x['month']==cp['sale_month'])
                net=max(D(0),low-D(base['recovery_cost_inr']))
                all_constraints &= max(D(0),exposure-net)/exposure<=D(policy['maximum_downside_shortfall_ratio'])
    check('Every candidate belongs to configured grid',all_grid)
    check('Every feasibility flag agrees with reasons',all_reasons)
    check('Every checkpoint reconciles to schedule',all_checkpoints)
    check('Every feasible offer satisfies independent affordability and downside checks',all_constraints)
    feasible=[c for c in response['candidates'] if c['feasible']]
    reference=min(feasible,key=lambda x:(-x['principal_inr'],x['total_contractual_interest_inr'],x['tenure_months']))
    check('Winner follows explicit ranking',reference['candidate_id']==response['recommended_offer']['candidate_id'])
    check('Initial exposure evaluated before maturity',all(any(x['default_month']==0 and x['status']=='evaluated' for x in c['checkpoints']) for c in response['candidates']))
    check('High LTV not falsely safe because maturity balance is zero',all('downside_limit_month_0' in c['constraint_failures'] for c in response['candidates'] if c['ltv']>.8))
    for name,expected in [('low_income','no_feasible_offer'),('missing_obligations','review_required'),('low_recovery','no_feasible_offer'),('missing_path','no_feasible_offer'),('recovery_delay','feasible_offer')]:
        request=json.loads((out/f'examples/{name}.json').read_text());res=simulate(request,policy)
        check(name+' expected handling',res['status']==expected)
        check(name+' reproduces saved result',res==json.loads((out/f'results/{name}.json').read_text()))
    unverified=deepcopy(base);unverified['income_verified']=False
    check('Unverified income never passes affordability',simulate(unverified,policy)['status']=='review_required')
    invalid=deepcopy(base);invalid['existing_monthly_obligations_inr']=-1
    rejects('Negative obligations rejected',lambda:simulate(invalid,policy))
    invalid=deepcopy(base);invalid['downside_value_path'].append(invalid['downside_value_path'][0])
    rejects('Duplicate path months rejected',lambda:simulate(invalid,policy))
    unknown=deepcopy(base);unknown['value_path_kind']='guaranteed_forecast'
    rejects('Unsupported future coverage claim rejected',lambda:simulate(unknown,policy))
    fixed=deepcopy(policy);fixed['ltv_candidates']=[.8];fixed['tenure_candidates_months']=[12]
    boundary=deepcopy(base);boundary['verified_monthly_income_inr']=100000;boundary['existing_monthly_obligations_inr']=0;boundary['recovery_cost_inr']=0
    boundary['downside_value_path']=[{'month':0,'value_inr':64000},{'month':6,'value_inr':64000}]
    check('Exact 20 percent downside threshold accepted',simulate(boundary,fixed)['status']=='feasible_offer')
    boundary['downside_value_path'][0]['value_inr']=63999.99
    check('Tiny threshold excess rejected before score rounding',simulate(boundary,fixed)['status']=='no_feasible_offer')
    delayed=json.loads((out/'results/recovery_delay.json').read_text())
    check('Delay shifts sale lookup and freezes principal',all(x['sale_month']==x['default_month']+2 for c in delayed['candidates'] for x in c['checkpoints']))
    check('Equal delayed path assumptions preserve financial decision',delayed['recommended_offer']['principal_inr']==response['recommended_offer']['principal_inr'])
    # A concrete earlier-default case: principal is not reduced by payments during delay.
    dc=next(c for c in delayed['candidates'] if c['ltv']==.8 and c['tenure_months']==18)
    cp=next(x for x in dc['checkpoints'] if x['default_month']==6)
    ss=schedule(80000,.21,18)
    check('Default month 6 with delay does not use month 8 balance',cp['scheduled_principal_inr']==ss['rows'][6]['balance'] and cp['scheduled_principal_inr']!=ss['rows'][8]['balance'])
    badpolicy=deepcopy(policy);badpolicy['ltv_candidates']=[80]
    rejects('LTV percentage unit mistake rejected',lambda:simulate(base,badpolicy))
    badpolicy=deepcopy(policy);badpolicy['ltv_premium_schedule']=[]
    rejects('Unpriced grid rejected',lambda:simulate(base,badpolicy))
    rows=[json.loads(s) for s in (out/'results/retrospective_recovery_risk.jsonl').read_text().splitlines()]
    calibration={json.loads(s)['agreement_id']:json.loads(s) for s in (p4/'data/calibration_predictions.jsonl').read_text().splitlines()}
    source={json.loads(s)['agreement_id']:json.loads(s) for s in (p1/'data/canonical_records.jsonl').read_text().splitlines()}
    check('Risk bridge uses exactly the 583 consumed calibration cases',len(rows)==583 and {x['agreement_id'] for x in rows}==set(calibration))
    all_risk=True
    for r in rows:
        p=calibration[r['agreement_id']];s=source[r['agreement_id']]
        expected=recovery_risk(s['outstanding_balance_at_liquidation'],p['calibrated_lower'],p['median'],3000)
        all_risk &= all(r[k]==v for k,v in expected.items())
    check('All retrospective risk rows reproduce source-linked arithmetic',all_risk)
    check('No actual approval in any candidate response',response['automatic_approval'] is False)
    check('Phase 4 predictions still unchanged',sha(p4/'data/calibration_predictions.jsonl')==lock['phase4_predictions_sha256'])
    output={'status':'passed','check_count':len(results),'checks':results,'actual_borrower_approvals':0,'final_test_scored':False}
    (out/'reports/verification.json').write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in output.items() if k!='checks'},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for x in ['phase1','phase4','output']:p.add_argument('--'+x,type=Path,required=True)
    a=p.parse_args();verify(a.phase1,a.phase4,a.output)
