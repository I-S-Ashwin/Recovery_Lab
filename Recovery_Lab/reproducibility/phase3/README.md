# Phase 3: CatBoost development model

Read `reports/Phase_3_Report.md` for results and limitations. This package contains an actual trained model, the fixed six-candidate search, development comparisons and a reusable inference contract.

## Files

- `models/catboost_quantiles.cbm`: selected native CatBoost model, predicting three quantiles.
- `models/feature_contract.json`: exact nine predictors, input handling and training support.
- `models/selected_parameters.json`: actual fitted parameters.
- `models/training_provenance.json`: training and selection agreement IDs and predecessor hashes.
- `configs/search_plan.json`: predeclared candidates and selection rule.
- `experiment_lock.json`: input, source-code and configuration hashes.
- `reports/trials.json`: all six development trials, retained trees, runtime and losses.
- `reports/comparison.json`: comparison with the matching Phase 2 baseline in both protocols.
- `reports/segment_metrics.json`: fuel/model/region diagnostics, including weak-sample flags.
- `reports/global_feature_importance.json`: global model importance, not causal or individual explanations.
- `reports/Development_Results.png`: visual comparison and development diagnostics.
- `data/*_tuning_predictions.jsonl`: tuning predictions only; raw and ordered quantiles are both preserved.
- `src/valuation.py`: strict preparation and inference implementation shared with training.
- `src/train.py`, `src/verify.py`: reproducible experiment and verification.

## Reproduce locally

Keep `phase1/`, `phase2/` and `phase3/` as sibling folders. Install the supplied pinned requirements in your own isolated Python environment. The run here used Python 3.12.14 and project-local dependencies; no shared runtime packages were modified.

From `phase3/`:

```text
python -m pip install -r requirements.txt
python src/train.py --phase1 ../phase1 --phase2 ../phase2 --output .
python src/verify.py --phase1 ../phase1 --phase2 ../phase2 --output .
python src/plot_results.py --output .
```

The search takes CPU time; inference can load the saved model without retraining. The lock refuses changed source/configuration/input hashes. For a changed experiment, create a new version rather than modifying the frozen experiment.

For inference, import `Valuator` from `src/valuation.py`, load `models/catboost_quantiles.cbm`, and pass a DataFrame containing exactly the features listed in `models/feature_contract.json`. The returned array has lower, middle and upper ordered estimates. Extra target/audit columns are rejected.

## Interpretation

The selected model is a candidate for Phase 4, not production-approved lending software. Early stopping and selection use operational tuning outcomes, so those errors are development estimates. The retrospective diagnostic overlaps that development sample and is not independent confirmation.

Three quantile estimates are not a calibrated confidence interval. They still need the separate Phase 4 calibration procedure. No calibration or final-test roles were scored here. Conditional future-value projections, risk scores and lending policies are later phases.

The source age ambiguity, missing timestamp provenance and sold-only population limitations from Phase 1 remain. No inspection/document features were enabled without confirmation.

An initial fit failed before any candidate completed because the evaluation metric lacked matching quantile levels. Search plan 1.0.1 supplies those levels; the candidate grid and data did not change. The failed attempt's lock is preserved in `reports/initial_metric_attempt_lock.json`.
