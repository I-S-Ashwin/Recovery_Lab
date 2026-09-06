# Final data dictionary

All 41 source fields and 8 derived/traceability fields are accounted for. Definitions remain those verified in Phase 1; unresolved meanings have not been guessed. “Used” below identifies the nine inputs in the frozen model, not independent verification of their historical availability.

| Canonical field | Source | Type / unit | Used by model | Definition |
|---|---|---|---|---|
| agreement_id | Agmt Id | string / identifier | No | Agreement identifier; not a customer or vehicle identifier. |
| customer_age | Cust Age | number / years | No | Recorded customer age; observation date is not supplied. |
| customer_gender | Cust Gender | string / code | No | Recorded gender category; audit only. |
| customer_cibil_score_raw | Cust Cibil Score | number / score/code | No | Source score preserved, including unresolved -1 code. |
| customer_employment_code | Cust Employment Type | string / code | No | Recorded employment code; codebook not provided. |
| customer_net_salary_raw | Cust Net Salary | number / INR; frequency unconfirmed | No | Recorded income amount; zero meaning and frequency unconfirmed. |
| coborrower_flag | Coborrower Flag | string / code | No | Recorded co-borrower flag; Y/N retained. |
| application_risk_band | App Score Risk | string / category | No | Application risk label; not a residual-risk outcome. |
| agreement_date | Agmt Date | date / date | No | Agreement event date. |
| seizure_date | Seizure Date | date / date | No | Seizure event date; prediction-time anchor for recovery mode. |
| sold_date | Sold Date | date / date | No | Sale event date; earliest assumed label availability, not system receipt time. |
| tenure_months | Tenure | number / months; confirm | No | Recorded loan tenure; contractual interpretation needs confirmation. |
| customer_net_irr_raw | Cust Net IRR | number / reported percent; basis unconfirmed | No | Reported net interest measure; do not treat automatically as nominal annual rate. |
| sold_month_raw | Sold Date Month | number / month number | No | Redundant source sale month; reconcile with sold date. |
| sold_year_raw | Sold Date Year | number / year | No | Redundant source sale year; reconcile with sold date. |
| seizure_month_raw | Seizure Date Month | number / month number | No | Redundant source seizure month; reconcile with seizure date. |
| seizure_year_raw | Seizure Date Year | number / year | No | Redundant source seizure year; reconcile with seizure date. |
| customer_branch | Cust Branch | string / category | Yes | Recorded branch; historical assignment timestamp unavailable. |
| customer_region | Cust Region | string / category | Yes | Business region code; not assumed to be a state. |
| customer_state | Cust State | string / code | Yes | Recorded state code preserved without inferred remapping. |
| pincode_tier | Pincode Tier | string / category | Yes | Provided settlement tier; full label retained. |
| rc_availability | RC Availability | string / code | No | Registration certificate availability; observation time unverified. |
| registration_flag | Registration Flag | string / code | No | Registration status; observation time unverified. |
| asset_disc_flag | Asset Disc Flag | string / code | No | Binary source disc flag; exact business meaning unconfirmed. |
| asset_alloy_flag | Asset Alloy Flag | string / code | No | Binary source alloy flag; exact business meaning unconfirmed. |
| asset_variant | Asset Variant | string / category | Yes | Recorded vehicle variant. |
| asset_model | Asset Model | string / category | Yes | Recorded vehicle model/segment label; levels are not assumed uniform. |
| asset_fuel_type | Asset Fuel Type | string / category | Yes | Recorded propulsion category, EV/Petrol. |
| asset_cost_at_disbursal | Asset Cost At Disbursal | number / INR | Yes | Recorded original asset cost. |
| loan_amount | Loan Amount | number / INR | No | Original financed amount; policy input, not core physical valuation predictor. |
| ltv | LTV | number / fraction | No | Loan amount divided by original asset cost; source value preserved. |
| outstanding_balance_at_liquidation | OS Balance At Liquidation | number / INR | No | Recorded liquidation balance; unavailable at earlier decisions. |
| asset_age_months_at_seizure_raw | Asset Age Months At Seizure | number / 30-day months | No | Source age label; matches agreement-to-seizure elapsed time in this file; manufacture age unverified. |
| months_spent_in_yard_raw | Months Spent In Yard | number / 30-day months | No | Realized seizure-to-sale delay; future information at seizure. |
| asset_body_condition | Asset Bodycondition | string / code | No | Recorded body-condition code; mapping and inspection timestamp unconfirmed. |
| asset_tyre_condition | Asset Tyrecondition | string / code | No | Recorded tyre-condition code; mapping and inspection timestamp unconfirmed. |
| asset_general_condition | Asset Generalcondition | string / code | No | Recorded general-condition code; mapping and inspection timestamp unconfirmed. |
| asset_engine_condition | Asset Enginecondition | string / code | No | Recorded engine-condition code; mapping and inspection timestamp unconfirmed. |
| asset_accident_flag | Asset Accident Flag | string / code | No | Recorded accident flag; timing and history scope unconfirmed. |
| traffic_challan_amount | Traiffic Challan Amount | number / INR | No | Recorded traffic fine amount; original misspelling mapped, timing unconfirmed. |
| sale_amount | Target Sold Amount At Liquidation | number / INR | No | Observed gross liquidation sale amount; target only, costs not supplied. |
| source_excel_row | None | integer / row number | No | Original worksheet row for traceability. |
| customer_cibil_score_usable | None | number/null / score | No | Source score if nonnegative, otherwise null; no claim that -1 means no history. |
| cibil_special_code_flag | None | boolean / flag | No | True when source CIBIL is negative; original value retained. |
| customer_income_positive | None | number/null / INR; frequency unconfirmed | No | Source income only if positive; not verified monthly income. |
| income_nonpositive_flag | None | boolean / flag | No | True when recorded income is zero or negative. |
| months_since_agreement_at_seizure | None | number / 30-day months | Yes | (Seizure date - agreement date) in days divided by 30; not confirmed vehicle age. |
| realized_yard_days | None | integer / days | No | (Sold date - seizure date) in days; retrospective audit only. |
| ltv_recomputed | None | number / fraction | No | Loan amount / asset cost; reconciliation and policy use only. |

## Availability and policy contract

Every live model input requires an available-on date no later than the requested seizure decision date. The dataset lacks field-level timestamps, so the retrospective feature-availability assumption is unverified. Sold date is only a proxy for label availability. See Open_Definitions.md for the outstanding data-owner questions.

CIBIL -1 is preserved in the raw score and converted to null only in the usable-score derived view, without claiming it means no credit history. Source salary is not verified monthly income. Loan rate and liquidation balance conventions remain unresolved. Source age is represented by the derived agreement-to-seizure duration, not a manufacture-age claim.

The machine-readable configs/data_dictionary.json includes observed codes, model-exclusion purposes and unresolved definitions. Source codes are not a verified business codebook.
