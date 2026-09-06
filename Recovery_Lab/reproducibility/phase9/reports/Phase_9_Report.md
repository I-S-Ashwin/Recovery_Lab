# Phase 9 — frozen final evaluation

The frozen model reduces MAE by **15.47%** against B0 on **1,244 reserved operational cases**: ₹7,051.86 versus ₹8,342.91. The calibrated interval covers **80.47%** of observed sales, with a mean width of **₹23,145.88**.

**The pooled result hides weaker EV performance.** EV coverage is 61.11% on 36 cases; its MAE gain over B0 is only 0.41%. This release is not validated for a claim of 80% coverage in every segment.

## Frozen protocol and provenance

The evaluation plan was written and hashed before test predictions were computed. Model weights, calibration correction, policy, split boundaries and feature definitions were not changed. All cases in the two locked final-test cohorts were retained, including unsupported inputs and large errors. Phase 1 had profiled the full file, so this is a model-development holdout, not an unseen external dataset. After this evaluation, these outcomes must not be reused as a fresh holdout for future tuning.

| Role | Records | Availability rule |
|---|---:|---|
| Training | 9,767 | Sale labels before 1 Jan 2026 |
| Model selection | 576 | Eligible Jan–Feb seizures, labels before 1 Mar 2026 |
| Calibration | 583 | Eligible Mar–Apr seizures, labels before 1 May 2026 |
| Primary final test | 1,244 | Seizures from 1 May 2026 with observed sale in supplied data |

Primary seizure dates are 2026-05-01–2026-07-09; observed sale dates are 2026-06-20–2026-07-31. The calibrated version was available from 1 May 2026 for all 1,244 primary cases. Sold date is a label-availability proxy, not a verified system-arrival timestamp. Availability of the nine source predictors at seizure is assumed; field-level timestamps were not provided.

The supplied data contain only sold repossessed vehicles. Later seizures with unobserved sales are absent, so the test is conditional on observed liquidation and subject to selection/right-truncation. Only one July seizure appears in the primary test; this is not evidence of stable full-July performance.

## Primary point-prediction results

| Metric | Frozen model | Frozen B0 baseline |
|---|---:|---:|
| MAE | ₹7,051.86 | ₹8,342.91 |
| RMSE | ₹9,557.46 | ₹11,085.38 |
| Median absolute error | ₹5,304.06 | ₹6,545.79 |
| Mean signed error (prediction − sale) | ₹-663.44 | ₹115.14 |
| MAPE | 19.07% | 22.80% |
| WAPE | 15.64% | 18.51% |
| R² | 0.6913 | 0.5847 |

The paired row-bootstrap 95% interval for the reduction in MAE is **₹1,003.73–₹1,574.95** per case, around ₹1,291.05. This uses 2,000 fixed-seed resamples, conditional on the frozen models; it ignores temporal, entity and training dependence. It is not a robust uncertainty guarantee under drift.

Tuning MAE was ₹5,912.88; the final-test MAE is 19.3% higher. The final result, not the more optimistic tuning metric, should lead the hackathon performance claim. MAPE is a regression error measure, not classification accuracy.

## Uncertainty interval results

| Range | Covered / total | Coverage | Mean width | Mean interval score |
|---|---:|---:|---:|---:|
| Sorted base quantile range | 893 / 1244 | 71.78% | ₹19,427.46 | ₹33,904.06 |
| Frozen conformal expansion | 1001 / 1244 | 80.47% | ₹23,145.88 | ₹33,180.33 |

The descriptive 95% Wilson interval for coverage is **78.17%–82.57%** under independent Bernoulli assumptions. The point estimate is near the 80% target; this does not establish temporal, per-segment or future-horizon coverage. There are 98 sales below the lower endpoint and 145 above the upper endpoint. The endpoints are not individually calibrated 10th/90th percentiles.

The correction remains ₹1,859.21 on each side, with the lower endpoint clipped at zero. Mean interval score uses width + 10 × each applicable miss distance; smaller is better. It improves only modestly despite the coverage gain because wider intervals have a cost.

## Segments and support

| Fuel | n | Model MAE | B0 MAE | Calibrated coverage | 95% Wilson interval |
|---|---:|---:|---:|---:|---:|
| EV | 36 | ₹13,508.80 | ₹13,564.32 | 61.11% | 44.86%–75.22% |
| Petrol | 1208 | ₹6,859.44 | ₹8,187.31 | 81.04% | 78.74%–83.15% |

EV mean signed error is ₹-7,260.48; negative means underprediction. Its calibrated misses include 3 below-range and 11 above-range outcomes. This small cohort does not support a strong EV accuracy or uncertainty claim. Do not change EV calibration on these test outcomes and then reuse the same cohort as validation.

There are **19 primary cases** with at least one input outside training support. Their warnings total 20, because a case can have several warnings. They remain included in all headline metrics. The online POC marks such inputs for review. Full model, region, month and agreement-duration tables are in operational_segments.json; no best-segment-only filter was applied.

### Coverage by seizure month

| Month | n | Coverage | Note |
|---|---:|---:|---|
| 2026-05 | 679 | 79.53% | Observed sold cases only |
| 2026-06 | 564 | 81.56% | Observed sold cases only |
| 2026-07 | 1 | 100.00% | Too few observations for a stable claim |

## Secondary retrospective result

The sale-period cohort has **1835 cases**, model MAE **₹7,157.07**, B0 MAE **₹8,603.82**, and calibrated coverage **80.76%**. It contains every primary case plus 591 earlier seizures. Those 591 predate calibration availability, so this is a post-fit sale-period diagnostic, not a real-time replay. The two evaluations contain **1,835 unique agreements**, not 3,079 independent cases.

## Failure examples

Examples follow the predeclared selection rule and are diagnostic, not a representative performance sample. The largest absolute-error case is also the largest downside miss.

| Selection | Agreement | Observed sale | Model median | Calibrated interval |
|---|---|---:|---:|---:|
| Nearest median absolute error | ASSET_1004 | ₹34,000.00 | ₹39,308.50 | ₹28,691.58–₹48,959.48 |
| Largest absolute error | ASSET_1161 | ₹15,000.00 | ₹61,099.67 | ₹44,952.92–₹72,331.48 |
| Largest calibrated downside miss | ASSET_1161 | ₹15,000.00 | ₹61,099.67 | ₹44,952.92–₹72,331.48 |
| First unsupported agreement ID | ASSET_10885 | ₹80,500.00 | ₹67,972.60 | ₹51,406.66–₹90,811.54 |

The available features do not establish why a vehicle sold unusually low. Do not invent damage, fraud, distress or inspection explanations. These cases call for source-level investigation, not deletion from the reported test.

## Verification and next decision

**115 checks passed**, covering frozen checksums, role separation, source-label reconciliation, model rescore samples, interval arithmetic, subgroup aggregation and seeded bootstrap reproduction. The original workbook and deployed Phase 8 model are unchanged. The final evidence is authoritative in this Phase 9 package; the Phase 8 dashboard retains its archived development-evidence view.

For the hackathon, lead with the 15.5% primary MAE reduction and the honest uncertainty result, then show the EV limitation and a failed case. Keep lending benefits framed as simulations under explicit assumptions. This phase does not validate default probability, expected credit loss, future depreciation, causal profit, or production underwriting.

Future improvements require additional EV observations, verified inspection timestamps, longer outcome follow-up and a new untouched evaluation period. Any recalibration or model change informed by these final results is a new experiment. Next: Phase 10 submission artifacts and demo rehearsal.
