"""Build an indexed, integrity-checked delivery archive after verification."""
import json
import zipfile
from run_phase6 import ROOT, digest, save

verification=json.loads((ROOT/'reports/verification.json').read_text())
if verification['failed'] or verification['passed'] < 83:
    raise RuntimeError('Verification must pass before packaging')
files=sorted(p for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='package_index.json')
save(ROOT/'package_index.json',{str(p.relative_to(ROOT)).replace('\\','/'):{'sha256':digest(p),'bytes':p.stat().st_size} for p in files})
archive=ROOT.parent/'TVS_Credit_Phase_6.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    for p in files+[ROOT/'package_index.json']:
        z.write(p,str(p.relative_to(ROOT.parent)))
with zipfile.ZipFile(archive) as z:
    if z.testzip() is not None:
        raise RuntimeError('Archive integrity failed')
print(json.dumps({'archive':str(archive),'files':len(files)+1,'integrity':'passed'}))
