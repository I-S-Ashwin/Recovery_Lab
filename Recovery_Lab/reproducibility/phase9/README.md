# Phase 9 — final evaluation and documentation

Start with reports/Phase_9_Report.md. Model_Card.md describes intended use, provenance, inputs, limitations and operation. Data_Dictionary.md accounts for all 49 canonical fields; Open_Definitions.md preserves unresolved source questions. Final_Evaluation.png is a standalone figure suitable for the final presentation.

The primary evaluation contains 1,244 reserved operational cases. Model MAE is ₹7,051.86 versus ₹8,342.91 for B0, a 15.47% reduction. Calibrated coverage is 80.47% overall, but only 61.11% among 36 EV cases. The final report includes mean interval width, uncertainty assumptions, segment results and large errors.

The secondary 1,835-case cohort includes all primary cases and 591 earlier seizures. It is a retrospective diagnostic, not independent real-time validation. Do not add the cohort counts together or describe the tuning improvement as the final-test result.

## Contents

- configs/evaluation_lock.json: protocol and source hashes committed before scoring.
- models/: exact frozen model, calibration, baseline and feature contract.
- data/: predictions and observed outcomes for the two final cohorts.
- reports/final_metrics.json: full numerical evidence and execution timestamps.
- reports/*_segments.json: all predeclared segment analyses, with counts and small-sample flags.
- reports/diagnostic_examples.json: cases selected by the predeclared diagnostic rule.
- reports/verification.json: 115 independent numerical/provenance checks.
- src/: evaluation, verification, documentation and packaging code.

## Reproduce

Use Python 3.12 and the pinned requirements.txt. Keep Phase 1, 2, 3, 4 and 8 as sibling folders; the scripts read their frozen source artifacts and reports. From this phase9 folder:

```powershell
python src/evaluate.py
python src/verify.py
python src/document.py
python src/package.py
```

Evaluation does not retrain or recalibrate. Repeated executions reproduce numerical results but update execution timestamps and derived file hashes. Do not overwrite the evaluation lock or regenerate it to accept an unexplained source change.

The final-test outcomes are now inspected. Any model or calibration change informed by them requires a new experiment and a new untouched cohort. A future re-score of these same cases is not a fresh holdout evaluation.

The Phase 8 app remains a frozen local deployment with its archived development-evidence view. This Phase 9 package is the authoritative final evidence; submission/dashboard evidence integration belongs to Phase 10. No production-lending approval, validated future depreciation or default probability is claimed.

Keep this package private: it includes source-derived agreement outcomes and fitted artifacts. It does not include the raw workbook or full canonical source file.
