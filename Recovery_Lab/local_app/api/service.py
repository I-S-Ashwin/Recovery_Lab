"""Local POC API. Finance/projection/model formulas are imported unchanged."""
from contextlib import asynccontextmanager
from datetime import date
import hashlib
import json
import os
import secrets
import time
from pathlib import Path
from threading import Lock
from typing import Literal, Annotated
from uuid import uuid4

import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware
from calibrated import CalibratedValuator
from frozen_policy import simulate, schedule, recovery_risk
from projection import project, stress_asset, aggregate
from frozen_baseline import MedianRatioBaseline
from explanations import explain
from operations import AuditJournal, RateLimit, verify_bundle

ROOT=Path(__file__).resolve().parents[1]
def read(p): return json.loads(p.read_text(encoding='utf-8'))
CONFIG=read(ROOT/'configs/scenarios.json')
POLICY=read(ROOT/'configs/demo_policy.json')
CONTRACT=read(ROOT/'models/base_feature_contract.json')
SCENARIOS={s['name']:s for s in CONFIG['scenarios']}
MODEL_LOCK=Lock()
CALIBRATION=read(ROOT/'models/calibration.json')

class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)

class Features(Strict):
    customer_branch: str=Field(min_length=1,max_length=100)
    customer_region: str=Field(min_length=1,max_length=100)
    customer_state: str=Field(min_length=1,max_length=100)
    pincode_tier: str=Field(min_length=1,max_length=100)
    asset_variant: str=Field(min_length=1,max_length=150)
    asset_model: str=Field(min_length=1,max_length=100)
    asset_fuel_type: str=Field(min_length=1,max_length=30)
    asset_cost_at_disbursal: float=Field(gt=0,le=10000000,strict=True)
    months_since_agreement_at_seizure: float=Field(ge=0,le=600,strict=True)

class Availability(Strict):
    available_on: date
    source: str=Field(min_length=1,max_length=200)

class ValuationRequest(Strict):
    request_id: str=Field(min_length=1,max_length=100)
    mode: Literal['seizure']='seizure'
    as_of_date: date
    features: Features
    feature_sources: dict[str,Availability]
    contemporaneous_exposure_inr: float|None=Field(default=None,ge=0,le=10000000,strict=True)
    recovery_cost_inr: float=Field(default=3000,ge=0,le=1000000,strict=True)

class Reference(Strict):
    asset_id: str=Field(min_length=1,max_length=100)
    valuation_date: date
    downside_anchor_inr: float=Field(ge=0,le=10000000,strict=True)
    median_anchor_inr: float=Field(ge=0,le=10000000,strict=True)

class ProjectionRequest(Strict):
    reference: Reference
    scenario: Literal['base','adverse','severe']='base'
    months: list[Annotated[int,Field(strict=True)]]=Field(default=[0,12,24,36],min_length=1,max_length=43)

class LendingRequest(Strict):
    request_id: str=Field(min_length=1,max_length=100)
    reference: Reference
    scenario: Literal['base','adverse','severe']='base'
    asset_reference_cost_inr: float=Field(gt=0,le=10000000,strict=True)
    verified_monthly_income_inr: float|None=Field(default=None,ge=0,le=10000000,strict=True)
    existing_monthly_obligations_inr: float|None=Field(default=None,ge=0,le=10000000,strict=True)
    income_verified: bool=Field(default=False,strict=True)
    obligations_verified: bool=Field(default=False,strict=True)

class PortfolioAsset(Strict):
    reference: Reference
    existing_principal_inr: float=Field(gt=0,le=10000000,strict=True)
    annual_nominal_rate: float=Field(ge=0,le=1,strict=True)
    remaining_term_months: int=Field(ge=1,le=600,strict=True)

class PortfolioRequest(Strict):
    scenario: Literal['base','adverse','severe']='base'
    default_month: int=Field(default=0,ge=0,le=36,strict=True)
    assets: list[PortfolioAsset]=Field(min_length=1,max_length=100)

@asynccontextmanager
async def lifespan(app):
    app.state.integrity_files=verify_bundle(ROOT)
    app.state.audit=AuditJournal(os.environ.get('TVS_RUNTIME_DIR',str(ROOT/'runtime')))
    app.state.rate_limit=RateLimit()
    app.state.baseline=MedianRatioBaseline.load(ROOT/'models/B0_median_ratio.json')
    app.state.valuator=CalibratedValuator(ROOT/'models')
    app.state.primary_healthy=True
    yield
    app.state.valuator=None

app=FastAPI(title='TVS Recovery Lab — local deployment',version='0.8.0',lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware,allowed_hosts=['127.0.0.1','localhost','testserver'])

