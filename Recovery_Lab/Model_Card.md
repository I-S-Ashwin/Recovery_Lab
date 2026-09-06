# Model card — TVS recovery valuation, frozen release

Version: `phase4-operational-80-v1`. Model SHA-256: `1b0c5949af11932f3ea693fee55a91aa68bc292d524e42f45151b5acd707d0d3`. Intended audience: hackathon reviewers and supervised POC operators. Status: tested local POC; not approved for production underwriting.

## Intended use and exclusions

Estimate gross liquidation sale value from supplied seizure-time vehicle and geography inputs for the observed sold-repossession population. Use as a review aid with explicit uncertainty limits. Do not interpret it as an origination default model, actual vehicle-health score, expected credit loss, independently calibrated EV forecast or validated 12/24/36-month residual value.

## Data and provenance

The original Analytics Case Study Dataset.xlsx contains 15,000 rows and 41 source columns. The Phase 1 canonical snapshot contains 49 fields and retains every source row. There are 306 EV and 14,694 petrol rows in the full source. Unsold seizures and performing loans are absent. Agreement IDs are unique, but cross-agreement vehicle/customer identity is unavailable, so independence at that level is not established. Source reality/anonymization/simulation status remains unconfirmed.

Canonical SHA-256: `34a903573d80aed79b58da9bc59a11e3764c2f7ada5ac030e99536b8efe50be0`. Raw workbook is unchanged. Full-file descriptive profiling preceded model development; this is an internal model-development holdout.

## Model and inputs

CatBoost 1.2.10, MultiQuantile 0.10/0.50/0.90, depth 6, learning rate 0.05, L2 regularization 3, 474 trees, seed 2026. Six predetermined trials were compared on 576 tuning cases. Training used 9,767 labels available before 1 Jan 2026. The final model was not refit on test data.

Seven categorical inputs: branch, region, state, tier, asset variant, model and fuel. Two numeric inputs: original asset cost and months from agreement to seizure. The latter is not confirmed manufacture age. Unknown categories are accepted by CatBoost but flagged for review; numeric values outside training ranges are also flagged. The API rejects missing/nonfinite numeric values, nonpositive cost, negative duration and forbidden extra fields.

Gender, income, CIBIL, realized yard duration, sale dates, sale amount and liquidation exposure are excluded from model predictors. Condition/document/accident fields remain excluded because definitions or availability timestamps were not established. Core feature availability at seizure is an assumption requiring data-owner confirmation.

## Calibration and explanations

Outputs are sorted within each row and clipped at zero. The median is the middle sorted output. Nonnegative conformal expansion was fitted on 583 separate eligible calibration cases using rank 468 for an 80% target; each endpoint expands by ₹1,859.21. This version is available from 1 May 2026. Interval endpoints are not independently calibrated quantiles.

Phase 8 provides native SHAP contributions for the raw output slot selected as the median. Additivity is checked before display. Contributions describe model associations relative to its reference, not causal effects, interval width or policy decisions. Attribution failure leaves the estimate unchanged with an unavailable label.

## Final evaluation

Primary cohort: 1,244 observed sold cases with seizures 1 May–9 July 2026 and sales 20 June–31 July 2026. Frozen model MAE ₹7,051.86, RMSE ₹9,557.46, R² 0.6913; B0 MAE ₹8,342.91. MAE reduction 15.47%. Calibrated coverage 80.47%; mean width ₹23,145.88.

EV: n=36, MAE ₹13,508.80, coverage 61.11%, negligible MAE gain over B0. Petrol: n=1208, MAE ₹6,859.44, coverage 81.04%. No claim of uniform subgroup performance is justified. July has only one primary seizure.

The 1,835-case secondary cohort overlaps all 1,244 primary cases and includes 591 seizures before model availability. It is a retrospective diagnostic, not independent prospective validation. See the final report for full metrics, descriptive intervals and failure cases.

## Serving, fallback and controls

The local Phase 8 service runs model, static dashboard and API on loopback. It checks bundle hashes, input availability dates, support and resource limits. A frozen B0 fallback is uncalibrated and review-only; the dashboard blocks lending from it. Simultaneous engine failure returns no estimate. Audit write failure blocks decision responses. The audit journal does not retain raw request values.

There is no multi-user authentication or production monitoring platform. Local users with machine access can access the POC. The demonstration lending policy and future scenario factors are not approved TVS Credit rules. Income/obligations in examples are fictional; source salary frequency is unconfirmed.

## Risks, monitoring and revision

Monitor label-arrival delay, unsold/censoring rates, unknown categories, support drift, monthly and fuel-specific MAE/coverage/width, lower-tail misses, audit/storage health and fallback rates. Confirm units and observation times before enabling excluded features. A monitoring plan is not evidence that production monitoring is installed.

Do not silently recalibrate on these test outcomes. A revised model, feature set or EV interval requires a new version, separate calibration data and an untouched later cohort. The current evidence supports a supervised hackathon demo, not automatic credit approval.

## Ownership and rights

The project owner must confirm authorization to redistribute the supplied dataset and fitted artifacts. This package has not established data licensing or real-world production authorization. Third-party runtime versions are recorded in requirements.txt; their licenses remain applicable. No LLM changes model or finance outputs.

