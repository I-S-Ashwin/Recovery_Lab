# Phase 5: exposure, risk scoring and lending policy

This phase implements a runnable financial calculation and candidate-search engine. The lending examples use explicit fictional assumptions. Rates and policy limits are demonstration settings, not TVS Credit policy or validated optimum lending terms.

## Implemented capabilities

- Cent-rounded amortization schedules with exact principal reconciliation and a final-instalment adjustment.
- Scheduled outstanding principal after each successful payment, including month zero.
- Net recovery, median/downside shortfall and a 0-100 downside severity score.
- Enumeration of 35 LTV/tenure combinations under a fixed illustrative rate schedule.
- Affordability checks using explicitly verified monthly income and obligations.
- Collateral constraints at pre-maturity checkpoints, with explicit recovery-delay handling.
- Deterministic ranking and feasible, no-feasible-offer, or review-required outcomes.
- Constraint reasons, hashes and full candidate output for audit.
- Integration of the risk formula with the 583 existing calibration-sample estimates; no model inference or training required.

## Demonstration outcomes

| Example | Result | Feasible candidates | Principal INR | LTV | Tenure months | Annual nominal rate | EMI INR |
|---|---|---:|---:|---:|---:|---:|---:|
| base | feasible_offer | 24 | 80,000 | 80% | 18 | 21% | 5,219.59 |
| low_income | no_feasible_offer | 0 | — | — | — | — | — |
| missing_obligations | review_required | 0 | — | — | — | — | — |
| low_recovery | no_feasible_offer | 0 | — | — | — | — | — |
| missing_path | no_feasible_offer | 0 | — | — | — | — | — |
| recovery_delay | feasible_offer | 24 | 80,000 | 80% | 18 | 21% | 5,219.59 |

The base fixture assumes original cost INR 100,000, monthly income INR 30,000, existing obligations INR 5,000 and recovery expenses INR 3,000. Its downside value path is hand-authored, not predicted. The verified flags are part of the fictional fixture, not a claim of actual customer verification.

## Policy and ranking

LTV grid: 60%, 65%, 70%, 75%, 80%, 85%, 90%. Tenures: 12, 18, 24, 30, 36 months. Base annual nominal rate: 18%; policy premiums: 2 points up to 70% LTV, 3 up to 80%, 5 up to 90%. These rates are assumptions and are not derived from the workbook's net IRR.
Maximum FOIR: 40%. Maximum downside shortfall ratio: 20%. Checks occur at months 0, 6, 12, 18, 24, 30 and 36 where applicable, plus maturity. Month zero explicitly checks initial principal exposure. Maturity with zero exposure does not require a collateral value.
Feasible candidates are ranked by highest principal, then lowest total contractual interest, then shortest tenure. This objective is not profit maximization. Thresholds use exact arithmetic before rounding the displayed risk score.

## Financial conventions

Money uses Decimal arithmetic and rounding to INR 0.01. Interest accrues monthly on remaining principal and is rounded monthly. Regular EMI is calculated from the nominal annual rate divided by 12; the last payment adjusts for accumulated cent rounding. Maximum scheduled instalment is used in FOIR, including the final adjustment.
Exposure at default month t is the scheduled remaining principal after t successful payments. It is frozen during the assumed recovery delay: no later payments, extra default interest or unknown arrears are fabricated. The downside sale value is looked up at t plus delay. No interpolation or extrapolation is performed in Phase 5.
A missing required future checkpoint rejects the affected candidate. Missing monthly obligations or verification produces review_required, rather than an affordability pass. Malformed or negative numeric values raise an input error.

## Risk score definition

Net downside recovery = max(0, lower value - explicit recovery cost). Downside shortfall = max(0, exposure - net downside recovery). For positive exposure the score is round-half-up(100 * downside shortfall / exposure). Bands: 0-25 Low, 26-50 Medium, 51-75 High, 76-100 Critical. Zero exposure returns no score and no band.
This is shortfall severity under assumptions, not probability of default or loss. A central calibrated lower interval bound is not automatically a guaranteed 90% one-sided floor. Future assumed paths do not inherit Phase 4 interval coverage.

## Link to the supplied data

The risk formula was applied to 583 saved Phase 4 calibration estimates, using each original recorded liquidation balance and an explicit INR 3,000 assumed recovery cost. These are post-fit, retrospective calculations. They are not live historical decisions, independent model validation, economic LGD or evidence of policy uplift.
Actual lending recommendations were not generated for these borrowers: the workbook lacks verified monthly income frequency, existing obligations and future collateral paths. All six lending demonstrations use separate labelled fixtures. The original dataset and frozen models remain unchanged; final-test outcomes remain unscored.

## Phase 6 handoff

The lending engine consumes a downside_value_path and an explicit source label. Phase 6 can supply conditional future-value paths and stress scenarios through this interface. Add scenario evidence without silently upgrading assumed values into validated forecasts. The API/dashboard phases can call the same engine directly; no financial logic should be duplicated in the UI.
The saved candidate lists, selected payment schedule and per-checkpoint rejection reasons support explainable demonstrations. No loan is automatically approved and no recommendation has been transmitted to an external system.

## Verification

verification.json records independent amortization examples, principal reconciliation, rounding and boundary checks, monotonic-risk tests, all feasible-candidate constraint checks and source hashes. These are software tests, not production underwriting validation.
