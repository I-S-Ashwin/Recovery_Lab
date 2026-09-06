"""Run one explicit lending simulation; input errors are returned as structured JSON."""
import argparse
import json
from pathlib import Path
from engine import simulate


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--request',type=Path,required=True);p.add_argument('--policy',type=Path,required=True);p.add_argument('--output',type=Path)
    a=p.parse_args()
    try:
        result=simulate(json.loads(a.request.read_text()),json.loads(a.policy.read_text()))
    except (ValueError,KeyError,TypeError) as e:
        result={'status':'invalid_input','reasons':[str(e)],'automatic_approval':False}
    text=json.dumps(result,indent=2,allow_nan=False)+'\n'
    if a.output:a.output.write_text(text,encoding='utf-8')
    else:print(text)
