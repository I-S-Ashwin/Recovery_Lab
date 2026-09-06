# Phase 4: uncertainty calibration

The frozen Phase 3 CatBoost model was calibrated using only the 583 operational calibration cases. Model weights, input features and final-test reservation are unchanged.

## Fitted interval adjustment

- Target central coverage: 80%.
- Calibration records: 583; finite-sample order statistic: 468 of 583.
- Expand each raw range by INR 1,859.21 on each side, flooring the lower endpoint at zero.
- The median prediction is unchanged. Adjusted endpoints are interval bounds, not individually calibrated P10/P90 values.
- Earliest version availability: 1 May 2026 under the sale-date arrival assumption. The inference wrapper rejects requests dated before this version was available.

## Diagnostics — interpret each row separately

| Evidence | Records | Raw coverage | Adjusted coverage | Raw mean width INR | Adjusted mean width INR |
|---|---:|---:|---:|---:|---:|
| Held-back static check; correction fitted on 408 other cases | 175 | 69.14% | 78.86% | 19,644 | 23,351 |
| Final correction on its own fitting records; NOT independent validation | 583 | 73.07% | 80.27% | 19,302 | 23,020 |

The internal diagnostic split was fixed by a seeded hash of agreement IDs before using labels: 70% fit and 30% check. It is not a random train/test split for model selection: the existing temporal model/cohort roles stay fixed. It is also not a prospective seizure-time test. No alpha, subgroup or correction rule was changed after seeing its result.
The final saved correction then used all 583 calibration cases, including the diagnostic check cases. Therefore that check does not validate the final refit independently. Its role is a limited diagnostic of the predeclared procedure within this selected population. Final forward-period performance remains reserved for Phase 9.

## Method

For each calibration sale y and the model's ordered lower/upper estimates, compute s=max(lower-y,y-upper,0). For n scores take the ceil((n+1)*0.8)-th smallest score without interpolation. Add that correction to the upper endpoint and subtract it from the lower endpoint, with a zero floor. This implementation expands only; it does not shrink initially over-wide intervals.
Conformal coverage theory requires assumptions such as exchangeability. These data are time-dependent, sold-only and incomplete for unsold seizures, so nominal coverage is not a guaranteed future or per-segment probability. A central 80% interval also does not establish 90% one-sided protection for its lower bound.

## Temporal validation limitation

Within the reserved calibration cohort, the largest number of labels observed before any calibration seizure is 2. With the predeclared minimum 200, 0 seizures support a genuine sequential calibration replay.
We therefore do not claim an operational online-validation result here. Sorting outcomes by sale date and using them to score earlier seizures would introduce hindsight. Phase 9 can evaluate the frozen May-available bundle on the reserved later seizure cohort, with its end-of-file follow-up limitation disclosed.

## Segment and population limits

One pooled correction is used. Segment coverage and widths are fitting diagnostics with sample counts, not segment guarantees. Sparse EV results are flagged. There are no unsold seizures or full-book default outcomes. These intervals concern eventual liquidation proceeds in the observed sample, not verified retail values, default probability or 12/24/36-month projections.

## Handoff

Use models/calibration.json with its exact bound model hash and src/calibrated.py. Replacing the point model invalidates the correction. Preserve this version for Phase 5 lending simulations and Phase 9 final evaluation. If making lower-tail risk probability claims later, add separately designed and validated one-sided calibration rather than reinterpreting this central interval.
Adaptive updating remains a future extension; no online algorithm or market-shift guarantee has been implemented.

## References

Conformalized Quantile Regression, Romano, Patterson and Candes (2019): https://arxiv.org/abs/1905.03222 . The implemented nonnegative score is an expansion-only variant.
Gibbs and Candes (2024), adaptive conformal inference under distribution shifts: https://www.jmlr.org/papers/v25/22-1218.html . This is context for a future extension, not a capability claimed for this fixed correction.
