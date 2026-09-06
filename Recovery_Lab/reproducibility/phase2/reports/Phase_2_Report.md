# Phase 2: temporal cohorts and valuation baseline

Phase 2 is implemented. The baseline was fitted on training outcomes only and scored on development tuning sets. Calibration and final-test prediction errors have not been computed.

## Frozen split membership

| Protocol | Train | Tuning | Calibration reserved | Final test reserved | Excluded |
|---|---:|---:|---:|---:|---:|
| operational | 9,767 | 576 | 583 | 1,244 | 2,830 |
| retrospective | 9,767 | 1,879 | 1,519 | 1,835 | 0 |

Training labels are available before 1 January 2026. Tuning ends before 1 March; calibration ends before 1 May; final testing is reserved for the remaining observed period through 31 July. The plan was saved and hashed before fitting the baseline.

## Two different questions

- **Operational:** could a seizure-time prediction use only labels already available before that development period? Seizures must occur inside their allocated period, and outcomes must arrive before its end. This stricter rule leaves delayed outcomes and older seizures excluded from those roles.
- **Retrospective:** does a model fitted on older sold records generalize to later sale cohorts? Some tuning vehicles were seized before training finished, so this is not a deployable-at-seizure claim.
- These are alternative experiments on the same source, not independent datasets. Compare future models within the same protocol, never across protocols to claim improvement.

## Baseline

B0 predicts original cost multiplied by the training median sale-to-original-cost ratio for model and elapsed-agreement-duration bin. Fixed lower bounds are 0, 6, 12, 18, 24, 36, 48 and 60 months; each interval includes its lower bound and excludes the next. The last interval is 60+ months. This is not confirmed vehicle age.
Groups need at least 30 training records. Back off to model, then fuel, then the global training median. B00 always uses the global training ratio. No hyperparameters or bin boundaries were tuned against final-test results.

## Development results

| Protocol | Model | Records | MAE INR | RMSE INR | MAPE | Median absolute error INR |
|---|---|---:|---:|---:|---:|---:|
| operational | B0_model_duration | 576 | 7,360 | 9,991 | 22.05% | 5,194 |
| operational | B00_global_ratio | 576 | 8,933 | 11,384 | 27.51% | 7,482 |
| retrospective | B0_model_duration | 1,879 | 7,928 | 10,786 | 22.46% | 5,842 |
| retrospective | B00_global_ratio | 1,879 | 9,627 | 12,391 | 27.52% | 7,817 |

MAE is the average absolute difference between estimated and actual sale amounts. MAPE averages percentage errors relative to each actual sale amount; it is not an accuracy percentage. These are development results, not final-test evidence.

## Sample limitations

The operational tuning sample includes only vehicles sold before its boundary. It therefore favors sufficiently rapid recoveries; unsold seizures are absent from the source entirely. Do not generalize its errors to all seized assets. Operational final testing has a similar end-of-file follow-up limit. No population coverage denominator is available.
Sale date is used as a proxy for label arrival, with strict date cutoffs. Actual arrival timestamps are missing. A 7- and 30-day reporting-lag sensitivity is supplied as cohort counts only; these are assumptions, not measured lags.
Full-file descriptive profiling occurred in Phase 1. The reserved test is a model-development holdout, not an external dataset that nobody has seen. Do not examine its prediction errors until the planned final evaluation.
Agreement IDs are unique, but true customer/vehicle IDs are missing, so cross-agreement entity independence cannot be certified. Per-field timestamp provenance remains an explicit assumption.

## Fallback use on tuning sets

| Protocol | Level | Records |
|---|---|---:|
| operational | model_duration | 551 |
| operational | model | 25 |
| retrospective | model_duration | 1,819 |
| retrospective | model | 60 |

## Phase 3 handoff

- Train CatBoost only on the frozen training role and tune on the matching tuning role.
- Use the Phase 1 whitelist; do not feed the entire audit table to a model.
- Compare against the matching B0 predictions and preserve agreement membership.
- Reserve calibration for interval calibration and final-test outcomes for the frozen final evaluation.
- Refit on additional development labels only after model selection, with a separate version and release date before the subsequent prediction cohort. Never evaluate that refit on labels it has consumed.
- Keep both protocol names, sample counts and selection limitations with every result.
- No risk classifier, lending policy or future-value forecast was fitted in Phase 2.

## Verification

verification.json records executed boundary, fallback, leakage and artifact checks. The canonical Phase 1 input is verified against its original hash. Split manifests contain IDs, role, dates and reasons; they contain no target sale values. Tuning prediction exports contain targets only for tuning agreements.
