"""Execute a fresh notebook copy with the active Python environment."""
from pathlib import Path
import json,os,sys,tempfile
import nbformat
from nbclient import NotebookClient
root=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='recovery-kernel-') as temporary:
    kernel=Path(temporary)/'kernels/python3';kernel.mkdir(parents=True)
    (kernel/'kernel.json').write_text(json.dumps({'argv':[sys.executable,'-m','ipykernel_launcher','-f','{connection_file}'],'display_name':'Python 3','language':'python'}),encoding='utf-8')
    os.environ['JUPYTER_PATH']=temporary+os.pathsep+os.environ.get('JUPYTER_PATH','')
    nb=nbformat.read(root/'Recovery_Lab_POC.ipynb',as_version=4)
    NotebookClient(nb,timeout=180,kernel_name='python3',resources={'metadata':{'path':str(root)}}).execute()
    nbformat.write(nb,root/'Recovery_Lab_POC_rerun.ipynb')
print('Notebook replay completed without cell errors.')
