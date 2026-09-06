# Phase 4 — uncertainty calibration

Start with `reports/Phase_4_Report.md`. The saved bundle contains the unchanged Phase 3 model and an actual fitted interval adjustment. Final-test outcomes remain unscored.

## Contents

- `models/calibration.json`: pooled correction, rank, sample count, alpha, version availability and bound model hash.
- `models/catboost_quantiles.cbm`: byte-for-byte copy of the selected Phase 3 model.
- `models/calibration_provenance.json`: calibration and diagnostic IDs, dates and reserved count.
- `models/base_feature_contract.json`: the underlying unchanged Phase 3 input/output contract; its base outputs are uncalibrated until the wrapper applies the correction.
- `configs/calibration_plan.json`: rule and diagnostic split fixed before using calibration labels.
- `calibration_lock.json`: frozen input/config/code hashes.
- `data/calibration_predictions.jsonl`: fitting scores and fitted endpoints for all calibration cases; these are not independent final-refit validation results.
- `data/diagnostic_split.jsonl`: ID-only diagnostic fit/check membership.
- `data/heldback_diagnostic_predictions.jsonl`: check-set results using the correction fitted only on the diagnostic fit subset.
- `reports/segment_diagnostics.json`: pooled-correction diagnostics by segment, with sample flags.
- `reports/forward_replay_feasibility.json`: why these calibration records cannot establish live seizure-time calibration performance.
- `reports/verification.json`: executed numerical and provenance checks.
- `src/`: repeatable calibration and versioned inference.

## Reproduce

Keep phase folders as siblings. Use the requirements already pinned in Phase 3; the identical list is supplied here. From `phase4/`, in an environment with those dependencies:

```text
python src/run_phase4.py --phase1 ../phase1 --phase2 ../phase2 --phase3 ../phase3 --output .
python src/verify.py --phase1 ../phase1 --phase2 ../phase2 --phase3 ../phase3 --output .
```

For application use, import `CalibratedValuator` from `src/calibrated.py`, load `models/`, and supply the exact nine-feature DataFrame plus an ISO `as_of_date`. Dates before 2026-05-01 are rejected because this calibration version used labels through April. The result is lower interval bound, unchanged median and upper interval bound. It is a central interval; do not reinterpret the lower bound as a guaranteed 90% one-sided recovery floor.

## What the diagnostic means

A seeded ID hash divides the existing operational calibration role into 408 fit cases and 175 held-back check cases. This is a static diagnostic, not a replacement for the frozen temporal model split or a prospective test. After the check, the unchanged procedure fits all 583 cases for the saved final correction. The check cases are therefore no longer independent of that saved refit.

No interval parameter was tuned after this diagnostic. Coverage on the final fitting records is explicitly labelled as fitting coverage. Validation on the reserved later seizure cohort belongs to Phase 9. There are too few prior labels inside the calibration period to claim a live sequential calibration backtest.

Do not modify or retrain the underlying model without producing a new compatible correction and version. For new environments, install dependencies in a normal project virtual environment. The Codex run reused Phase 3's dependencies; its Windows network-enabled execution account was needed to access that installation.