@app.middleware('http')
async def boundaries(request:Request,call_next):
    trace=str(uuid4());started=time.perf_counter();body=bytearray()
    def finish(response):
        elapsed=(time.perf_counter()-started)*1000
        if request.url.path.startswith('/v1/'):
            route=getattr(request.scope.get('route'),'path','/v1/unmatched')
            try:
                app.state.audit.record(trace,request.method,route,bytes(body),response.status_code,elapsed,getattr(request.state,'decision_status',None))
            except Exception:
                response=JSONResponse({'detail':'Audit storage unavailable; no decision was issued'},status_code=503)
        response.headers['X-Request-ID']=trace
        response.headers['Server-Timing']=f'app;dur={(time.perf_counter()-started)*1000:.3f}'
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        return response
    if request.client and request.client.host not in ['127.0.0.1','::1','testclient']:
        return finish(JSONResponse({'detail':'Local access only'},status_code=403))
    origin=request.headers.get('origin')
    if origin and origin not in ['http://127.0.0.1:5174','http://localhost:5174','http://127.0.0.1:8078','http://localhost:8078']:
        return finish(JSONResponse({'detail':'Origin is not allowed'},status_code=403))
    if request.url.path.startswith('/v1/') and not app.state.rate_limit.allow():
        return finish(JSONResponse({'detail':'Local request limit reached; retry in one minute'},status_code=429,headers={'Retry-After':'60'}))
    if request.method=='POST':
        if request.headers.get('content-type','').split(';')[0]!='application/json':
            return finish(JSONResponse({'detail':'application/json required'},status_code=415))
        async for chunk in request.stream():
            if len(body)+len(chunk)>131072:
                return finish(JSONResponse({'detail':'Request exceeds 128 KiB'},status_code=413))
            body.extend(chunk)
        request._body=bytes(body)
    try:
        response=await call_next(request)
    except Exception:
        response=JSONResponse({'detail':'Service error; no decision was issued'},status_code=503)
    return finish(response)

@app.exception_handler(ValueError)
async def invalid(request,exc):
    return JSONResponse({'detail':str(exc)},status_code=422)

@app.exception_handler(RequestValidationError)
async def invalid_contract(request,exc):
    # Do not echo raw supplied values, including nonfinite numbers or private fields.
    return JSONResponse({'detail':[{'location':list(e['loc']),'message':e['msg'],'type':e['type']} for e in exc.errors()]},status_code=422)

@app.get('/health')
def health(): return {'status':'ok','version':'0.8.0','local_poc':True}

@app.get('/ready')
def ready():
    if not getattr(app.state,'valuator',None) or not app.state.primary_healthy: raise HTTPException(503,'Primary model is unavailable; baseline review only')
    try: app.state.audit.summary()
    except Exception:raise HTTPException(503,'Audit storage unavailable')
    return {'status':'ready','model_version':CALIBRATION['version'],'integrity_files':app.state.integrity_files,'audit':'available'}

@app.get('/v1/audit')
def audit():return {'summary':app.state.audit.summary(),'recent':app.state.audit.recent()}

@app.get('/v1/model-info')
def info():
    return {'model':read(ROOT/'models/calibration.json'),'contract':CONTRACT,
            'policy':POLICY,'scenarios':CONFIG,'evidence':read(ROOT/'data/evidence.json'),
            'limitations':['Sold repossessed population only','No validated future horizon forecasts',
                           'Demo policy; no automatic approval','Final holdout evaluated: 1244 operational cases; EV coverage 61.1% on 36 cases'],
            'training_labels_before':'2026-01-01','selection_labels_before':'2026-03-01',
            'calibration_labels_before':'2026-05-01'}

@app.get('/v1/demo-portfolio')
def demo_portfolio():
    return {'evidence_type':'Fictional fixtures; no real customer verification',
            'assets':read(ROOT/'data/fictional_portfolio.json')}

@app.get('/v1/calibration-cases/{agreement_id}')
def lookup(agreement_id:str):
    result=read(ROOT/'data/calibration_lookup.json').get(agreement_id)
    if result is None: raise HTTPException(404,'Not in the packaged calibration cohort')
    return result

