"""Run with Python 3.10+; standard library only; outputs relative to this package."""
import hashlib
import json
from pathlib import Path
from frozen_policy import schedule, simulate, recovery_risk
from projection import project, stress_asset, aggregate

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    config = read(ROOT/'configs/scenarios.json')
    policy = read(ROOT/'configs/demo_policy.json')
    anchors = config['factor_anchors']
    assets = []
    for name, cost, lower, median, principal, term, income, obligations in [
        ('DEMO-A',100000,70000,85000,80000,36,30000,5000),
        ('DEMO-B',80000,52000,65000,65000,24,25000,4000),
        ('DEMO-C',140000,90000,110000,120000,36,40000,7000)]:
        assets.append(dict(asset_id=name, valuation_date='2026-09-06',
                           asset_reference_cost_inr=cost, downside_anchor_inr=lower,
                           median_anchor_inr=median, existing_principal_inr=principal,
                           remaining_term_months=term, annual_nominal_rate=0.21,
                           verified_monthly_income_inr=income, existing_monthly_obligations_inr=obligations,
                           evidence_type='Fictional fixture; all verification flags assumed'))
    save(ROOT/'examples/fictional_portfolio.json', assets)
    projections = []
    fixed_book = []
    offers = []
    for scenario in config['scenarios']:
        for horizon in [0,12,24,36]:
            rows=[]
            for asset in assets:
                sched=schedule(asset['existing_principal_inr'], asset['annual_nominal_rate'],asset['remaining_term_months'])
                exposure=sched['rows'][min(horizon,asset['remaining_term_months'])]['balance']
                rows.append(stress_asset(asset,exposure,horizon,scenario,anchors))
            fixed_book.append({'scenario':scenario['name'],'default_month':horizon,
                               'scope':'Fictional fixed book; all loans default at checkpoint after scheduled payments',
                               **aggregate(rows),'assets':rows})
        for asset in assets:
            values=[project(asset,m,scenario,anchors) for m in range(43)]
            projections.append({'asset_id':asset['asset_id'],'scenario':scenario['name'],'monthly_values':values})
            request={k:asset[k] for k in ['asset_reference_cost_inr','verified_monthly_income_inr','existing_monthly_obligations_inr']}
            request.update(request_id=asset['asset_id']+'-'+scenario['name'],income_verified=True,
                           obligations_verified=True,recovery_cost_inr=scenario['recovery_cost_inr'],
                           recovery_delay_months=scenario['recovery_delay_months'],value_path_kind='explicit_assumptions',
                           assumption_source='Fictional portfolio and phase6-demo-v1 factors; verification flags assumed',
                           downside_value_path=[{'month':x['month'],'value_inr':x['downside_value_inr']} for x in values])
            save(ROOT/f'examples/{request["request_id"]}.json',request)
            result=simulate(request,policy)
            save(ROOT/f'results/offers/{request["request_id"]}.json',result)
            offers.append({'asset_id':asset['asset_id'],'scenario':scenario['name'],'status':result['status'],
                           'feasible_candidates':result.get('feasible_candidate_count',0),
                           'recommended_offer':result['recommended_offer']})
    save(ROOT/'results/monthly_projections.json',projections)
    save(ROOT/'results/fixed_book_stress.json',fixed_book)
    save(ROOT/'results/new_offer_summary.json',offers)
    # Historical cohort: direct price-only snapshot stress. No arbitrary common as-of date.
    source=OUT/'phase5/results/retrospective_recovery_risk.jsonl'
    preds_path=OUT/'phase4/data/calibration_predictions.jsonl'
    previous=[json.loads(x) for x in source.read_text().splitlines()]
    preds={x['agreement_id']:x for x in map(json.loads,preds_path.read_text().splitlines())}
    history=[]
    for scenario in config['scenarios']:
        rows=[]
        for old in previous:
            pred=preds[old['agreement_id']]
            from decimal import Decimal
            multiplier=Decimal(str(scenario['market_multiplier']))
            risk=recovery_risk(old['exposure_inr'],Decimal(str(pred['calibrated_lower']))*multiplier,
                               Decimal(str(pred['median']))*multiplier,3000)
            rows.append({'agreement_id':old['agreement_id'],**risk})
        history.append({'scenario':scenario['name'],'market_multiplier':scenario['market_multiplier'],
                        'cost_inr_per_asset':3000,'delay_applied':False,
                        'scope':'583 historical calibration fitting cases at their respective liquidation snapshots; price-only stress',
                        **aggregate(rows),'assets':rows})
    save(ROOT/'results/historical_price_stress.json',history)
    locked=[source,preds_path,OUT/'phase5/src/engine.py',OUT/'phase1/data/canonical_records.jsonl']
    save(ROOT/'source_lock.json',{'source_files':{str(p.relative_to(OUT)).replace('\\','/'):digest(p) for p in locked},
                                  'final_test_used':False,'training_performed':False})
    lines=['# Phase 6 — future value assumptions and portfolio stress','',
           'This phase implements reproducible scenario calculations, not validated 12/24/36-month forecasts. The original workbook remains unchanged. The 583-case historical bridge uses saved Phase 4 estimates and Phase 5 liquidation exposures from that workbook; three separate fictional assets demonstrate future lending decisions. No final-test outcomes were used.', '',
           '## Method and boundaries','',
           'Projected gross value = reference value × elapsed-month depreciation factor × common market multiplier. Elapsed months start at the supplied valuation date; they are not manufacture age. Factors are linearly interpolated through month 42, and later requests fail explicitly. Anchors are 1.00 at month 0, 0.80 at 12, 0.65 at 24, 0.50 at 36 and 0.45 at 42. These are demonstration assumptions, not fitted depreciation rates.', '',
           'Base/adverse/severe market multipliers are 1.00/0.90/0.80; fictional-book recovery costs are ₹3,000/₹4,000/₹6,000 and delays 0/1/3 months. A common shock applies to every asset. There are no estimated probabilities for these scenarios. The scenario spread is not a confidence interval; Phase 4 conformal coverage does not extend to these future values.', '',
           '## Example projected values: fictional asset A','',
           '| Scenario | Month 12 downside / median | Month 24 downside / median | Month 36 downside / median |',
           '|---|---:|---:|---:|']
    for scenario in config['scenarios']:
        v=[project(assets[0],m,scenario,anchors) for m in [12,24,36]]
        lines.append('| '+scenario['name']+' | '+' | '.join(f"₹{x['downside_value_inr']:,.0f} / ₹{x['median_value_inr']:,.0f}" for x in v)+' |')
    lines+=['','## Fixed fictional book stress','',
            'The same existing loans are held fixed in every scenario. At each checkpoint, all assets are assumed to default after the scheduled payments; balances freeze until recovery. No default interest, missed-payment arrears or extra payments during recovery are assumed. This measures conditional shortfall, not expected credit loss. Each checkpoint is a separate scenario and must not be summed across time.', '',
            '| Scenario | Default month | Exposure | Downside shortfall | Exposure-weighted ratio |','|---|---:|---:|---:|---:|']
    for x in fixed_book:
        ratio=x['exposure_weighted_shortfall_ratio']
        lines.append(f"| {x['scenario']} | {x['default_month']} | ₹{x['exposure_inr']:,.2f} | ₹{x['downside_shortfall_inr']:,.2f} | {format(ratio,'.2%') if ratio is not None else 'N/A: no exposure'} |")
    lines+=['','Portfolio shortfall is the sum of each asset’s positive shortfall divided by total exposure. Surplus collateral on one loan cannot offset another loan’s deficit. Summed downside values are not a calibrated portfolio quantile.', '',
            '## New offers under the same scenarios','',
            'These are separate hypothetical new applications, not modifications to the existing book. The Phase 5 engine is reused unchanged. Verification flags and income are fictional. No real application is approved.', '',
            '| Asset | Scenario | Feasible candidates | Recommended principal | Term |','|---|---|---:|---:|---:|']
    for x in offers:
        offer=x['recommended_offer']
        lines.append(f"| {x['asset_id']} | {x['scenario']} | {x['feasible_candidates']} | "+(f"₹{offer['principal_inr']:,.0f} | {offer['tenure_months']} months |" if offer else 'No feasible offer | — |'))
    lines+=['','## Original-data historical price sensitivity','',
            'This is a descriptive stress of 583 sold calibration cases at different historical liquidation dates, not a current live portfolio. Estimates were calibrated on these cases; this is not independent validation. Costs stay fixed at ₹3,000 and no delay or future depreciation is applied here, to isolate price sensitivity. Recorded balances were known at liquidation, not necessarily at seizure.', '',
            '| Price scenario | Recorded exposure | Downside shortfall | Weighted ratio |','|---|---:|---:|---:|']
    for x in history:
        lines.append(f"| {x['scenario']} | ₹{x['exposure_inr']:,.2f} | ₹{x['downside_shortfall_inr']:,.2f} | {x['exposure_weighted_shortfall_ratio']:.2%} |")
    lines+=['','## Reproduce and production handoff','',
            'Requires Python 3.10+ with no third-party packages. Keep phase1, phase4, phase5 and phase6 as sibling folders to regenerate the original-data bridge. From the phase6 folder run `python src/run_phase6.py`, then `python src/verify.py`. Projection and financial modules run standalone with the bundled configuration. Source hashes are recorded in source_lock.json; package_index.json identifies delivered files.', '',
            'Before production: obtain longitudinal valuations with explicit asset age and observation dates; include unsold and performing populations; validate horizons on later untouched cohorts; confirm recovery expenses, delay distributions and repayment behavior; replace demonstration policy with approved rules; require verified income and obligations; and add authenticated API access, monitoring and audit retention. This phase is a tested POC component, not a production-approved credit decision system.', '',
            'Next: Phase 7 API and dashboard. The frozen final evaluation remains reserved for Phase 9.']
    (ROOT/'reports').mkdir(exist_ok=True)
    (ROOT/'reports/Phase_6_Report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    save(ROOT/'reports/summary.json',{'phase':6,'fictional_assets':3,'historical_cases':len(previous),
         'scenarios':3,'monthly_projection_rows':len(projections)*43,'offer_simulations':len(offers),
         'fixed_book_scenarios':len(fixed_book),'final_test_used':False,'future_forecasts_validated':False})


if __name__=='__main__':
    main()

