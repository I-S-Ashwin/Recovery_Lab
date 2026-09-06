# Phase 6 — future value assumptions and portfolio stress

This phase implements reproducible scenario calculations, not validated 12/24/36-month forecasts. The original workbook remains unchanged. The 583-case historical bridge uses saved Phase 4 estimates and Phase 5 liquidation exposures from that workbook; three separate fictional assets demonstrate future lending decisions. No final-test outcomes were used.

## Method and boundaries

Projected gross value = reference value × elapsed-month depreciation factor × common market multiplier. Elapsed months start at the supplied valuation date; they are not manufacture age. Factors are linearly interpolated through month 42, and later requests fail explicitly. Anchors are 1.00 at month 0, 0.80 at 12, 0.65 at 24, 0.50 at 36 and 0.45 at 42. These are demonstration assumptions, not fitted depreciation rates.

Base/adverse/severe market multipliers are 1.00/0.90/0.80; fictional-book recovery costs are ₹3,000/₹4,000/₹6,000 and delays 0/1/3 months. A common shock applies to every asset. There are no estimated probabilities for these scenarios. The scenario spread is not a confidence interval; Phase 4 conformal coverage does not extend to these future values.

## Example projected values: fictional asset A

| Scenario | Month 12 downside / median | Month 24 downside / median | Month 36 downside / median |
|---|---:|---:|---:|
| base | ₹56,000 / ₹68,000 | ₹45,500 / ₹55,250 | ₹35,000 / ₹42,500 |
| adverse | ₹50,400 / ₹61,200 | ₹40,950 / ₹49,725 | ₹31,500 / ₹38,250 |
| severe | ₹44,800 / ₹54,400 | ₹36,400 / ₹44,200 | ₹28,000 / ₹34,000 |

## Fixed fictional book stress

The same existing loans are held fixed in every scenario. At each checkpoint, all assets are assumed to default after the scheduled payments; balances freeze until recovery. No default interest, missed-payment arrears or extra payments during recovery are assumed. This measures conditional shortfall, not expected credit loss. Each checkpoint is a separate scenario and must not be summed across time.

| Scenario | Default month | Exposure | Downside shortfall | Exposure-weighted ratio |
|---|---:|---:|---:|---:|
| base | 0 | ₹265,000.00 | ₹62,000.00 | 23.40% |
| base | 12 | ₹182,507.23 | ₹24,636.43 | 13.50% |
| base | 24 | ₹80,922.43 | ₹0.00 | 0.00% |
| base | 36 | ₹0.00 | ₹0.00 | N/A: no exposure |
| adverse | 0 | ₹265,000.00 | ₹89,380.00 | 33.73% |
| adverse | 12 | ₹182,507.23 | ₹44,252.23 | 24.25% |
| adverse | 24 | ₹80,922.43 | ₹916.04 | 1.13% |
| adverse | 36 | ₹0.00 | ₹0.00 | N/A: no exposure |
| severe | 0 | ₹265,000.00 | ₹121,880.00 | 45.99% |
| severe | 12 | ₹182,507.23 | ₹71,187.23 | 39.01% |
| severe | 24 | ₹80,922.43 | ₹14,522.43 | 17.95% |
| severe | 36 | ₹0.00 | ₹0.00 | N/A: no exposure |

Portfolio shortfall is the sum of each asset’s positive shortfall divided by total exposure. Surplus collateral on one loan cannot offset another loan’s deficit. Summed downside values are not a calibrated portfolio quantile.

## New offers under the same scenarios

These are separate hypothetical new applications, not modifications to the existing book. The Phase 5 engine is reused unchanged. Verification flags and income are fictional. No real application is approved.

| Asset | Scenario | Feasible candidates | Recommended principal | Term |
|---|---|---:|---:|---:|
| DEMO-A | base | 24 | ₹80,000 | 18 months |
| DEMO-B | base | 20 | ₹60,000 | 12 months |
| DEMO-C | base | 18 | ₹105,000 | 18 months |
| DEMO-A | adverse | 15 | ₹70,000 | 12 months |
| DEMO-B | adverse | 10 | ₹52,000 | 12 months |
| DEMO-C | adverse | 10 | ₹91,000 | 12 months |
| DEMO-A | severe | 0 | No feasible offer | — |
| DEMO-B | severe | 0 | No feasible offer | — |
| DEMO-C | severe | 0 | No feasible offer | — |

## Original-data historical price sensitivity

This is a descriptive stress of 583 sold calibration cases at different historical liquidation dates, not a current live portfolio. Estimates were calibrated on these cases; this is not independent validation. Costs stay fixed at ₹3,000 and no delay or future depreciation is applied here, to isolate price sensitivity. Recorded balances were known at liquidation, not necessarily at seizure.

| Price scenario | Recorded exposure | Downside shortfall | Weighted ratio |
|---|---:|---:|---:|
| base | ₹40,388,723.28 | ₹24,590,926.30 | 60.89% |
| adverse | ₹40,388,723.28 | ₹26,296,290.62 | 65.11% |
| severe | ₹40,388,723.28 | ₹28,025,942.82 | 69.39% |

## Reproduce and production handoff

Requires Python 3.10+ with no third-party packages. Keep phase1, phase4, phase5 and phase6 as sibling folders to regenerate the original-data bridge. From the phase6 folder run `python src/run_phase6.py`, then `python src/verify.py`. Projection and financial modules run standalone with the bundled configuration. Source hashes are recorded in source_lock.json; package_index.json identifies delivered files.

Before production: obtain longitudinal valuations with explicit asset age and observation dates; include unsold and performing populations; validate horizons on later untouched cohorts; confirm recovery expenses, delay distributions and repayment behavior; replace demonstration policy with approved rules; require verified income and obligations; and add authenticated API access, monitoring and audit retention. This phase is a tested POC component, not a production-approved credit decision system.

Next: Phase 7 API and dashboard. The frozen final evaluation remains reserved for Phase 9.
