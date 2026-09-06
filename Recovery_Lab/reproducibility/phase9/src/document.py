"""Generate evidence reports and scientific plots from saved frozen results."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter, FuncFormatter
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT.parent
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(name,text):(ROOT/'reports'/name).write_text(text+'\n',encoding='utf-8')
def money(v):return f'₹{v:,.2f}'
def percent(v):return f'{v*100:.2f}%'
def main():
    result=read(ROOT/'reports/final_metrics.json');p=result['operational'];r=result['retrospective']
    segments=read(ROOT/'reports/operational_segments.json');fuel=[s for s in segments if s['field']=='asset_fuel_type']
    ev=next(s for s in fuel if s['value']=='EV');petrol=next(s for s in fuel if s['value']=='Petrol')
    lock=read(ROOT/'configs/evaluation_lock.json');verification=read(ROOT/'reports/verification.json')
    calib=read(ROOT/'models/calibration.json');contract=read(ROOT/'models/base_feature_contract.json')
    selected=read(OUT/'phase3/reports/summary.json');bootstrap=result['paired_mae_bootstrap']
    examples=read(ROOT/'reports/diagnostic_examples.json')
    rows=[json.loads(x) for x in (ROOT/'data/operational_final_predictions.jsonl').read_text().splitlines()]
    table=['| Metric | Frozen model | Frozen B0 baseline |','|---|---:|---:|']
    for key,label in [('mae_inr','MAE'),('rmse_inr','RMSE'),('median_absolute_error_inr','Median absolute error'),('mean_signed_error_inr','Mean signed error (prediction − sale)')]:
        table.append(f"| {label} | {money(p['model'][key])} | {money(p['baseline'][key])} |")
    for key,label in [('mape_percent','MAPE'),('wape_percent','WAPE')]:table.append(f"| {label} | {p['model'][key]:.2f}% | {p['baseline'][key]:.2f}% |")
    table.append(f"| R² | {p['model']['r2']:.4f} | {p['baseline']['r2']:.4f} |")
    summary_table='\n'.join(table)
    lines=['# Phase 9 — frozen final evaluation','',
      f"The frozen model reduces MAE by **{p['mae_reduction_percent']:.2f}%** against B0 on **1,244 reserved operational cases**: {money(p['model']['mae_inr'])} versus {money(p['baseline']['mae_inr'])}. The calibrated interval covers **{percent(p['calibrated_interval']['coverage'])}** of observed sales, with a mean width of **{money(p['calibrated_interval']['mean_width_inr'])}**.",'',
      f"**The pooled result hides weaker EV performance.** EV coverage is {percent(ev['calibrated_interval']['coverage'])} on {ev['n']} cases; its MAE gain over B0 is only {ev['mae_reduction_percent']:.2f}%. This release is not validated for a claim of 80% coverage in every segment.",'',
      '## Frozen protocol and provenance','',
      'The evaluation plan was written and hashed before test predictions were computed. Model weights, calibration correction, policy, split boundaries and feature definitions were not changed. All cases in the two locked final-test cohorts were retained, including unsupported inputs and large errors. Phase 1 had profiled the full file, so this is a model-development holdout, not an unseen external dataset. After this evaluation, these outcomes must not be reused as a fresh holdout for future tuning.','',
      '| Role | Records | Availability rule |','|---|---:|---|',
      '| Training | 9,767 | Sale labels before 1 Jan 2026 |',
      '| Model selection | 576 | Eligible Jan–Feb seizures, labels before 1 Mar 2026 |',
      '| Calibration | 583 | Eligible Mar–Apr seizures, labels before 1 May 2026 |',
      '| Primary final test | 1,244 | Seizures from 1 May 2026 with observed sale in supplied data |','',
      f"Primary seizure dates are {p['seizure_date_range'][0]}–{p['seizure_date_range'][1]}; observed sale dates are {p['sale_date_range'][0]}–{p['sale_date_range'][1]}. The calibrated version was available from 1 May 2026 for all 1,244 primary cases. Sold date is a label-availability proxy, not a verified system-arrival timestamp. Availability of the nine source predictors at seizure is assumed; field-level timestamps were not provided.",'',
      'The supplied data contain only sold repossessed vehicles. Later seizures with unobserved sales are absent, so the test is conditional on observed liquidation and subject to selection/right-truncation. Only one July seizure appears in the primary test; this is not evidence of stable full-July performance.','',
      '## Primary point-prediction results','',summary_table,'',
      f"The paired row-bootstrap 95% interval for the reduction in MAE is **{money(bootstrap['percentile_95_inr'][0])}–{money(bootstrap['percentile_95_inr'][1])}** per case, around {money(bootstrap['mean_mae_reduction_inr'])}. This uses 2,000 fixed-seed resamples, conditional on the frozen models; it ignores temporal, entity and training dependence. It is not a robust uncertainty guarantee under drift.",'',
      f"Tuning MAE was {money(selected['selected_trial']['mae_inr'])}; the final-test MAE is {(p['model']['mae_inr']/selected['selected_trial']['mae_inr']-1)*100:.1f}% higher. The final result, not the more optimistic tuning metric, should lead the hackathon performance claim. MAPE is a regression error measure, not classification accuracy.",'',
      '## Uncertainty interval results','',
      '| Range | Covered / total | Coverage | Mean width | Mean interval score |','|---|---:|---:|---:|---:|']
    for name,label in [('base_interval','Sorted base quantile range'),('calibrated_interval','Frozen conformal expansion')]:
        m=p[name];lines.append(f"| {label} | {m['covered']} / {m['n']} | {percent(m['coverage'])} | {money(m['mean_width_inr'])} | {money(m['mean_interval_score_inr'])} |")
    lo,hi=p['calibrated_interval']['wilson_95']
    lines+=['',f"The descriptive 95% Wilson interval for coverage is **{percent(lo)}–{percent(hi)}** under independent Bernoulli assumptions. The point estimate is near the 80% target; this does not establish temporal, per-segment or future-horizon coverage. There are {p['calibrated_interval']['below']} sales below the lower endpoint and {p['calibrated_interval']['above']} above the upper endpoint. The endpoints are not individually calibrated 10th/90th percentiles.",'',
      f"The correction remains {money(calib['correction_inr'])} on each side, with the lower endpoint clipped at zero. Mean interval score uses width + 10 × each applicable miss distance; smaller is better. It improves only modestly despite the coverage gain because wider intervals have a cost.",'',
      '## Segments and support','',
      '| Fuel | n | Model MAE | B0 MAE | Calibrated coverage | 95% Wilson interval |','|---|---:|---:|---:|---:|---:|']
    for s in fuel:
        ci=s['calibrated_interval']['wilson_95'];lines.append(f"| {s['value']} | {s['n']} | {money(s['model']['mae_inr'])} | {money(s['baseline']['mae_inr'])} | {percent(s['calibrated_interval']['coverage'])} | {percent(ci[0])}–{percent(ci[1])} |")
    lines+=['',f"EV mean signed error is {money(ev['model']['mean_signed_error_inr'])}; negative means underprediction. Its calibrated misses include {ev['calibrated_interval']['below']} below-range and {ev['calibrated_interval']['above']} above-range outcomes. This small cohort does not support a strong EV accuracy or uncertainty claim. Do not change EV calibration on these test outcomes and then reuse the same cohort as validation.",'',
      f"There are **{p['unsupported_input_count']} primary cases** with at least one input outside training support. Their warnings total {sum(p['support_warning_counts'].values())}, because a case can have several warnings. They remain included in all headline metrics. The online POC marks such inputs for review. Full model, region, month and agreement-duration tables are in operational_segments.json; no best-segment-only filter was applied.",'',
      '### Coverage by seizure month','',
      '| Month | n | Coverage | Note |','|---|---:|---:|---|']
    for s in [x for x in segments if x['field']=='seizure_month']:
        lines.append(f"| {s['value']} | {s['n']} | {percent(s['calibrated_interval']['coverage'])} | {'Too few observations for a stable claim' if s['small_sample'] else 'Observed sold cases only'} |")
    lines+=['','## Secondary retrospective result','',
      f"The sale-period cohort has **{r['model']['n']} cases**, model MAE **{money(r['model']['mae_inr'])}**, B0 MAE **{money(r['baseline']['mae_inr'])}**, and calibrated coverage **{percent(r['calibrated_interval']['coverage'])}**. It contains every primary case plus 591 earlier seizures. Those 591 predate calibration availability, so this is a post-fit sale-period diagnostic, not a real-time replay. The two evaluations contain **1,835 unique agreements**, not 3,079 independent cases.",'',
      '## Failure examples','',
      'Examples follow the predeclared selection rule and are diagnostic, not a representative performance sample. The largest absolute-error case is also the largest downside miss.','',
      '| Selection | Agreement | Observed sale | Model median | Calibrated interval |','|---|---|---:|---:|---:|']
    for ex in examples:
        c=ex['case'];lines.append(f"| {ex['selection']} | {c['agreement_id']} | {money(c['actual_sale_inr'])} | {money(c['median_inr'])} | {money(c['calibrated_lower_inr'])}–{money(c['calibrated_upper_inr'])} |")
    lines+=['', 'The available features do not establish why a vehicle sold unusually low. Do not invent damage, fraud, distress or inspection explanations. These cases call for source-level investigation, not deletion from the reported test.','',
      '## Verification and next decision','',
      f"**{verification['passed']} checks passed**, covering frozen checksums, role separation, source-label reconciliation, model rescore samples, interval arithmetic, subgroup aggregation and seeded bootstrap reproduction. The original workbook and deployed Phase 8 model are unchanged. The final evidence is authoritative in this Phase 9 package; the Phase 8 dashboard retains its archived development-evidence view.",'',
      'For the hackathon, lead with the 15.5% primary MAE reduction and the honest uncertainty result, then show the EV limitation and a failed case. Keep lending benefits framed as simulations under explicit assumptions. This phase does not validate default probability, expected credit loss, future depreciation, causal profit, or production underwriting.','',
      'Future improvements require additional EV observations, verified inspection timestamps, longer outcome follow-up and a new untouched evaluation period. Any recalibration or model change informed by these final results is a new experiment. Next: Phase 10 submission artifacts and demo rehearsal.']
    write('Phase_9_Report.md','\n'.join(lines))

    card=f'''# Model card — TVS recovery valuation, frozen release

Version: `{calib['version']}`. Model SHA-256: `{calib['model_sha256']}`. Intended audience: hackathon reviewers and supervised POC operators. Status: tested local POC; not approved for production underwriting.

## Intended use and exclusions

Estimate gross liquidation sale value from supplied seizure-time vehicle and geography inputs for the observed sold-repossession population. Use as a review aid with explicit uncertainty limits. Do not interpret it as an origination default model, actual vehicle-health score, expected credit loss, independently calibrated EV forecast or validated 12/24/36-month residual value.

## Data and provenance

The original Analytics Case Study Dataset.xlsx contains 15,000 rows and 41 source columns. The Phase 1 canonical snapshot contains 49 fields and retains every source row. There are 306 EV and 14,694 petrol rows in the full source. Unsold seizures and performing loans are absent. Agreement IDs are unique, but cross-agreement vehicle/customer identity is unavailable, so independence at that level is not established. Source reality/anonymization/simulation status remains unconfirmed.

Canonical SHA-256: `{lock['artifact_sha256']['phase1/data/canonical_records.jsonl']}`. Raw workbook is unchanged. Full-file descriptive profiling preceded model development; this is an internal model-development holdout.

## Model and inputs

CatBoost 1.2.10, MultiQuantile 0.10/0.50/0.90, depth 6, learning rate 0.05, L2 regularization 3, 474 trees, seed 2026. Six predetermined trials were compared on 576 tuning cases. Training used 9,767 labels available before 1 Jan 2026. The final model was not refit on test data.

Seven categorical inputs: branch, region, state, tier, asset variant, model and fuel. Two numeric inputs: original asset cost and months from agreement to seizure. The latter is not confirmed manufacture age. Unknown categories are accepted by CatBoost but flagged for review; numeric values outside training ranges are also flagged. The API rejects missing/nonfinite numeric values, nonpositive cost, negative duration and forbidden extra fields.

Gender, income, CIBIL, realized yard duration, sale dates, sale amount and liquidation exposure are excluded from model predictors. Condition/document/accident fields remain excluded because definitions or availability timestamps were not established. Core feature availability at seizure is an assumption requiring data-owner confirmation.

## Calibration and explanations

Outputs are sorted within each row and clipped at zero. The median is the middle sorted output. Nonnegative conformal expansion was fitted on 583 separate eligible calibration cases using rank 468 for an 80% target; each endpoint expands by {money(calib['correction_inr'])}. This version is available from 1 May 2026. Interval endpoints are not independently calibrated quantiles.

Phase 8 provides native SHAP contributions for the raw output slot selected as the median. Additivity is checked before display. Contributions describe model associations relative to its reference, not causal effects, interval width or policy decisions. Attribution failure leaves the estimate unchanged with an unavailable label.

## Final evaluation

Primary cohort: 1,244 observed sold cases with seizures 1 May–9 July 2026 and sales 20 June–31 July 2026. Frozen model MAE {money(p['model']['mae_inr'])}, RMSE {money(p['model']['rmse_inr'])}, R² {p['model']['r2']:.4f}; B0 MAE {money(p['baseline']['mae_inr'])}. MAE reduction {p['mae_reduction_percent']:.2f}%. Calibrated coverage {percent(p['calibrated_interval']['coverage'])}; mean width {money(p['calibrated_interval']['mean_width_inr'])}.

EV: n={ev['n']}, MAE {money(ev['model']['mae_inr'])}, coverage {percent(ev['calibrated_interval']['coverage'])}, negligible MAE gain over B0. Petrol: n={petrol['n']}, MAE {money(petrol['model']['mae_inr'])}, coverage {percent(petrol['calibrated_interval']['coverage'])}. No claim of uniform subgroup performance is justified. July has only one primary seizure.

The 1,835-case secondary cohort overlaps all 1,244 primary cases and includes 591 seizures before model availability. It is a retrospective diagnostic, not independent prospective validation. See the final report for full metrics, descriptive intervals and failure cases.

## Serving, fallback and controls

The local Phase 8 service runs model, static dashboard and API on loopback. It checks bundle hashes, input availability dates, support and resource limits. A frozen B0 fallback is uncalibrated and review-only; the dashboard blocks lending from it. Simultaneous engine failure returns no estimate. Audit write failure blocks decision responses. The audit journal does not retain raw request values.

There is no multi-user authentication or production monitoring platform. Local users with machine access can access the POC. The demonstration lending policy and future scenario factors are not approved TVS Credit rules. Income/obligations in examples are fictional; source salary frequency is unconfirmed.

## Risks, monitoring and revision

Monitor label-arrival delay, unsold/censoring rates, unknown categories, support drift, monthly and fuel-specific MAE/coverage/width, lower-tail misses, audit/storage health and fallback rates. Confirm units and observation times before enabling excluded features. A monitoring plan is not evidence that production monitoring is installed.

Do not silently recalibrate on these test outcomes. A revised model, feature set or EV interval requires a new version, separate calibration data and an untouched later cohort. The current evidence supports a supervised hackathon demo, not automatic credit approval.

## Ownership and rights

The project owner must confirm authorization to redistribute the supplied dataset and fitted artifacts. This package has not established data licensing or real-world production authorization. Third-party runtime versions are recorded in requirements.txt; their licenses remain applicable. No LLM changes model or finance outputs.
'''
    write('Model_Card.md',card)
    dictionary=read(ROOT/'configs/data_dictionary.json')
    text=['# Final data dictionary','', 'All 41 source fields and 8 derived/traceability fields are accounted for. Definitions remain those verified in Phase 1; unresolved meanings have not been guessed. “Used” below identifies the nine inputs in the frozen model, not independent verification of their historical availability.','',
          '| Canonical field | Source | Type / unit | Used by model | Definition |','|---|---|---|---|---|']
    for d in dictionary:
        text.append('| '+' | '.join(str(v).replace('|','/').replace('\n',' ') for v in [d['canonical_name'],d['source_name'],d['type']+' / '+d['unit'],'Yes' if d['canonical_name'] in contract['features'] else 'No',d['definition']])+' |')
    text+=['','## Availability and policy contract','',
           'Every live model input requires an available-on date no later than the requested seizure decision date. The dataset lacks field-level timestamps, so the retrospective feature-availability assumption is unverified. Sold date is only a proxy for label availability. See Open_Definitions.md for the outstanding data-owner questions.','',
           'CIBIL -1 is preserved in the raw score and converted to null only in the usable-score derived view, without claiming it means no credit history. Source salary is not verified monthly income. Loan rate and liquidation balance conventions remain unresolved. Source age is represented by the derived agreement-to-seizure duration, not a manufacture-age claim.','',
           'The machine-readable configs/data_dictionary.json includes observed codes, model-exclusion purposes and unresolved definitions. Source codes are not a verified business codebook.']
    write('Data_Dictionary.md','\n'.join(text))

    # Standalone scientific figure: no generated artwork or unlabelled confidence claims.
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(2,2,figsize=(12,8.4),layout='constrained')
    fig.suptitle('Frozen operational holdout · 1,244 observed sold cases',fontsize=17,fontweight='bold')
    ax=axes[0,0];vals=[p['baseline']['mae_inr'],p['model']['mae_inr']]
    ax.bar(['B0 baseline','Frozen model'],vals,color=['#8493a9','#126bb5'],width=.55)
    for i,v in enumerate(vals):ax.text(i,v+120,f'INR {v:,.0f}',ha='center',fontweight='bold')
    ax.set_ylim(0,max(vals)*1.22);ax.set_ylabel('Mean absolute error (INR)');ax.set_title(f"MAE improves by {p['mae_reduction_percent']:.1f}%")
    ax=axes[0,1];y=np.array([x['actual_sale_inr'] for x in rows]);pred=np.array([x['median_inr'] for x in rows]);maximum=max(y.max(),pred.max())*1.05
    ax.scatter(y,pred,s=11,alpha=.3,color='#126bb5',edgecolors='none');ax.plot([0,maximum],[0,maximum],color='#6b7786',ls='--',lw=1)
    ax.set(xlim=(0,maximum),ylim=(0,maximum),xlabel='Observed gross sale (INR)',ylabel='Predicted median (INR)',title='Large individual errors remain')
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v,pos:f'{v/1000:.0f}k'));ax.yaxis.set_major_formatter(FuncFormatter(lambda v,pos:f'{v/1000:.0f}k'))
    ax=axes[1,0];groups=[('All',p['calibrated_interval'])]+[(s['value'],s['calibrated_interval']) for s in fuel]
    values=[x[1]['coverage'] for x in groups];error=np.array([[v-g[1]['wilson_95'][0] for v,g in zip(values,groups)],[g[1]['wilson_95'][1]-v for v,g in zip(values,groups)]])
    ax.bar(range(3),values,color=['#126bb5','#c17817','#3a8a80'],width=.55,yerr=error,capsize=5)
    ax.axhline(.8,color='#555',ls='--',lw=1);ax.set_ylim(0,1.03);ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.set_xticks(range(3),[f"{name}\nn={m['n']}" for name,m in groups]);ax.set_title('Pooled coverage does not hold for EVs');ax.set_ylabel('Calibrated interval coverage')
    ax.text(.03,.96,'Bars: observed coverage\nWhiskers: descriptive 95% Wilson intervals',transform=ax.transAxes,va='top',fontsize=8)
    ax=axes[1,1];residual=pred-y;ax.hist(residual,bins=35,color='#4c83ad',edgecolor='white');ax.axvline(0,color='#555',ls='--');ax.set_title('Signed prediction errors');ax.set_xlabel('Prediction minus observed sale (INR)');ax.set_ylabel('Cases');ax.xaxis.set_major_formatter(FuncFormatter(lambda v,pos:f'{v/1000:.0f}k'))
    fig.savefig(ROOT/'reports/Final_Evaluation.png',dpi=170);plt.close(fig)
    print('Created final report, model card, 49-field dictionary and evaluation figure')

if __name__=='__main__':main()
