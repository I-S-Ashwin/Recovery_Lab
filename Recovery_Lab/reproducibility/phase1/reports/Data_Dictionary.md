# Phase 1 data dictionary

Source: Analytics Case Study Dataset.xlsx, Sheet1. All 41 source columns plus 8 traceability/derived columns. Observed codes are not verified definitions.

| Source field | Canonical field | Type / unit | Definition | Seizure use | Origination use |
|---|---|---|---|---|---|
| Agmt Id | agreement_id | string / identifier | Agreement identifier; not a customer or vehicle identifier. | excluded from predictors: identifier | excluded from predictors: identifier |
| Cust Age | customer_age | number / years | Recorded customer age; observation date is not supplied. | excluded from core physical valuation | policy context only after units/timing confirmation |
| Cust Gender | customer_gender | string / code | Recorded gender category; audit only. | excluded from predictors: audit_only | excluded from predictors: audit_only |
| Cust Cibil Score | customer_cibil_score_raw | number / score/code | Source score preserved, including unresolved -1 code. | excluded from core physical valuation | policy context only after units/timing confirmation |
| Cust Employment Type | customer_employment_code | string / code | Recorded employment code; codebook not provided. | excluded from core physical valuation | policy context only after units/timing confirmation |
| Cust Net Salary | customer_net_salary_raw | number / INR; frequency unconfirmed | Recorded income amount; zero meaning and frequency unconfirmed. | excluded from core physical valuation | policy context only after units/timing confirmation |
| Coborrower Flag | coborrower_flag | string / code | Recorded co-borrower flag; Y/N retained. | excluded from core physical valuation | policy context only after units/timing confirmation |
| App Score Risk | application_risk_band | string / category | Application risk label; not a residual-risk outcome. | excluded from core physical valuation | policy context only after units/timing confirmation |
| Agmt Date | agreement_date | date / date | Agreement event date. | event anchor/calendar only if known | agreement date only; future seizure fields excluded |
| Seizure Date | seizure_date | date / date | Seizure event date; prediction-time anchor for recovery mode. | event anchor/calendar only if known | agreement date only; future seizure fields excluded |
| Sold Date | sold_date | date / date | Sale event date; earliest assumed label availability, not system receipt time. | excluded from predictors: future | excluded from predictors: future |
| Tenure | tenure_months | number / months; confirm | Recorded loan tenure; contractual interpretation needs confirmation. | policy/audit input only | policy input only; not core valuation feature |
| Cust Net IRR | customer_net_irr_raw | number / reported percent; basis unconfirmed | Reported net interest measure; do not treat automatically as nominal annual rate. | policy/audit input only | policy input only; not core valuation feature |
| Sold Date Month | sold_month_raw | number / month number | Redundant source sale month; reconcile with sold date. | excluded from predictors: future | excluded from predictors: future |
| Sold Date Year | sold_year_raw | number / year | Redundant source sale year; reconcile with sold date. | excluded from predictors: future | excluded from predictors: future |
| Seizure Date Month | seizure_month_raw | number / month number | Redundant source seizure month; reconcile with seizure date. | event anchor/calendar only if known | agreement date only; future seizure fields excluded |
| Seizure Date Year | seizure_year_raw | number / year | Redundant source seizure year; reconcile with seizure date. | event anchor/calendar only if known | agreement date only; future seizure fields excluded |
| Cust Branch | customer_branch | string / category | Recorded branch; historical assignment timestamp unavailable. | candidate; source timestamp not supplied | candidate; historical snapshot must be verified |
| Cust Region | customer_region | string / category | Business region code; not assumed to be a state. | candidate; source timestamp not supplied | candidate; historical snapshot must be verified |
| Cust State | customer_state | string / code | Recorded state code preserved without inferred remapping. | candidate; source timestamp not supplied | candidate; historical snapshot must be verified |
| Pincode Tier | pincode_tier | string / category | Provided settlement tier; full label retained. | candidate; source timestamp not supplied | candidate; historical snapshot must be verified |
| RC Availability | rc_availability | string / code | Registration certificate availability; observation time unverified. | exclude until meaning/availability confirmed | exclude future versions; require approval-time snapshot |
| Registration Flag | registration_flag | string / code | Registration status; observation time unverified. | exclude until meaning/availability confirmed | exclude future versions; require approval-time snapshot |
| Asset Disc Flag | asset_disc_flag | string / code | Binary source disc flag; exact business meaning unconfirmed. | exclude until meaning/availability confirmed | exclude future versions; require approval-time snapshot |
| Asset Alloy Flag | asset_alloy_flag | string / code | Binary source alloy flag; exact business meaning unconfirmed. | exclude until meaning/availability confirmed | exclude future versions; require approval-time snapshot |
| Asset Variant | asset_variant | string / category | Recorded vehicle variant. | candidate; source timestamp not supplied | candidate; historical snapshot must be verified |
| Asset Model | asset_model | string / category | Recorded vehicle model/segment label; levels are not assumed uniform. | candidate; source timestamp not supplied | candidate; historical snapshot must be verified |
| Asset Fuel Type | asset_fuel_type | string / category | Recorded propulsion category, EV/Petrol. | candidate; source timestamp not supplied | candidate; historical snapshot must be verified |
| Asset Cost At Disbursal | asset_cost_at_disbursal | number / INR | Recorded original asset cost. | candidate; source timestamp not supplied | candidate; historical snapshot must be verified |
| Loan Amount | loan_amount | number / INR | Original financed amount; policy input, not core physical valuation predictor. | policy/audit input only | policy input only; not core valuation feature |
| LTV | ltv | number / fraction | Loan amount divided by original asset cost; source value preserved. | policy/audit input only | policy input only; not core valuation feature |
| OS Balance At Liquidation | outstanding_balance_at_liquidation | number / INR | Recorded liquidation balance; unavailable at earlier decisions. | excluded from predictors: future | excluded from predictors: future |
| Asset Age Months At Seizure | asset_age_months_at_seizure_raw | number / 30-day months | Source age label; matches agreement-to-seizure elapsed time in this file; manufacture age unverified. | exclude raw duplicate; use explicitly named elapsed-agreement duration | excluded; future event |
| Months Spent In Yard | months_spent_in_yard_raw | number / 30-day months | Realized seizure-to-sale delay; future information at seizure. | excluded from predictors: future | excluded from predictors: future |
| Asset Bodycondition | asset_body_condition | string / code | Recorded body-condition code; mapping and inspection timestamp unconfirmed. | exclude until meaning/availability confirmed | exclude future versions; require approval-time snapshot |
| Asset Tyrecondition | asset_tyre_condition | string / code | Recorded tyre-condition code; mapping and inspection timestamp unconfirmed. | exclude until meaning/availability confirmed | exclude future versions; require approval-time snapshot |
| Asset Generalcondition | asset_general_condition | string / code | Recorded general-condition code; mapping and inspection timestamp unconfirmed. | exclude until meaning/availability confirmed | exclude future versions; require approval-time snapshot |
| Asset Enginecondition | asset_engine_condition | string / code | Recorded engine-condition code; mapping and inspection timestamp unconfirmed. | exclude until meaning/availability confirmed | exclude future versions; require approval-time snapshot |
| Asset Accident Flag | asset_accident_flag | string / code | Recorded accident flag; timing and history scope unconfirmed. | exclude until meaning/availability confirmed | exclude future versions; require approval-time snapshot |
| Traiffic Challan Amount | traffic_challan_amount | number / INR | Recorded traffic fine amount; original misspelling mapped, timing unconfirmed. | exclude until meaning/availability confirmed | exclude future versions; require approval-time snapshot |
| Target Sold Amount At Liquidation | sale_amount | number / INR | Observed gross liquidation sale amount; target only, costs not supplied. | excluded from predictors: target | excluded from predictors: target |
| (derived) | source_excel_row | integer / row number | Original worksheet row for traceability. | excluded from predictors: identifier | excluded from predictors: identifier |
| (derived) | customer_cibil_score_usable | number/null / score | Source score if nonnegative, otherwise null; no claim that -1 means no history. | excluded from core physical valuation | policy context only after units/timing confirmation |
| (derived) | cibil_special_code_flag | boolean / flag | True when source CIBIL is negative; original value retained. | excluded from core physical valuation | policy context only after units/timing confirmation |
| (derived) | customer_income_positive | number/null / INR; frequency unconfirmed | Source income only if positive; not verified monthly income. | excluded from core physical valuation | policy context only after units/timing confirmation |
| (derived) | income_nonpositive_flag | boolean / flag | True when recorded income is zero or negative. | excluded from core physical valuation | policy context only after units/timing confirmation |
| (derived) | months_since_agreement_at_seizure | number / 30-day months | (Seizure date - agreement date) in days divided by 30; not confirmed vehicle age. | candidate at seizure; elapsed agreement time only | excluded; future event |
| (derived) | realized_yard_days | integer / days | (Sold date - seizure date) in days; retrospective audit only. | excluded from predictors: future | excluded from predictors: future |
| (derived) | ltv_recomputed | number / fraction | Loan amount / asset cost; reconciliation and policy use only. | policy/audit input only | policy input only; not core valuation feature |
