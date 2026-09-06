# Recovery Lab: five-minute demonstration

Timing includes clicks and short pauses. Practice aloud once before presenting. Open the local app at http://127.0.0.1:8078/ and have the final presentation ready. The default vehicle and lending reference are fictional. The evidence tab reports the measured holdout.

| Time | Action | Suggested narration |
|---|---|---|
| 0:00–0:40 | Show cover, then app | “Recovery Lab supports a recovery decision: what could a seized vehicle sell for, and what lending offers remain feasible under explicit assumptions? We used the supplied 15,000-record workbook. We kept the source unchanged and separated observed evidence from policy scenarios.” |
| 0:40–1:30 | Valuation & lending: keep default inputs, click Estimate recovery value | “This fictional input returns a median of about INR 34,511. The interval communicates uncertainty around sale value. The explanation shows model-specific SHAP contributions, which are associations. Months since agreement is not vehicle manufacture age. Dates and input availability are checked before inference.” |
| 1:30–2:25 | Lending: select Phase 6 fictional example A, compare base, adverse, severe | “For a controlled comparison, these clearly labeled anchors are hand-authored. We evaluate 35 offers using a 40% payment-to-income cap and a 20% downside shortfall cap. Base yields INR 80,000 for 18 months, adverse INR 70,000 for 12 months, and severe no feasible offer. The ranking and rejected constraints remain inspectable. This is a simulation, and future depreciation is an assumption.” |
| 2:25–3:15 | Portfolio stress: month zero, severe, Run portfolio stress | “Now we hold the existing three-loan book fixed. With every loan defaulting at this checkpoint, exposure is INR 265,000 and severe downside shortfall is INR 121,880, or 46%. We sum asset shortfalls without using surplus collateral to erase another loan’s loss. This measures conditional severity. It does not estimate default probability or expected loss.” |
| 3:15–4:10 | Model evidence: show final MAE, coverage and EV note | “On 1,244 operational holdout cases, MAE fell from INR 8,343 to INR 7,052, a 15.5% reduction. The model and calibration stayed frozen. Pooled interval coverage is 80.5%, with mean width INR 23,146. EV coverage is only 61.1% on 36 cases. We show this limitation because a pooled metric cannot justify segment reliability.” |
| 4:10–5:00 | Refresh audit trail, then final deck slide | “The local journal records outcomes across restarts without retaining raw request values. Primary model failure provides a review-only baseline and removes the interval. Our next pilot gates are prospective outcomes including unsold vehicles, verified timestamps, more EV evidence, approved policy and access controls. We deliver the working local app, frozen model, executed notebook and documentation.” |

## Before the session

1. Add your actual team and presenter names to the cover if required by the organizer. Check the organizer’s current upload rules and deadline.
2. Run the app before presenting and keep the laptop powered. Keep the default decision date at or after 1 May 2026.
3. Choose fictional reference A for the offer comparison. The default model-derived reference can legitimately return no feasible offer.
4. Keep internet-independent copies of the presentation and executed notebook. The local model does not call a cloud API.
5. Rehearse the spoken script with a timer. The technical replay verifies API outputs; it does not substitute for practicing clicks or speaking.

## If something fails during the demonstration

Use the executed notebook and presentation to show recorded evidence. Describe them as saved outputs, not a live request. Do not alter the model or loosen constraints on stage. If the app is unavailable, use the documented local startup steps. Avoid deliberate failure injection into the running presentation service.

## Likely judge questions

**Why CatBoost?** The dataset is structured and contains many categorical inputs. The frozen selection used six trials and a separate tuning period. The main evidence is the final 15.5% MAE improvement over a meaningful median-ratio baseline, not a claim that CatBoost always wins.

**What is innovative here?** The contribution is the integrated decision workflow: time-based evidence controls, quantified uncertainty, explicit offer constraints, consistent loan-book stress and auditable local serving. CatBoost and conformal methods are established work credited in the presentation.

**Is it production ready?** It is a tested local POC with operational safeguards. Production underwriting still needs approved policy, access controls, prospective monitoring, verified input timestamps and further segment validation.

**Can you forecast 12, 24 and 36 months?** The app projects those horizons using explicit depreciation factors. The supplied data does not validate those future paths. We label them assumptions.

**What failed?** EV coverage was 22 of 36 cases. The largest observed error, ASSET_1161, sold for INR 15,000 against a median estimate near INR 61,100. The dataset does not establish the cause; we would investigate the source record.

**Is 80.5% an accuracy score?** It is the fraction of outcomes inside the interval. MAE measures point error. The interval is broad and its coverage is not guaranteed for each subgroup or later time period.

**Did you use the original dataset?** Yes. The canonical records come from the original Analytics Case Study Dataset.xlsx. The audit matched 615,000 source cells, retained all 15,000 rows and preserved the original workbook unchanged.

**Does the larger retrospective result confirm the model independently?** No. Its 1,835 cases include the 1,244 operational cases. The extra earlier seizures make it a retrospective diagnostic, not an independent real-time test.
