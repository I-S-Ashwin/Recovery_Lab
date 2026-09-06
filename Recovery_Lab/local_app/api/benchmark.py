"""Local HTTP latency sample with fixed fictional requests, never test outcomes."""
from concurrent.futures import ThreadPoolExecutor
import json
import math
from pathlib import Path
import statistics
import time
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parents[1]
BASE='http://127.0.0.1:8078'
features={'customer_branch':'HYDERABAD I','customer_region':'AP','customer_state':'AP','pincode_tier':'02 Megapolis (B)',
          'asset_variant':'TVS XL 100 HD ITS','asset_model':'MOPEDS','asset_fuel_type':'Petrol',
          'asset_cost_at_disbursal':81000,'months_since_agreement_at_seizure':18}
payload={'request_id':'latency-fictional','mode':'seizure','as_of_date':'2026-09-06','features':features,
         'feature_sources':{k:{'available_on':'2026-09-06','source':'Fictional latency fixture'} for k in features}}
def call(_=None):
    started=time.perf_counter()
    request=Request(BASE+'/v1/valuations',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    with urlopen(request,timeout=15) as response:
        value=json.load(response)
        if response.status!=200 or abs(value['median_value_inr']-34510.9924319773)>1e-6:raise AssertionError('Incorrect live model output')
        if value['explanation']['method']!='Native CatBoost SHAP':raise AssertionError('Missing explanation')
        if not response.headers.get('X-Request-ID'):raise AssertionError('Missing audit trace')
    return (time.perf_counter()-started)*1000
def summary(values):
    return {'requests':len(values),'p50_ms':statistics.median(values),'p95_ms':sorted(values)[math.ceil(.95*len(values))-1],
            'maximum_ms':max(values),'minimum_ms':min(values),'samples_ms':values}
if __name__=='__main__':
    first=call()
    for _ in range(3):call()
    serial=[call() for _ in range(24)]
    with ThreadPoolExecutor(max_workers=4) as pool:concurrent=list(pool.map(call,range(16)))
    result={'first_measured_request_ms':first,'serial':summary(serial),'four_clients':summary(concurrent),
            'scope':'Loopback HTTP, fixed fictional request, native Windows runtime; includes model, SHAP and audit commit. Not a production load certification.',
            'timed_out_requests':0,'incorrect_predictions':0}
    (ROOT/'reports/latency.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:{a:b for a,b in v.items() if a!='samples_ms'} if isinstance(v,dict) else v for k,v in result.items()}))
