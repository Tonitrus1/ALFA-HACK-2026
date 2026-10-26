"""Verify byte-identical outputs after a clean self-contained rebuild in a new directory."""
from pathlib import Path
import sys,os,tempfile,shutil,subprocess,hashlib,json
O=Path(__file__).resolve().parents[1]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
files=[p for p in O.rglob('*') if p.is_file() and (p.suffix in ['.pdf','.svg','.drawio'] or (p.parent.name=='api' and p.suffix=='.json'))]
with tempfile.TemporaryDirectory(prefix='credit-spec-rebuild-') as tmp:
 dest=Path(tmp)/'spec';shutil.copytree(O,dest,ignore=shutil.ignore_patterns('__pycache__','visual-review.json','SHA256SUMS','validation-report.json'))
 # Remove generated outputs so the command cannot accidentally verify stale copies.
 for p in files:(dest/p.relative_to(O)).unlink()
 subprocess.run([sys.executable,str(dest/'sources/build.py')],check=True,cwd=dest,env=os.environ.copy())
 bad=[str(p.relative_to(O)) for p in files if not(dest/p.relative_to(O)).exists() or digest(p)!=digest(dest/p.relative_to(O))]
 report={'status':'PASS' if not bad else 'FAIL','method':'Fresh directory, deleted generated outputs, builder reads only delivered files','filesCompared':len(files),'outputSha256':{str(p.relative_to(O)):digest(p) for p in files},'builderSha256':digest(O/'sources/build.py'),'mismatches':bad,'scope':'Specification rendering and API copies only; no application built'}
 (O/'evidence/reproducibility-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
 if bad:raise SystemExit(1)
