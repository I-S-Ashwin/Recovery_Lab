"""Release-time manifest builder. Never regenerate it automatically on server startup."""
from pathlib import Path
import hashlib
import json
ROOT=Path(__file__).resolve().parents[1]
paths=list((ROOT/'models').glob('*'))+list((ROOT/'configs').glob('*.json'))
paths += [ROOT/'api'/name for name in ['calibrated.py','frozen_valuation.py','frozen_baseline.py','frozen_policy.py','projection.py','explanations.py','operations.py','service.py']]
paths += [p for p in (ROOT/'dashboard/dist/client').rglob('*') if p.is_file()]
(ROOT/'bundle_lock.json').write_text(json.dumps({p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)},indent=2)+'\n')
print('Locked',len(paths),'model/configuration/inference files')
