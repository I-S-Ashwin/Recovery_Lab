"""Training-only median-ratio baseline, explicit input contract, serializable state."""
import bisect
import json
import math
from pathlib import Path
import pandas as pd


FEATURES = ['customer_branch','customer_region','customer_state','pincode_tier',
            'asset_variant','asset_model','asset_fuel_type','asset_cost_at_disbursal',
            'months_since_agreement_at_seizure']
REQUIRED = ['asset_model','asset_fuel_type','asset_cost_at_disbursal','months_since_agreement_at_seizure']


def duration_bin(value, lower_bounds):
    if not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:
        raise ValueError('Elapsed agreement duration must be finite and nonnegative')
    return lower_bounds[bisect.bisect_right(lower_bounds,value)-1]


def select_features(records):
    """An explicit projection: audit/target columns are deliberately not predictors."""
    missing=set(FEATURES)-set(records.columns)
    if missing:raise ValueError('Missing feature columns: '+str(sorted(missing)))
    return records.loc[:,FEATURES].copy()


def validate_inputs(frame):
    extra=set(frame.columns)-set(FEATURES)
    if extra:raise ValueError('Forbidden or unknown predictor columns: '+str(sorted(extra)))
    missing=set(REQUIRED)-set(frame.columns)
    if missing:raise ValueError('Missing baseline predictors: '+str(sorted(missing)))
    for x in frame.asset_cost_at_disbursal:
        if not isinstance(x,(int,float)) or not math.isfinite(x) or x<=0:
            raise ValueError('Original cost must be positive and finite')
    for name in ['asset_model','asset_fuel_type']:
        if frame[name].isna().any():raise ValueError('Missing '+name)


class MedianRatioBaseline:
    def __init__(self,min_count=30,lower_bounds=None):
        self.min_count=min_count
        self.lower_bounds=lower_bounds or [0,6,12,18,24,36,48,60]
        self.state=None

    def fit(self,features,target):
        validate_inputs(features)
        if len(features)==0 or len(features)!=len(target):raise ValueError('Invalid training sizes')
        y=pd.Series(list(target),index=features.index,dtype=float)
        if y.isna().any() or not all(math.isfinite(v) and v>0 for v in y):raise ValueError('Invalid sale target')
        table=features.copy()
        table['duration_bin']=table.months_since_agreement_at_seizure.map(lambda x:duration_bin(x,self.lower_bounds))
        table['ratio']=y/table.asset_cost_at_disbursal
        state={'min_count':self.min_count,'lower_bounds':self.lower_bounds,'n_training':len(table),'tables':{},
               'global':{'median_ratio':float(table.ratio.median()),'count':len(table)}}
        for level,columns in [('model_duration',['asset_model','duration_bin']),('model',['asset_model']),('fuel',['asset_fuel_type'])]:
            stats=[]
            for key,g in table.groupby(columns,sort=True):
                if not isinstance(key,tuple):key=(key,)
                key=[int(x) if columns[i]=='duration_bin' else str(x) for i,x in enumerate(key)]
                stats.append({'key':key,'median_ratio':float(g.ratio.median()),'count':len(g)})
            state['tables'][level]=stats
        self.state=state
        return self

    def predict(self,features,global_only=False):
        validate_inputs(features)
        if self.state is None:raise ValueError('Baseline has not been fitted')
        lookups={level:{tuple(x['key']):x for x in values} for level,values in self.state['tables'].items()}
        result=[]
        for r in features.to_dict('records'):
            bucket=duration_bin(r['months_since_agreement_at_seizure'],self.lower_bounds)
            chosen=self.state['global']; level='global'
            if not global_only:
                for candidate,key in [('model_duration',(r['asset_model'],bucket)),('model',(r['asset_model'],)),('fuel',(r['asset_fuel_type'],))]:
                    item=lookups[candidate].get(key)
                    if item is not None and item['count']>=self.min_count:
                        chosen=item;level=candidate;break
            result.append({'prediction':r['asset_cost_at_disbursal']*chosen['median_ratio'],
                           'fallback_level':level,'reference_count':chosen['count'],'reference_ratio':chosen['median_ratio']})
        return pd.DataFrame(result,index=features.index)

    def save(self,path):
        Path(path).write_text(json.dumps(self.state,indent=2,allow_nan=False)+'\n',encoding='utf-8')

    @classmethod
    def load(cls,path):
        state=json.loads(Path(path).read_text())
        model=cls(state['min_count'],state['lower_bounds']);model.state=state
        return model
