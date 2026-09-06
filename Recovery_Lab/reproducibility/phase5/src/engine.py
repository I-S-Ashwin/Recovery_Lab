"""Deterministic POC finance and policy engine; standard-library dependencies only."""
from collections import Counter
from decimal import Decimal,InvalidOperation,ROUND_HALF_UP,localcontext
import hashlib
import json

CENT=Decimal('0.01')


def decimal(value,name):
    if value is None or isinstance(value,bool):raise ValueError(name+' must be a finite number')
    try:d=Decimal(str(value))
    except (InvalidOperation,ValueError):raise ValueError(name+' must be numeric')
    if not d.is_finite():raise ValueError(name+' must be finite')
    return d


def nonnegative(value,name):
    d=decimal(value,name)
    if d<0:raise ValueError(name+' cannot be negative')
    return d


def money(value):return value.quantize(CENT,rounding=ROUND_HALF_UP)
def f(value):return float(value)
def fingerprint(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def schedule(principal,annual_rate,months):
    p=money(nonnegative(principal,'principal'));r=nonnegative(annual_rate,'annual_rate')
    if p<=0:raise ValueError('principal must be positive after cent rounding')
    if r>1:raise ValueError('annual_rate must be a fraction between 0 and 1 in this engine')
    if isinstance(months,bool) or not isinstance(months,int) or not 1<=months<=600:
        raise ValueError('months must be an integer from 1 to 600')
    with localcontext() as context:
        context.prec=50
        monthly=r/12
        denominator=(1+monthly)**months-1
        payment=money(p/months if monthly==0 or denominator==0 else p*monthly*(1+monthly)**months/denominator)
        balance=p;rows=[{'month':0,'payment':0.0,'interest':0.0,'principal_paid':0.0,'balance':f(p)}]
        total_interest=Decimal(0);total_payment=Decimal(0)
        for month in range(1,months+1):
            interest=money(balance*monthly)
            actual_payment=balance+interest if month==months else min(payment,balance+interest)
            principal_paid=actual_payment-interest
            if principal_paid<0:raise ValueError('Rounded EMI would not amortize principal')
            balance=money(balance-principal_paid)
            total_interest+=interest;total_payment+=actual_payment
            rows.append({'month':month,'payment':f(actual_payment),'interest':f(interest),
                         'principal_paid':f(principal_paid),'balance':f(balance)})
        if balance!=0:raise AssertionError('Ending principal did not reconcile')
        return {'principal':f(p),'annual_nominal_rate':f(r),'tenure_months':months,'regular_emi':f(payment),
                'maximum_instalment':max(x['payment'] for x in rows),'total_interest':f(total_interest),
                'total_payments':f(total_payment),'rows':rows}


def recovery_risk(exposure,lower_value,median_value,recovery_cost):
    e=money(nonnegative(exposure,'exposure'));lo=money(nonnegative(lower_value,'lower_value'))
    med=money(nonnegative(median_value,'median_value'));cost=money(nonnegative(recovery_cost,'recovery_cost'))
    if lo>med:raise ValueError('lower_value cannot exceed median_value')
    net_low=max(Decimal(0),lo-cost);net_med=max(Decimal(0),med-cost)
    low_loss=max(Decimal(0),e-net_low);med_loss=max(Decimal(0),e-net_med)
    ratio=low_loss/e if e>0 else None
    score=int((ratio*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP)) if ratio is not None else None
    band=None if score is None else next(b for maximum,b in [(25,'Low'),(50,'Medium'),(75,'High'),(100,'Critical')] if score<=maximum)
    return {'exposure_inr':f(e),'downside_net_recovery_inr':f(net_low),'median_net_recovery_inr':f(net_med),
            'downside_shortfall_inr':f(low_loss),'median_shortfall_inr':f(med_loss),
            'downside_shortfall_ratio':f(ratio) if ratio is not None else None,'policy_risk_score':score,'risk_band':band,
            'risk_definition':'Downside shortfall severity under inputs, not probability of default or loss'}


def validate_policy(p):
    if p.get('currency')!='INR':raise ValueError('Only INR policy supported')
    ltvs=p['ltv_candidates'];terms=p['tenure_candidates_months'];checks=p['exposure_checkpoints_months']
    if not ltvs or len(set(ltvs))!=len(ltvs):raise ValueError('LTV grid must be nonempty and unique')
    for v in ltvs:
        if not 0<decimal(v,'LTV')<=1:raise ValueError('LTV must be a fraction in (0,1]')
    if not terms or len(set(terms))!=len(terms) or any(isinstance(v,bool) or not isinstance(v,int) or v<=0 or v>600 for v in terms):raise ValueError('Invalid tenure grid')
    if not checks or 0 not in checks or len(set(checks))!=len(checks) or any(isinstance(v,bool) or not isinstance(v,int) or v<0 for v in checks):raise ValueError('Invalid checkpoint grid; month zero required')
    for key in ['maximum_foir','maximum_downside_shortfall_ratio']:
        if not 0<=decimal(p[key],key)<=1:raise ValueError(key+' must be in [0,1]')
    previous=Decimal(0)
    for tier in p['ltv_premium_schedule']:
        bound=decimal(tier['maximum_ltv'],'maximum_ltv')
        if not previous<bound<=1:raise ValueError('Rate tiers must increase within (0,1]')
        premium=nonnegative(tier['annual_premium'],'premium')
        base=nonnegative(p['nominal_annual_base_rate'],'base rate')
        if base+premium>1:raise ValueError('Rate exceeds supported fraction range')
        previous=bound
    if previous<max(decimal(v,'LTV') for v in ltvs):raise ValueError('Rate tiers do not cover candidate LTVs')


def simulate(request,policy):
    validate_policy(policy)
    result={'request_id':request.get('request_id'),'policy_id':policy['policy_id'],'policy_sha256':fingerprint(policy),
            'request_sha256':fingerprint(request),'evidence_type':'policy_simulation','automatic_approval':False,
            'policy_status':policy['policy_status'],'status':None,'reasons':[],'recommended_offer':None,'candidates':[]}
    required=['asset_reference_cost_inr','verified_monthly_income_inr','existing_monthly_obligations_inr',
              'recovery_cost_inr','recovery_delay_months','downside_value_path','value_path_kind','assumption_source']
    missing=[k for k in required if request.get(k) is None]
    if missing:
        result.update(status='review_required',reasons=['Missing required input: '+k for k in missing]);return result
    if request.get('income_verified') is not True or request.get('obligations_verified') is not True:
        result.update(status='review_required',reasons=['Verified monthly income and existing obligations are required']);return result
    cost=money(nonnegative(request['asset_reference_cost_inr'],'asset_reference_cost_inr'))
    income=money(nonnegative(request['verified_monthly_income_inr'],'income'))
    obligations=money(nonnegative(request['existing_monthly_obligations_inr'],'obligations'))
    recovery_cost=money(nonnegative(request['recovery_cost_inr'],'recovery_cost'))
    if income<=0 or cost<=0:raise ValueError('Income and asset cost must be positive')
    delay=request['recovery_delay_months']
    if isinstance(delay,bool) or not isinstance(delay,int) or delay<0:raise ValueError('Recovery delay must be a nonnegative integer')
    if request['value_path_kind'] not in ['explicit_assumptions','conditional_projection']:raise ValueError('Future path must be labelled assumptions or conditional projection')
    if not isinstance(request['assumption_source'],str) or not request['assumption_source'].strip():raise ValueError('Assumption source required')
    path={}
    for point in request['downside_value_path']:
        t=point['month']
        if isinstance(t,bool) or not isinstance(t,int) or t<0 or t in path:raise ValueError('Value path months must be unique nonnegative integers')
        path[t]=money(nonnegative(point['value_inr'],'downside value'))
    if not path:
        result.update(status='review_required',reasons=['No future downside values supplied']);return result
    maxfoir=decimal(policy['maximum_foir'],'maximum_foir');maxloss=decimal(policy['maximum_downside_shortfall_ratio'],'maximum loss')
    for ltv_value in policy['ltv_candidates']:
        ltv=decimal(ltv_value,'ltv');principal=money(cost*ltv)
        tier=next(t for t in policy['ltv_premium_schedule'] if ltv<=decimal(t['maximum_ltv'],'maximum_ltv'))
        premium=decimal(tier['annual_premium'],'premium');base=decimal(policy['nominal_annual_base_rate'],'base rate');rate=base+premium
        for tenure in policy['tenure_candidates_months']:
            sched=schedule(principal,rate,tenure)
            # Maximum instalment includes final cent adjustment, so no payment silently breaches FOIR.
            foir=(obligations+decimal(sched['maximum_instalment'],'instalment'))/income
            reasons=[];exposures=[]
            if foir>maxfoir:reasons.append('affordability_limit')
            checkpoints=sorted({t for t in policy['exposure_checkpoints_months'] if t<=tenure}|{tenure})
            for month in checkpoints:
                balance=decimal(sched['rows'][month]['balance'],'balance')
                if balance==0:
                    exposures.append({'default_month':month,'sale_month':month+delay,'scheduled_principal_inr':0.0,'downside_shortfall_ratio':None,'status':'no_exposure'})
                    continue
                sale_month=month+delay
                if sale_month not in path:
                    reasons.append('missing_value_month_'+str(sale_month));continue
                risk=recovery_risk(balance,path[sale_month],path[sale_month],recovery_cost)
                # Approve using exact money arithmetic, not a rounded score or display percentage.
                net=max(Decimal(0),path[sale_month]-recovery_cost)
                exact_ratio=max(Decimal(0),balance-net)/balance
                if exact_ratio>maxloss:reasons.append('downside_limit_month_'+str(month))
                exposures.append({'default_month':month,'sale_month':sale_month,'scheduled_principal_inr':f(balance),
                                  'gross_downside_value_inr':f(path[sale_month]),'recovery_cost_inr':f(recovery_cost),**risk,'status':'evaluated'})
            candidate={'candidate_id':f'L{ltv*100:g}_T{tenure}','ltv':f(ltv),'principal_inr':f(principal),
                       'tenure_months':tenure,'base_annual_nominal_rate':f(base),'annual_policy_premium':f(premium),'annual_nominal_rate':f(rate),
                       'emi_inr':sched['regular_emi'],'maximum_instalment_inr':sched['maximum_instalment'],
                       'total_contractual_interest_inr':sched['total_interest'],'foir':f(foir),
                       'feasible':not reasons,'constraint_failures':sorted(set(reasons)),'checkpoints':exposures}
            result['candidates'].append(candidate)
    feasible=[c for c in result['candidates'] if c['feasible']]
    result['candidate_count']=len(result['candidates']);result['feasible_candidate_count']=len(feasible)
    result['rejection_reason_counts']=dict(Counter(reason for c in result['candidates'] for reason in c['constraint_failures']))
    result['assumptions']={'value_path_kind':request['value_path_kind'],'source':request['assumption_source'],
                           'recovery_cost_inr':f(recovery_cost),'recovery_delay_months':delay,
                           'future_value_coverage_guaranteed':False,'default_exposure_convention':policy['default_exposure_convention']}
    if not feasible:
        result.update(status='no_feasible_offer',reasons=['No candidate meets all supplied policy and value-support constraints']);return result
    winner=min(feasible,key=lambda c:(-c['principal_inr'],c['total_contractual_interest_inr'],c['tenure_months']))
    recommendation={k:v for k,v in winner.items() if k!='checkpoints'}
    recommendation['selection_reasons']=['Highest feasible principal in the configured grid','Lowest contractual interest among offers with that principal','Shorter tenure breaks remaining ties']
    recommendation['scheduled_payments']=schedule(winner['principal_inr'],winner['annual_nominal_rate'],winner['tenure_months'])['rows']
    result.update(status='feasible_offer',recommended_offer=recommendation)
    return result
