# Phase 3: CatBoost model development

Six predeclared CatBoost quantile candidates were trained on the frozen training set. The winner was selected by operational tuning median MAE. These are tuning results, not unbiased final-test performance.

Training rows: 9,767. Operational tuning rows: 576. Predictors: 9. Selected trial: C2, 474 trees.

## Development comparison

| Protocol | Rows | Baseline MAE INR | CatBoost MAE INR | MAE reduction | CatBoost RMSE INR |
|---|---:|---:|---:|---:|---:|
| operational | 576 | 7,360 | 5,913 | 19.7% | 8,068 |
| retrospective | 1,879 | 7,928 | 6,347 | 19.9% | 8,979 |

MAE is average absolute error in rupees. A reduction here is a development improvement, not a profit uplift or a guaranteed future accuracy gain. The retrospective tuning set overlaps the operational tuning set and is diagnostic only. It was not used to select the winner.

## Fixed search

| Trial | Depth | Learning rate | L2 | Trees retained | Operational MAE INR |
|---|---:|---:|---:|---:|---:|
| C1 | 4 | 0.05 | 3 | 595 | 5,973 |
| C2 | 6 | 0.05 | 3 | 474 | 5,913 |
| C3 | 8 | 0.05 | 3 | 310 | 5,914 |
| C4 | 4 | 0.1 | 10 | 378 | 5,967 |
| C5 | 6 | 0.1 | 10 | 245 | 5,953 |
| C6 | 8 | 0.1 | 10 | 267 | 5,918 |

Early stopping uses MultiQuantile loss on operational tuning; candidate selection uses ordered median MAE on that same development set. Maximum 1,000 iterations, patience 80, fixed seed 2026, four CPU threads. No extra search was added after results.

## Uncertainty output

The model outputs raw 0.10, 0.50 and 0.90 quantiles. The shared inference function sorts them per record and floors at zero. Sorting can change the middle prediction when quantiles cross; the same transformed median is used in every reported comparison. This is postprocessing, not calibration. Raw and ordered outputs are retained in tuning exports.
The displayed lower/upper range is uncalibrated. Its development coverage and width are diagnostic only, particularly because the same cases drove early stopping and selection. Phase 4 must calibrate on the reserved calibration role.

## Time and population limitations

Training sale labels precede 1 January 2026; the operational tuning outcomes precede 1 March. Model weights use only training outcomes, but settings and stopping iteration were selected using later tuning outcomes. Therefore the selected model can be treated as available no earlier than 1 March under the sale-date arrival assumption; its tuning performance is not an independently deployed January backtest.
Only sold assets appear in the source. The operational tuning sample additionally requires sale by its development boundary, favoring faster recoveries. Field timestamps, real vehicle/customer IDs and operational label-arrival timestamps are missing. These limitations remain despite computational leakage checks.
The original asset-age column is not used. The explicitly named agreement-to-seizure elapsed duration is used instead. Inspection/document/accident fields remain excluded pending source definitions. There is no customer-default model or long-horizon forecast here.

## Saved model and handoff

The native CatBoost model, exact fitted parameters, feature contract, fit/selection IDs, versions and hashes are included. Inference rejects missing/extra fields and invalid cost/duration. Category novelty is recorded separately from prediction validity. Global feature importance is not a causal explanation or a per-customer reason.
Freeze this model for Phase 4 before accessing calibration outcomes. Do not refit on calibration or final-test labels. A later refit needs a new model version and a new calibration design. The final-test roles remain unscored.

## Research and implementation reference

CatBoost officially supports the MultiQuantile objective used here: https://catboost.ai/docs/en/concepts/loss-functions-regression . Its availability does not establish performance on this dataset; the measured development comparison above does.
