"""Native CatBoost SHAP for the output slot selected as the row median."""
import numpy as np
from catboost import Pool
from frozen_valuation import prepare, FEATURES, CATEGORICAL

LABELS={'customer_branch':'Branch','customer_region':'Region','customer_state':'State','pincode_tier':'Location tier',
        'asset_variant':'Variant','asset_model':'Model','asset_fuel_type':'Fuel',
        'asset_cost_at_disbursal':'Original asset cost','months_since_agreement_at_seizure':'Months since agreement'}

def explain(valuator, frame):
    x=prepare(frame);model=valuator.model.model
    raw=np.asarray(model.predict(x,thread_count=4),dtype=float)
    slot=int(np.argsort(raw[0],kind='stable')[1])
    shap=np.asarray(model.get_feature_importance(Pool(x,cat_features=CATEGORICAL),type='ShapValues',thread_count=4),dtype=float)
    if shap.shape!=(1,3,len(FEATURES)+1):raise ValueError('Unsupported SHAP shape')
    contributions=shap[0,slot,:-1];base=float(shap[0,slot,-1])
    reconstruction=base+float(contributions.sum())
    if not np.isfinite(shap).all() or abs(reconstruction-float(raw[0,slot]))>.01:
        raise ValueError('SHAP additivity check failed')
    rows=[{'feature':k,'label':LABELS[k],'contribution_inr':float(v)} for k,v in zip(FEATURES,contributions)]
    top=sorted(rows,key=lambda r:abs(r['contribution_inr']),reverse=True)[:3]
    return {'method':'Native CatBoost SHAP','selected_output_slot':slot,'base_value_inr':base,
            'raw_median_inr':float(raw[0,slot]),'displayed_median_inr':max(0,float(raw[0,slot])),
            'reconstruction_error_inr':abs(reconstruction-float(raw[0,slot])),
            'contributions':rows,'top_three':top,
            'note':'Contributions explain the selected raw model output relative to its SHAP reference. They are associations, not causal effects or explanations of interval width.',
            'sentences':[f"{r['label']}: {r['contribution_inr']:+,.0f} INR contribution relative to the model reference." for r in top]}
