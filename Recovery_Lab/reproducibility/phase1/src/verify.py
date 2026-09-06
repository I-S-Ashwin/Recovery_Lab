"""Independent full-row verification of the Phase 1 package and its original source."""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path

import openpyxl


def digest(p):
    return hashlib.file_digest(Path(p).open('rb'), 'sha256').hexdigest()


def load_lines(p):
    return [json.loads(s, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
            for s in Path(p).read_text(encoding='utf-8').splitlines() if s]


def verify(source, folder):
    root=Path(folder)
    result=[]
    def require(name, condition):
        if not condition:
            raise AssertionError(name)
        result.append({'check':name,'result':'passed'})

    manifest=json.loads((root/'manifest.json').read_text())
    require('Original workbook matches audited hash', digest(source)==manifest['source_sha256'])
    require('Source script matches manifest', digest(root/'src/audit.py')==manifest['audit_script_sha256'])
    for file,h in manifest['files'].items():
        require('Artifact hash: '+file, digest(root/file)==h)
    raw=load_lines(root/'data/source_values.jsonl')
    clean=load_lines(root/'data/canonical_records.jsonl')
    quarantine=load_lines(root/'data/quarantined_records.jsonl')
    issues=load_lines(root/'reports/row_issues.jsonl')
    dictionary=json.loads((root/'configs/data_dictionary.json').read_text())
    rules=json.loads((root/'reports/quality_checks.json').read_text())
    policy=json.loads((root/'configs/feature_policy.json').read_text())
    fields=[x for x in dictionary if x['source_name'] is not None]
    require('All 41 source columns documented exactly once', len(fields)==41 and len({x['source_name'] for x in fields})==41)
    require('49 canonical columns documented uniquely',len(dictionary)==49 and len({x['canonical_name'] for x in dictionary})==49)
    require('Row reconciliation', len(raw)==len(clean)+len(quarantine)==manifest['source_records'])
    require('Current supplied dataset has expected 15000 rows',len(raw)==15000)
    byrow={x['source_excel_row']:x for x in clean+quarantine}
    require('No row lost or duplicated during normalization',len(byrow)==len(raw))
    require('Quarantine membership matches hard-rule issues',set(x['source_excel_row'] for x in quarantine)=={x['source_excel_row'] for x in issues if x['severity']=='quarantine'})
    require('Retained agreement IDs are unique',len({x['agreement_id'] for x in clean})==len(clean))

    wb=openpyxl.load_workbook(source,read_only=True,data_only=False)
    rows=wb['Sheet1'].iter_rows(values_only=True)
    headers=next(rows)
    direct={i:dict(zip(headers,r)) for i,r in enumerate(rows,2) if any(v is not None for v in r)}
    wb.close()
    same_source=True; same_clean=True; derived=True
    for r in raw:
        excel_row=r['source_excel_row']; canonical=byrow[excel_row]
        for f in fields:
            value=direct[excel_row][f['source_name']]
            if isinstance(value,datetime):value=value.isoformat()
            same_source &= r[f['source_name']]==value
            if f['type']=='string' and value is not None:value=str(value).strip()
            same_clean &= canonical[f['canonical_name']]==value
        a=datetime.fromisoformat(canonical['agreement_date'])
        b=datetime.fromisoformat(canonical['seizure_date'])
        c=datetime.fromisoformat(canonical['sold_date'])
        derived &= math.isclose(canonical['months_since_agreement_at_seizure'],(b-a).total_seconds()/2592000,abs_tol=1e-8)
        derived &= math.isclose(canonical['realized_yard_days'],(c-b).total_seconds()/86400,abs_tol=1e-8)
        derived &= math.isclose(canonical['ltv_recomputed'],canonical['loan_amount']/canonical['asset_cost_at_disbursal'],abs_tol=1e-12)
        cibil=canonical['customer_cibil_score_raw']
        derived &= canonical['customer_cibil_score_usable']==(cibil if cibil>=0 else None)
        derived &= canonical['cibil_special_code_flag']==(cibil<0)
        income=canonical['customer_net_salary_raw']
        derived &= canonical['customer_income_positive']==(income if income>0 else None)
        derived &= canonical['income_nonpositive_flag']==(income<=0)
    require('Source-value snapshot matches every original cell',same_source)
    require('Every canonical source field preserves normalized source value',same_clean)
    require('Every derived value independently reconciles',derived)
    counts=Counter(x['rule'] for x in issues)
    require('Rule counts reconcile with row-level issues',all(counts[r['rule']]==r['affected_rows'] for r in rules))
    blocked={'sale_amount','sold_date','sold_month_raw','sold_year_raw','outstanding_balance_at_liquidation','months_spent_in_yard_raw','realized_yard_days','customer_gender','agreement_id','source_excel_row','asset_age_months_at_seizure_raw'}
    allowed=set(policy['seizure_core_candidate_features'])
    require('Proposed core excludes future, audit, ID and ambiguous-age fields',not (allowed & blocked))
    require('Conditional fields not silently enabled',not allowed.intersection(policy['excluded_pending_definition_or_timestamp']))
    require('All proposed fields exist',allowed.issubset(clean[0]))
    require('Origination excludes realized seizure duration','months_since_agreement_at_seizure' not in policy['origination_core_candidate_features'])
    required_keys={x['canonical_name'] for x in dictionary}
    require('Every retained record follows 49-field schema',all(set(x)==required_keys for x in clean))
    require('Source still unchanged at verification end',digest(source)==manifest['source_sha256'])
    output={'status':'passed','checks':result,'check_count':len(result),'source_records_verified':len(raw),
            'source_cells_verified':len(raw)*len(fields),'note':'Data preparation verification only; no trained model or performance validation.'}
    (root/'reports/verification.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps({k:v for k,v in output.items() if k!='checks'},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--source',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args()
    verify(a.source,a.output)
