# TVS Credit POC — Phase 1

Phase 1 implements the data audit and preparation specified in the POC blueprint. Start with [the audit report](reports/Phase_1_Report.md), then read [the data dictionary](reports/Data_Dictionary.md) and [definitions to confirm](reports/Open_Definitions.md).

## What is delivered

- `data/canonical_records.jsonl`: all retained records, 41 canonical source fields plus 8 traceability/derived fields. Original raw CIBIL and income values are preserved alongside safer derived views.
- `data/source_values.jsonl`: original source cell values, with worksheet row references. This preserves values, not Excel formatting.
- `data/quarantined_records.jsonl`: hard-rule exclusions; an empty file means no exclusions.
- `reports/row_issues.jsonl`: review and exclusion reasons keyed to agreement and source row. Multiple flags can refer to the same row.
- `reports/quality_checks.json`: every executed data-quality rule and count, including zero-finding checks.
- `reports/column_profiles.json`, `monthly_profile.json`, `segment_profile.json`: descriptive profiles of the entire supplied file.
- `configs/data_dictionary.json`: structured field definitions, source mappings, observed codes and availability rules.
- `configs/feature_policy.json`: explicit candidate feature lists and exclusions.
- `reports/verification.json`: results of full-cell and derived-value verification.
- `manifest.json`: hashes, versions, row reconciliation and source provenance.
- `src/audit.py` and `src/verify.py`: repeatable audit and independent verification.

## Reading the data

JSON Lines contains one record per line. Numbers, booleans and missing values retain their types. Dates are ISO strings and should be explicitly parsed. It can be loaded with Python using `pandas.read_json(path, lines=True)` or the standard `json` module.

The supplied runtime has no Parquet engine. JSON Lines is used instead of installing additional dependencies; it is suitable for this 15,000-row POC. A later phase may add Parquet without changing the canonical schema.

Do not use the entire canonical table as a training matrix: it deliberately includes target, audit and future fields for traceability. Select only an explicit mode-specific feature list. The initial lists are POC candidates; the workbook does not prove per-field historical availability.

## Reproducing Phase 1

Use Python 3.11+ with the package versions recorded in `manifest.json` and `requirements.txt`. From this folder:

```text
python src/audit.py --source "PATH/Analytics Case Study Dataset.xlsx" --output "PATH/phase1_rebuilt"
python src/verify.py --source "PATH/Analytics Case Study Dataset.xlsx" --output "PATH/phase1_rebuilt"
```

The verification script expects the audit script at `src/audit.py` within the package; copy `src/` to `phase1_rebuilt/` before these commands. Alternatively run the commands with `--output .` to refresh this package's generated data and reports. Source files are opened read-only. The output dataset is deterministic; manifest generation time changes on a fresh run.

## Completion and remaining work

The source has 15,000 rows, 41 columns and 15,000 unique agreements. All rows were retained. There are no blank source cells, exact duplicate records excluding ID, or invalid event orderings. Review flags record semantic and unusual-value issues; they do not mean the full row is unusable.

The source age field matches elapsed agreement time in all rows. No manufacture-age assumption has been introduced. Customer score `-1` and zero income remain traceable, with null-safe derived views. Long yard durations and high fines/balances are retained for review.

Phase 2 can proceed with a conservative valuation feature set and explicit timestamp assumptions. It must create temporal splits, test for leakage and establish a baseline. No split has been fitted or frozen, and no model has been trained in Phase 1. Field-definition questions remain in the open-definitions register; they do not prevent the completed data preparation from being used conservatively.

Keep the package private: it contains the supplied customer/loan data. Public demo examples should use synthetic records.
