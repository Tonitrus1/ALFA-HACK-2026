"""Acceptance of ML durability, persistence failure and OS-level network isolation."""
import json,os,hashlib,subprocess,time
from pathlib import Path
import requests
from ml_manage import ROOT,admin,env,up,down
from scoring.client import RiskClient
from scoring.demo_policy import after_risk
m=json.loads((ROOT/'ml/artifacts/baseline/manifest.json').read_text());client=RiskClient('http://127.0.0.1:8001',env()['ML_INTERNAL_TOKEN'],m['bundleDigest'])
s=json.loads((ROOT/'ml/fixtures/scenarios.json').read_text())['companies'][0]['reference'];snapshot=client.create_snapshot(client.snapshot_request(s));b=client.risk_request(snapshot);prediction=client.evaluate(b)
artifacts={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'ml/artifacts/baseline').iterdir() if p.is_file()}
down();up(True)
assert client.evaluate(b)==prediction;assert client.call('/internal/v2/feature-snapshots/'+snapshot['featureSnapshotId'])==snapshot
assert artifacts=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'ml/artifacts/baseline').iterdir() if p.is_file()}
checks=[{'name':'restart_preserves_immutable_snapshot_and_exact_inference','passed':True},{'name':'runtime_does_not_train_or_change_bundle','passed':True}]
# Hold real inference table authority, then make a real request. No successful response may precede persistence.
second=client.create_snapshot(client.snapshot_request(s));blocked_request=client.risk_request(second);db=admin();db.execute('begin');db.execute('lock ml.inferences in access exclusive mode');started=time.perf_counter()
try:
    try:client.evaluate(blocked_request);raise AssertionError('Success before persistence')
    except requests.RequestException:pass
finally:db.execute('rollback');db.close()
elapsed=time.perf_counter()-started;assert elapsed<3.5
assert after_risk(s,20000000,None,.039,ml_error=True)['outcome']=='MANUAL'
restored=client.evaluate(blocked_request);assert restored['score']==prediction['score']
checks.append({'name':'persistence_failure_is_error_and_reference_policy_manual','passed':True,'seconds':elapsed})
script="import socket; socket.create_connection(('1.1.1.1',443),timeout=1)"
r=subprocess.run(['/usr/bin/sandbox-exec','-f',str(ROOT/'scripts/offline.sb'),str(ROOT/'.venv/bin/python'),'-c',script],capture_output=True,text=True)
assert r.returncode!=0 and 'Operation not permitted' in r.stderr
checks.append({'name':'external_tcp_denied_by_os_profile','passed':True,'target':'1.1.1.1:443','errno':1})
report={'scope':'Standalone ML API + PostgreSQL only','passed':True,'checks':checks,'networkMode':'all ML and PostgreSQL processes launched under scripts/offline.sb (loopback and Unix sockets only)','profileDigest':hashlib.sha256((ROOT/'scripts/offline.sb').read_bytes()).hexdigest(),'bundleDigest':m['bundleDigest']}
(ROOT/'reports/ml-runtime.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('Standalone runtime checks passed')
