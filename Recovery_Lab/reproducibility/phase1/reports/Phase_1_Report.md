# Phase 1: dataset audit and preparation

Source: Analytics Case Study Dataset.xlsx, Sheet1. This report describes the complete supplied file, not model performance. Source workbook unchanged.

## Outcome

- 15,000 source rows, 41 source columns, 15,000 unique agreement IDs.
- 15,000 rows retained; 0 quarantined; 9,680 distinct rows have one or more review flags.
- 0 blank source cells. Special codes and zero income still require semantic handling.
- Canonical records are provided as JSON Lines, with one object per agreement and explicit numeric/null/boolean types. No rows are silently imputed, capped or deduplicated.
- Modelling, chronological split assignment and model fitting belong to Phase 2 onward and have not been performed.

## Important findings

1. **Age definition:** 15,000/15,000 reported age values equal (seizure date - agreement date)/30 within 1e-8 months. Use `months_since_agreement_at_seizure` for this quantity. It is not confirmed manufacture age.
2. **Realized yard duration:** 15,000/15,000 yard values equal sale-minus-seizure days/30. This is unavailable at seizure and must stay out of the seizure model.
3. **CIBIL:** 8,850 records (59.0%) have a negative special code. Preserve the raw code and use null in the derived usable view. Its business meaning remains unresolved.
4. **Income:** 39 records contain zero/negative recorded income. These cannot establish affordability. Income frequency and existing obligations are missing.
5. **EV sample:** 306 EV records (2.04%); use pooled estimates initially and disclose small segment samples.
6. **LTV reconciliation:** 15,000/15,000 supplied values match loan/original-cost within 1e-6. Retain fraction units.
7. **Condition patterns:** all four codes agree in 12,246 records (81.6%). Investigate coding/inspection practice; this alone does not establish fabricated data.
8. **Population:** observed liquidation sales exclude the performing-loan population and unsold seizures. Default probability, full credit LGD and causal policy uplift cannot be identified from this file alone.
9. **Time coverage:** sale outcomes span 2025-04-08 through 2026-07-31; long-horizon forecasts require additional evidence.

## Quality checks with findings

| Rule | Rows | Handling |
|---|---:|---|
| cibil_negative_special_code | 8,850 | review: Unresolved negative source code; usable score set null |
| income_nonpositive | 39 | review: Affordability unavailable without verified positive income and frequency |
| yard_over_six_months | 22 | review: Operational investigation threshold only; genuine long delays retained |
| challan_exceeds_sale | 64 | review: Verify fine amount and recoverability; do not subtract automatically |
| liquidation_balance_exceeds_loan | 2,276 | review: Could include arrears/charges; confirm balance definition |
| sale_exceeds_original_cost | 3 | review: Verify valid outcome; do not cap target |

The complete rule list, including zero-findings checks, is in quality_checks.json. Flags overlap; never add flagged counts to estimate unique affected agreements. Review flags do not automatically quarantine a vehicle.

## Monthly sale coverage

| Sale month | Records | Median sale (INR) | Median realized yard months |
|---|---:|---:|---:|
| 2025-04 | 1,207 | 43,000 | 1.37 |
| 2025-05 | 1,101 | 45,000 | 1.37 |
| 2025-06 | 1,153 | 45,000 | 1.43 |
| 2025-07 | 1,159 | 47,000 | 1.43 |
| 2025-08 | 1,139 | 46,000 | 1.53 |
| 2025-09 | 1,022 | 44,000 | 1.60 |
| 2025-10 | 982 | 41,750 | 1.53 |
| 2025-11 | 995 | 42,000 | 1.57 |
| 2025-12 | 1,009 | 40,000 | 1.53 |
| 2026-01 | 931 | 41,000 | 1.57 |
| 2026-02 | 948 | 42,000 | 1.50 |
| 2026-03 | 797 | 41,500 | 1.33 |
| 2026-04 | 722 | 43,000 | 1.37 |
| 2026-05 | 458 | 42,000 | 1.45 |
| 2026-06 | 673 | 44,000 | 1.30 |
| 2026-07 | 704 | 44,225 | 1.33 |

Monthly medians are descriptive and mix-dependent; they are not a quality-adjusted market price index.

## Cleaning performed

- Assigned stable canonical field names and retained source worksheet row references.
- Preserved all source field values in a separate value snapshot. Dates are serialized as ISO timestamps; Excel display formatting is not part of that snapshot.
- Converted canonical flags/categories to strings and numeric/date fields to typed values; stripped surrounding whitespace only.
- Preserved raw CIBIL/income values; appended null-safe derived views and explicit flags without guessing meanings.
- Derived agreement elapsed time, realized yard days and an independently recomputed LTV.
- Stored field-level policy, row-level issues, full profiles and file hashes.
- Performed no target-based imputation, category pooling, outlier deletion, train/test split or model fitting.

## Questions and Phase 2 handoff

Read Open_Definitions.md for the unresolved source-owner questions. Safe preparatory work can continue with the explicit feature whitelist; inspection/document flags stay excluded until timing is verified.
Phase 2 must construct temporal splits with label availability and keep repeated aggregates/transforms inside training folds. Do not pass the entire canonical audit table to a model.
The proposed core uses original cost, vehicle/model/fuel and location plus elapsed agreement time at seizure. Their immutable/historical status is still an explicit POC assumption, not verified per-field provenance.

## Verification

The companion verification script checks source hashes, row counts, source-to-canonical value preservation, derived calculations, issue reconciliation and forbidden feature exclusion. verification.json records the executed result. No prediction accuracy is asserted.