@app.post('/v1/valuations')
def valuation(req:ValuationRequest, request:Request):
    if req.as_of_date<date.fromisoformat(CALIBRATION['available_from']):raise ValueError('Calibration was unavailable at requested date')
    if set(req.feature_sources)!=set(CONTRACT['features']):
        raise ValueError('Availability metadata is required for exactly the nine model features')
    if any(x.available_on>req.as_of_date for x in req.feature_sources.values()):
        raise ValueError('A feature became available after the declared decision date')
    features=req.features.model_dump()
    features={k:v.strip() if isinstance(v,str) else v for k,v in features.items()}
    if any(isinstance(v,str) and not v for v in features.values()): raise ValueError('Blank category is not supported')
    support=[]
    for key,known in CONTRACT['training_category_values'].items():
        if features[key] not in known: support.append(key+': category absent from training')
    for key,bounds in CONTRACT['training_numeric_bounds'].items():
        if not bounds['min']<=features[key]<=bounds['max']: support.append(key+': outside training range')
    frame=pd.DataFrame([features])
    if not MODEL_LOCK.acquire(timeout=2):raise HTTPException(503,'Model queue is busy; retry shortly',headers={'Retry-After':'2'})
    explanation=None
    try:
        try:
            q=app.state.valuator.predict(frame,req.as_of_date.isoformat())[0]
            app.state.primary_healthy=True
        except Exception:
            app.state.primary_healthy=False
            try:reference=app.state.baseline.predict(frame).iloc[0].to_dict()
            except Exception:raise HTTPException(503,'Both valuation engines are unavailable; manual review required')
            request.state.decision_status='baseline_review'
            return {'request_id':req.request_id,'status':'review_required','evidence_type':'Uncalibrated B0 baseline fallback; not a primary-model prediction',
                    'currency':'INR','as_of_date':req.as_of_date,'median_value_inr':reference['prediction'],
                    'interval_lower_inr':None,'interval_upper_inr':None,'nominal_coverage':None,
                    'coverage_note':'No calibrated interval is available for this fallback',
                    'model_version':'phase2-B0-frozen','support_warnings':['Primary model unavailable. Manual review required; do not use this fallback for lending.'],
                    'context':[f"Training reference: {reference['fallback_level']} group, {reference['reference_count']:.0f} records",'No calibrated uncertainty interval','Model-based lending is disabled for this fallback'],
                    'fallback_reference':reference,'explanation':None,'risk':None}
        try:explanation=explain(app.state.valuator,frame)
        except Exception:explanation={'method':'unavailable','sentences':['Individual attribution is unavailable; the value estimate is unchanged.']}
    finally:MODEL_LOCK.release()
    low,mid,high=map(float,q)
    request.state.decision_status='review_required' if support else 'estimated'
    return {'request_id':req.request_id,'status':'review_required' if support else 'estimated',
        'evidence_type':'Model estimate for supplied seizure features; no observed outcome for this request',
        'currency':'INR','as_of_date':req.as_of_date,'median_value_inr':mid,
        'interval_lower_inr':low,'interval_upper_inr':high,'nominal_coverage':0.8,
        'coverage_note':'Pooled calibration target; temporal and segment coverage are not guaranteed',
        'model_version':app.state.valuator.calibration['version'],'support_warnings':support,
        'context':explanation['sentences'], 'explanation':explanation,
        'risk':None if req.contemporaneous_exposure_inr is None else recovery_risk(req.contemporaneous_exposure_inr,low,mid,req.recovery_cost_inr)}

@app.post('/v1/projections')
def projections(req:ProjectionRequest):
    return {'evidence_type':'Explicit future assumptions; not validated forecasts',
            'values':[project(req.reference.model_dump(mode='json'),m,SCENARIOS[req.scenario],CONFIG['factor_anchors']) for m in req.months]}

@app.post('/v1/lending-simulations')
def lending(req:LendingRequest, request_context:Request):
    reference=req.reference.model_dump(mode='json');scenario=SCENARIOS[req.scenario]
    values=[project(reference,m,scenario,CONFIG['factor_anchors']) for m in range(43)]
    request=req.model_dump(exclude={'reference','scenario'})
    request.update(recovery_cost_inr=scenario['recovery_cost_inr'],recovery_delay_months=scenario['recovery_delay_months'],
        value_path_kind='explicit_assumptions',assumption_source='Phase 6 demonstration factors and supplied reference anchors',
        downside_value_path=[{'month':v['month'],'value_inr':v['downside_value_inr']} for v in values])
    result=simulate(request,POLICY)
    request_context.state.decision_status=result['status']
    return {**result,'scenario_assumptions':scenario,'reference':reference,'projection_values':values,
            'input_assumptions':req.model_dump(mode='json')}

@app.post('/v1/portfolio-scenarios')
def portfolio(req:PortfolioRequest):
    ids=[a.reference.asset_id for a in req.assets]
    if len(set(ids))!=len(ids): raise ValueError('Duplicate asset IDs are not allowed')
    if len({a.reference.valuation_date for a in req.assets})!=1: raise ValueError('A fixed book requires a common valuation date')
    rows=[]
    for a in req.assets:
        sched=schedule(a.existing_principal_inr,a.annual_nominal_rate,a.remaining_term_months)
        exposure=sched['rows'][min(req.default_month,a.remaining_term_months)]['balance']
        rows.append(stress_asset(a.reference.model_dump(mode='json'),exposure,req.default_month,SCENARIOS[req.scenario],CONFIG['factor_anchors']))
    return {'scenario':req.scenario,'default_month':req.default_month,'scenario_assumptions':SCENARIOS[req.scenario],
            'evidence_type':'Conditional all-default stress; not expected credit loss',**aggregate(rows),'assets':rows,
            'input_assumptions':req.model_dump(mode='json')}

# Register the static catch-all after every API route.
STATIC=ROOT/'dashboard/dist/client'
if (STATIC/'index.html').is_file():
    app.mount('/',StaticFiles(directory=STATIC,html=True),name='dashboard')
