"""Strict model feature contract and identical training/inference normalization."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from catboost import CatBoostRegressor

FEATURES=['customer_branch','customer_region','customer_state','pincode_tier','asset_variant',
          'asset_model','asset_fuel_type','asset_cost_at_disbursal','months_since_agreement_at_seizure']
CATEGORICAL=FEATURES[:7]
NUMERIC=FEATURES[7:]


def prepare(frame):
    extras=set(frame.columns)-set(FEATURES)
    missing=set(FEATURES)-set(frame.columns)
    if extras or missing:
        raise ValueError(f'Feature contract mismatch; extra={sorted(extras)}, missing={sorted(missing)}')
    x=frame.loc[:,FEATURES].copy()
    for c in CATEGORICAL:
        x[c]=x[c].map(lambda v:'__MISSING__' if pd.isna(v) or not str(v).strip() else str(v).strip())
    for c in NUMERIC:
        x[c]=pd.to_numeric(x[c],errors='coerce')
        if not np.isfinite(x[c].to_numpy(dtype=float)).all():raise ValueError('Nonfinite numeric feature: '+c)
    if x.asset_cost_at_disbursal.le(0).any():raise ValueError('Original asset cost must be positive')
    if x.months_since_agreement_at_seizure.lt(0).any():raise ValueError('Elapsed agreement duration cannot be negative')
    return x


def ordered(raw):
    a=np.asarray(raw,dtype=float)
    if a.ndim!=2 or a.shape[1]!=3 or not np.isfinite(a).all():raise ValueError('Invalid model output')
    return np.maximum(np.sort(a,axis=1),0)


class Valuator:
    def __init__(self,model_path):
        self.model=CatBoostRegressor()
        self.model.load_model(str(model_path))
        if self.model.feature_names_!=FEATURES:raise ValueError('Saved model feature names differ from contract')

    def predict(self,features):
        raw=self.model.predict(prepare(features),thread_count=4)
        return ordered(raw)
