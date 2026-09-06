# Phase 5 — lending calculations and policy engine

Read `reports/Phase_5_Report.md` first. This package implements the financial and decision logic with Python's standard library. CatBoost does not need to be imported or retrained to run this phase.

## What is real and what is illustrative

The engine, test results, amortization schedules and saved candidate searches are real executable outputs. All lending examples are fictional and labelled as such. Their income, obligations, future values, recovery costs and rates are explicitly supplied assumptions, not inferred facts about customers in the workbook.

The separate retrospective risk file uses actual source liquidation balances and previously saved Phase 4 estimates for the 583 calibration cases, plus an assumed recovery cost. It demonstrates arithmetic integration only. It is not an independent forecast test, live lending recommendation, calibrated loss probability, LGD calculation or proof of business uplift.

## Main files

- `src/engine.py`: EMI schedules, recovery severity score, policy validation and candidate selection.
- `src/cli.py`: one-request simulation interface with structured input errors.
- `configs/demo_policy.json`: explicit demo policy and pricing assumptions.
- `examples/`: six input fixtures covering feasible, unaffordable, missing-input, low-recovery, missing-path and delayed-recovery cases.
- `results/`: full candidate comparisons, constraint reasons and selected payment schedules.
- `results/retrospective_recovery_risk.jsonl`: source-linked arithmetic on already consumed calibration cases.
- `reports/verification.json`: executed test outcomes.
- `policy_lock.json`: source and policy hashes.

## Run one example

From `phase5/`, with Python 3.11+ (3.12.14 used here):

```text
python src/cli.py --request examples/base.json --policy configs/demo_policy.json --output my_result.json
```

To reproduce all demonstrations and source-linked calculations, keep the prior phase folders as siblings:

```text
python src/run_phase5.py --phase1 ../phase1 --phase4 ../phase4 --output .
python src/verify.py --phase1 ../phase1 --phase4 ../phase4 --output .
```

The run locks policy/source hashes. Use a new version for changed policy experiments. The CLI can be used separately to explore explicit inputs without changing the frozen demonstration outputs.

## Input conventions

Amounts are INR. Rates and LTV are fractions: 0.21 means 21%, not 21. Income must be explicitly monthly and verified; obligations must be supplied and verified. Verification flags are caller assertions; this POC does not verify documents or connect to a credit bureau. Zero obligations are acceptable only when explicitly supplied; missing obligations are not silently zero.

The downside path must contain exact integer sale-month values for every exposed checkpoint. There is no automatic interpolation, depreciation forecasting or reuse of future observed sale values. Recovery delay changes the sale lookup month while freezing principal at the default checkpoint.

Risk score is rounded downside shortfall severity, not probability. Threshold checks use the unrounded ratio. Recovery cost must be explicit. Zero exposure returns no applicable risk score. A central interval lower bound is not a guaranteed one-sided protection level.

The status `feasible_offer` means a candidate satisfies the supplied simulation policy. It is never an automatic approval. The engine maximizes supported principal, then minimizes contractual interest; it does not optimize bank profit. Candidate pricing is a fixed LTV-based illustration, not a learned causal interest-rate strategy.

Phase 6 will generate labelled conditional value paths and portfolio scenarios for this interface. Actual underwriting and production approval remain outside the demonstration.
