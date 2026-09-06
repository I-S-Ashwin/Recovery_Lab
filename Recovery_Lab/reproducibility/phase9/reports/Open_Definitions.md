# Definitions to confirm with the data owner

These are recorded questions, not assertions about the data. Phase 1 preparation is complete without guessing the answers. Do not enable dependent features or business claims until the relevant question is answered.

| Priority | Question | Evidence / reason | Treatment until confirmed |
|---|---|---|---|
| High | Is the dataset simulated, anonymized or operational? What population and selection rules produced it? | Every row has a sale outcome; unsold seizures and performing loans are not represented. | Limit claims to observed liquidated assets; no population default model. |
| High | Does source asset age mean time since agreement, and were all vehicles new when financed? | All 15,000 age values match agreement-to-seizure days / 30. | Use the exact name months_since_agreement_at_seizure; do not assert manufacture age. |
| High | What does CIBIL -1 mean? Are there other special score codes? | 8,850 rows contain -1. | Preserve raw; usable score null; exclude customer score from core valuation. |
| High | When were condition, RC, registration, accident and challan fields recorded? | No per-field availability timestamps. | Exclude from default feature whitelist pending confirmation; allow only explicitly labelled later experiments. |
| High | What does salary represent: monthly income, annual income, household income or another quantity? What does zero mean? | 39 zero-income records; frequency undocumented. | Do not treat as verified monthly affordability input. Existing obligations must be supplied separately. |
| High | What rate convention does Cust Net IRR follow, and what exactly does tenure include? | Values and names alone do not establish nominal rate, annualization or repayment structure. | Preserve raw; no automatic conversion to EMI rate. |
| High | What does liquidation outstanding include? Is exposure at seizure available separately? | Some balances exceed original loans. | Retrospective descriptive use only; do not infer errors or default exposure dynamics. |
| Medium | What do G, A and P condition codes mean, and how are four inspections performed? | Four condition codes agree on 81.64% of rows. | Preserve categorical codes without inferred ordinal scores or an asset-health index. |
| Medium | What are official meanings of employment, branch/region/state and tier codes? | Source categories use business abbreviations and distinct region/state concepts. | Preserve codes; no guessed geographic or employment remapping. |
| Medium | Do disc/alloy flags refer to equipment, and are they fixed at origination? | Binary codes but no verified business dictionary. | Exclude from initial core; add only after confirmation. |
| Medium | When does the sale outcome arrive in the operational data system? | Sold date is an event date, not an arrival timestamp. | Phase 2 must document sold date as a proxy and optionally allow a reporting delay. |
| Medium | Are recovery expenses, other collections, unsold inventory and true vehicle/customer IDs available? | Needed for net recovery, censoring and entity-aware testing. | No economic-LGD, causal-profit or independent-vehicle claims. |
| Medium | Are high challan amounts and long yard delays valid? | Explicit row-level flags identify cases to inspect. | Retain them; no automatic cap, deletion or deduction from sale proceeds. |

Maintain answers as a versioned source-owner note. A plausible interpretation is not a confirmed definition.
