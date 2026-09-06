"""Frozen nonnegative conformal expansion and versioned inference wrapper."""
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from frozen_valuation import Valuator


def fit_correction(actual,quantiles,alpha=.2,min_count=200):
    y=np.asarray(actual,dtype=float);q=np.asarray(quantiles,dtype=float)
    if y.ndim!=1 or q.shape!=(len(y),3):raise ValueError('Actual/quantile dimensions differ')
    if not 0<alpha<1:raise ValueError('alpha must be between zero and one')
    if len(y)<min_count:raise ValueError('Insufficient calibration records')
    if not np.isfinite(y).all() or not np.isfinite(q).all():raise ValueError('Nonfinite calibration input')
    if (np.diff(q,axis=1)<0).any() or (q<0).any():raise ValueError('Ordered nonnegative quantiles required')
    if (y<=0).any():raise ValueError('Sale labels must be positive')
    rank=math.ceil((len(y)+1)*(1-alpha))
    if rank>len(y):raise ValueError('Insufficient records for finite conformal order statistic')
    scores=np.maximum.reduce([q[:,0]-y,y-q[:,2],np.zeros(len(y))])
    correction=float(np.sort(scores)[rank-1])
    return {'n':len(y),'alpha':alpha,'target_coverage':1-alpha,'rank_one_based':rank,'correction_inr':correction},scores


def expand(quantiles,correction):
    q=np.asarray(quantiles,dtype=float)
    if q.ndim!=2 or q.shape[1]!=3 or not np.isfinite(q).all():raise ValueError('Invalid quantile array')
    if (np.diff(q,axis=1)<0).any() or (q<0).any():raise ValueError('Ordered nonnegative quantiles required')
    if not math.isfinite(correction) or correction<0:raise ValueError('Correction must be finite and nonnegative')
    r=q.copy();r[:,0]=np.maximum(0,q[:,0]-correction);r[:,2]=q[:,2]+correction
    return r


class CalibratedValuator:
    def __init__(self,bundle):
        bundle=Path(bundle)
        self.calibration=json.loads((bundle/'calibration.json').read_text())
        path=bundle/'catboost_quantiles.cbm'
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest!=self.calibration['model_sha256']:raise ValueError('Calibration is bound to a different model')
        self.model=Valuator(path)

    def predict(self,features,as_of_date):
        when=date.fromisoformat(as_of_date)
        if when<date.fromisoformat(self.calibration['available_from']):
            raise ValueError('Calibration was unavailable at requested date; use an earlier version')
        q=self.model.predict(features)
        return expand(q,self.calibration['correction_inr'])
