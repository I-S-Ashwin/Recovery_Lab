"""Live HTTP route and asset checks; no browser automation."""
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parents[1];BASE='http://127.0.0.1:8078'
checks=[]
def check(name,condition):
    if not condition:raise AssertionError(name)
    checks.append(name)
def call(path,body=None):
    req=Request(BASE+path,data=None if body is None else json.dumps(body).encode(),headers={} if body is None else {'Content-Type':'application/json'})
    with urlopen(req,timeout=20) as r:return r.status,json.load(r)
class Assets(HTMLParser):
    def __init__(self):super().__init__();self.paths=set()
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        value=attrs.get('src') if tag=='script' else attrs.get('href') if tag=='link' else None
        if value and value.startswith('/') and not value.startswith('//'):self.paths.add(value)
with urlopen(BASE+'/',timeout=20) as response:
    check('production page HTTP 200',response.status==200)
    check('page served as HTML','text/html' in response.headers['Content-Type'])
parser=Assets();parser.feed((ROOT/'dashboard/dist/client/index.html').read_text(encoding='utf-8'))
check('export references assets',len(parser.paths)>0)
for path in sorted(parser.paths):
    with urlopen(BASE+path,timeout=20) as response:check('static asset '+path,response.status==200 and len(response.read())>0)
check('ready model and audit',call('/ready')[1]['status']=='ready')
check('correct deployment version',call('/health')[1]['version']=='0.8.0')
ref={'asset_id':'DEMO-A','valuation_date':'2026-09-06','downside_anchor_inr':70000,'median_anchor_inr':85000}
for scenario,expected in [('base',80000),('adverse',70000),('severe',None)]:
    result=call('/v1/lending-simulations',{'request_id':'deployment-'+scenario,'reference':ref,'scenario':scenario,
        'asset_reference_cost_inr':100000,'verified_monthly_income_inr':30000,'existing_monthly_obligations_inr':5000,
        'income_verified':True,'obligations_verified':True})[1]
    check('deployed offer '+scenario,(result['recommended_offer']['principal_inr'] if result['recommended_offer'] else None)==expected)
assets=call('/v1/demo-portfolio')[1]['assets']
portfolio={'scenario':'severe','default_month':0,'assets':[{'reference':{k:a[k] for k in ['asset_id','valuation_date','downside_anchor_inr','median_anchor_inr']},**{k:a[k] for k in ['existing_principal_inr','annual_nominal_rate','remaining_term_months']}} for a in assets]}
check('deployed portfolio endpoint precedes static catchall',call('/v1/portfolio-scenarios',portfolio)[1]['downside_shortfall_inr']==121880)
check('historical lookup',call('/v1/calibration-cases/ASSET_40')[1]['agreement_id']=='ASSET_40')
check('audit events recorded',call('/v1/audit')[1]['summary']['recorded_requests']>0)
(ROOT/'reports/deployment_checks.json').write_text(json.dumps({'passed':len(checks),'failed':0,'checks':checks,'browser_interactions_tested':False},indent=2)+'\n')
print(json.dumps({'deployment_checks_passed':len(checks)}))
