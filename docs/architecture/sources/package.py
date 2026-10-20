"""Seal a reviewed specification, never publish or send it anywhere."""
from pathlib import Path
import os,sys,json,hashlib,subprocess,zipfile
O=Path(__file__).resolve().parents[1]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
subprocess.run([sys.executable,str(O/'sources/validate.py')],cwd=O,check=True,env=os.environ.copy())
v=json.loads((O/'visual-review.json').read_text())
assert v['status']=='PASS' and all(digest(O/x['path'])==x['sha256'] for x in v['pdfs']),'Visual review is missing or stale'
rep=json.loads((O/'evidence/reproducibility-report.json').read_text());assert rep['status']=='PASS'
files=[p for p in sorted(O.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.name not in ['.DS_Store','SHA256SUMS']]
(O/'SHA256SUMS').write_text(''.join(digest(p)+'  '+str(p.relative_to(O))+'\n' for p in files))
files.append(O/'SHA256SUMS');archive=O.parent/'credit-workspace-hackathon-ready.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in sorted(files):
  zi=zipfile.ZipInfo('hackathon-ready/'+str(p.relative_to(O)),date_time=(2026,10,20,0,0,0));zi.compress_type=zipfile.ZIP_DEFLATED;zi.external_attr=0o100644<<16;z.writestr(zi,p.read_bytes())
record=dict(path=str(archive),sha256=digest(archive),bytes=archive.stat().st_size,files=len(files),status='LOCAL_PACKAGE_CREATED_NOT_PUBLISHED')
(archive.with_suffix('.sha256')).write_text(record['sha256']+'  '+archive.name+'\n');print(json.dumps(record,ensure_ascii=False))
