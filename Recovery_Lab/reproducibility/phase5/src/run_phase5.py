"""Build fictional lending demonstrations and a retrospective Phase 4 risk bridge."""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
from engine import simulate,recovery_risk,schedule


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def readlines(p):return [json.loads(x) for x in Path(p).read_text().splitlines() if x]


def examples():
    base={'request_id':'DEMO-BASE','asset_reference_cost_inr':100000,'verified_monthly_income_inr':30000,
          'existing_monthly_obligations_inr':5000,'income_verified':True,'obligations_verified':True,
          'recovery_cost_inr':3000,'recovery_delay_months':0,'value_path_kind':'explicit_assumptions',
          'assumption_source':'Fictional hand-authored demonstration. Income verification flags are assumed for this fixture, not real customer verification.',
          'downside_value_path':[{'month':m,'value_inr':v} for m,v in [(0,70000),(6,63000),(12,56000),(18,50000),(24,44000),(30,39000),(36,35000)]]}
    low=deepcopy(base);low.update(request_id='DEMO-LOW-INCOME',verified_monthly_income_inr=15000)
    missing=deepcopy(base);missing.update(request_id='DEMO-MISSING-OBLIGATIONS',existing_monthly_obligations_inr=None)
    weak=deepcopy(base);weak['request_id']='DEMO-LOW-RECOVERY'
    for x in weak['downside_value_path']:x['value_inr']*=.5
    unsupported=deepcopy(base);unsupported.update(request_id='DEMO-MISSING-PATH',downside_value_path=[{'month':0,'value_inr':70000}])
    delay=deepcopy(base);delay.update(request_id='DEMO-TWO-MONTH-DELAY',recovery_delay_months=2)
    # Explicit values for the delayed sale checkpoints; this does not estimate depreciation.
    for x in delay['downside_value_path']:x['month']+=2
    return {'base':base,'low_income':low,'missing_obligations':missing,'low_recovery':weak,'missing_path':unsupported,'recovery_delay':delay}


