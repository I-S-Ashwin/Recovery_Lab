# Phase 2: baseline and time-based splits

Start with `reports/Phase_2_Report.md`. This phase implements the valuation baseline and freezes cohort membership for later model comparison. It does not train CatBoost, calibrate intervals, or score the final test.

## Contents

- `configs/split_plan.json`: cutoffs, group minimum, fixed duration bins and evaluation rules, saved before baseline fitting.
- `split_lock.json`: input/config hashes frozen before the first run; a changed plan needs a new output version.
- `data/*_split_manifest.jsonl`: one role per agreement, with dates and exclusion reasons; no sale target values.
- `data/*_tuning_predictions.jsonl`: development predictions, actual tuning outcomes and baseline fallback provenance.
- `models/B0_median_ratio.json`: fitted training-only ratio statistics and group counts, no executable pickle.
- `reports/baseline_metrics.json`: baseline and global-ratio benchmark metrics on tuning roles only.
- `reports/segment_metrics.json`: model/fuel/region results with small-sample flags.
- `reports/label_delay_sensitivity.json`: counts under assumed 0/7/30-day outcome reporting delays.
- `reports/verification.json`: executed leakage, boundary, numeric and artifact checks.
- `src/`: repeatable implementation and verification.

## Reproduce

Keep `phase1/` and `phase2/` as sibling folders. Use the tested versions in `requirements.txt` (Python 3.12.14 used). From `phase2/`:

```text
python src/run_phase2.py --phase1 ../phase1 --output .
python src/verify_phase2.py --phase1 ../phase1 --output .
```

To run into a different location, copy the package there first so the plan and source modules exist. The runner refuses changed locked inputs or plans. Audit scripts do not modify Phase 1.

## Rules for later phases

Use the nine explicitly selected Phase 1 candidate features, not the complete canonical table. Original inspection and document flags remain excluded pending timestamp/definition confirmation. Duration means time since agreement, not confirmed manufacture age.

The operational protocol is the primary seizure-time development experiment. Its tuning sample includes only outcomes available by the tuning cutoff and excludes delayed sales, so it is selected toward sufficiently fast recoveries. The retrospective protocol is an additional sold-cohort experiment, not proof of operational performance.

Do not compare a CatBoost metric from one protocol against a baseline metric from the other. Do not use calibration or final-test errors to choose model settings. The Phase 1 full-file audit is disclosed; this holdout is reserved for modelling, not an external unseen sample.

The final-test outcomes remain in the original Phase 1 dataset for provenance. Reservation is a recorded workflow constraint, not an access-control system. Phase 2 exports and metrics score only tuning IDs.

Feature availability and true customer/vehicle independence are not certified because per-field timestamps and entity IDs are unavailable. These limits remain in force even though the implemented leakage tests pass.