def run(p1,p4,out):
    for folder in ['examples','results','reports']:(out/folder).mkdir(parents=True,exist_ok=True)
    policy_path=out/'configs/demo_policy.json';policy=json.loads(policy_path.read_text())
    phase1_manifest=json.loads((p1/'manifest.json').read_text())
    phase4_index=json.loads((p4/'package_index.json').read_text())
    source=p1/'data/canonical_records.jsonl';pred_path=p4/'data/calibration_predictions.jsonl'
    assert sha(source)==phase1_manifest['files']['data/canonical_records.jsonl']
    assert sha(pred_path)==phase4_index['files']['data/calibration_predictions.jsonl']['sha256']
    lock={'policy_sha256':sha(policy_path),'phase1_data_sha256':sha(source),'phase4_predictions_sha256':sha(pred_path),
          'source_code_sha256':{n:sha(out/'src'/n) for n in ['engine.py','run_phase5.py']},
          'created_utc':datetime.now(timezone.utc).isoformat(),'source_model_or_calibration_changed':False}
    if (out/'policy_lock.json').exists():
        old=json.loads((out/'policy_lock.json').read_text())
        for k in lock:
            if k!='created_utc' and lock[k]!=old[k]:raise ValueError('Frozen policy experiment changed: '+k)
    else:save(out/'policy_lock.json',lock)
    results=[]
    for name,request in examples().items():
        save(out/f'examples/{name}.json',request)
        response=simulate(request,policy)
        save(out/f'results/{name}.json',response)
        rec=response['recommended_offer']
        results.append({'example':name,'status':response['status'],'candidate_count':response.get('candidate_count',0),
                        'feasible_count':response.get('feasible_candidate_count',0),
                        'recommended':None if rec is None else {k:rec[k] for k in ['principal_inr','ltv','tenure_months','annual_nominal_rate','emi_inr','foir','total_contractual_interest_inr']}})
    records={r['agreement_id']:r for r in readlines(source)}
    preds=readlines(pred_path)
    risk_rows=[]
    for p in preds:
        r=records[p['agreement_id']]
        risk=recovery_risk(r['outstanding_balance_at_liquidation'],p['calibrated_lower'],p['median'],policy['retrospective_recovery_cost_assumption_inr'])
        risk_rows.append({'agreement_id':p['agreement_id'],'source_role':'operational.calibration',
                          'exposure_basis':'Recorded liquidation balance, not exposure known at seizure',
                          'value_basis':'Post-fit calibrated estimate on calibration fitting sample',
                          'recovery_cost_basis':'Illustrative fixed cost, not observed',
                          'recovery_cost_assumption_inr':policy['retrospective_recovery_cost_assumption_inr'],**risk})
    (out/'results/retrospective_recovery_risk.jsonl').write_text(''.join(json.dumps(r,allow_nan=False)+'\n' for r in risk_rows),encoding='utf-8')
    # Score integration only; this is not portfolio simulation or a business-impact estimate.
    summary={'phase':5,'demo_results':results,'retrospective_risk_rows':len(risk_rows),
             'retrospective_score_band_counts':dict(Counter(r['risk_band'] for r in risk_rows)),
             'risk_outputs_are_calculations_not_accuracy_results':True,
             'lending_examples_use_fictional_inputs':True,'actual_borrower_approvals':0,
             'model_retrained':False,'final_test_scored':False}
    save(out/'reports/summary.json',summary)
    report=['# Phase 5: exposure, risk scoring and lending policy','','This phase implements a runnable financial calculation and candidate-search engine. The lending examples use explicit fictional assumptions. Rates and policy limits are demonstration settings, not TVS Credit policy or validated optimum lending terms.','',
            '## Implemented capabilities','','- Cent-rounded amortization schedules with exact principal reconciliation and a final-instalment adjustment.',
            '- Scheduled outstanding principal after each successful payment, including month zero.',
            '- Net recovery, median/downside shortfall and a 0-100 downside severity score.',
            '- Enumeration of 35 LTV/tenure combinations under a fixed illustrative rate schedule.',
            '- Affordability checks using explicitly verified monthly income and obligations.',
            '- Collateral constraints at pre-maturity checkpoints, with explicit recovery-delay handling.',
            '- Deterministic ranking and feasible, no-feasible-offer, or review-required outcomes.',
            '- Constraint reasons, hashes and full candidate output for audit.',
            '- Integration of the risk formula with the 583 existing calibration-sample estimates; no model inference or training required.','',
            '## Demonstration outcomes','','| Example | Result | Feasible candidates | Principal INR | LTV | Tenure months | Annual nominal rate | EMI INR |','|---|---|---:|---:|---:|---:|---:|---:|']
    for r in results:
        v=r['recommended']
        report.append(f'| {r["example"]} | {r["status"]} | {r["feasible_count"]} | '+('— | — | — | — | — |' if v is None else f'{v["principal_inr"]:,.0f} | {v["ltv"]:.0%} | {v["tenure_months"]} | {v["annual_nominal_rate"]:.0%} | {v["emi_inr"]:,.2f} |'))
    report+=['','The base fixture assumes original cost INR 100,000, monthly income INR 30,000, existing obligations INR 5,000 and recovery expenses INR 3,000. Its downside value path is hand-authored, not predicted. The verified flags are part of the fictional fixture, not a claim of actual customer verification.','',
             '## Policy and ranking','','LTV grid: 60%, 65%, 70%, 75%, 80%, 85%, 90%. Tenures: 12, 18, 24, 30, 36 months. Base annual nominal rate: 18%; policy premiums: 2 points up to 70% LTV, 3 up to 80%, 5 up to 90%. These rates are assumptions and are not derived from the workbook\'s net IRR.',
             'Maximum FOIR: 40%. Maximum downside shortfall ratio: 20%. Checks occur at months 0, 6, 12, 18, 24, 30 and 36 where applicable, plus maturity. Month zero explicitly checks initial principal exposure. Maturity with zero exposure does not require a collateral value.',
             'Feasible candidates are ranked by highest principal, then lowest total contractual interest, then shortest tenure. This objective is not profit maximization. Thresholds use exact arithmetic before rounding the displayed risk score.','',
             '## Financial conventions','','Money uses Decimal arithmetic and rounding to INR 0.01. Interest accrues monthly on remaining principal and is rounded monthly. Regular EMI is calculated from the nominal annual rate divided by 12; the last payment adjusts for accumulated cent rounding. Maximum scheduled instalment is used in FOIR, including the final adjustment.',
             'Exposure at default month t is the scheduled remaining principal after t successful payments. It is frozen during the assumed recovery delay: no later payments, extra default interest or unknown arrears are fabricated. The downside sale value is looked up at t plus delay. No interpolation or extrapolation is performed in Phase 5.',
             'A missing required future checkpoint rejects the affected candidate. Missing monthly obligations or verification produces review_required, rather than an affordability pass. Malformed or negative numeric values raise an input error.','',
             '## Risk score definition','','Net downside recovery = max(0, lower value - explicit recovery cost). Downside shortfall = max(0, exposure - net downside recovery). For positive exposure the score is round-half-up(100 * downside shortfall / exposure). Bands: 0-25 Low, 26-50 Medium, 51-75 High, 76-100 Critical. Zero exposure returns no score and no band.',
             'This is shortfall severity under assumptions, not probability of default or loss. A central calibrated lower interval bound is not automatically a guaranteed 90% one-sided floor. Future assumed paths do not inherit Phase 4 interval coverage.','',
             '## Link to the supplied data','',
             f'The risk formula was applied to {len(risk_rows):,} saved Phase 4 calibration estimates, using each original recorded liquidation balance and an explicit INR 3,000 assumed recovery cost. These are post-fit, retrospective calculations. They are not live historical decisions, independent model validation, economic LGD or evidence of policy uplift.',
             'Actual lending recommendations were not generated for these borrowers: the workbook lacks verified monthly income frequency, existing obligations and future collateral paths. All six lending demonstrations use separate labelled fixtures. The original dataset and frozen models remain unchanged; final-test outcomes remain unscored.','',
             '## Phase 6 handoff','','The lending engine consumes a downside_value_path and an explicit source label. Phase 6 can supply conditional future-value paths and stress scenarios through this interface. Add scenario evidence without silently upgrading assumed values into validated forecasts. The API/dashboard phases can call the same engine directly; no financial logic should be duplicated in the UI.',
             'The saved candidate lists, selected payment schedule and per-checkpoint rejection reasons support explainable demonstrations. No loan is automatically approved and no recommendation has been transmitted to an external system.','',
             '## Verification','','verification.json records independent amortization examples, principal reconciliation, rounding and boundary checks, monotonic-risk tests, all feasible-candidate constraint checks and source hashes. These are software tests, not production underwriting validation.']
    (out/'reports/Phase_5_Report.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for x in ['phase1','phase4','output']:p.add_argument('--'+x,type=Path,required=True)
    a=p.parse_args();run(a.phase1,a.phase4,a.output)
