"""Exercise a candidate HTTP service against the existing dedicated PostgreSQL DB."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import requests

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'ml'))
from ml_manage import env,admin
from scoring.bundle import load_bundle
from scoring.client import RiskClient
from scoring.releases import verify_scenarios


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--port',type=int,default=8003)
    a=p.parse_args();bundle=a.bundle.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    _,manifest,_=load_bundle(bundle);verify_scenarios(bundle,ROOT)
    e=env();e.update({'MODEL_BUNDLE':str(bundle),'ML_BASE_URL':f'http://127.0.0.1:{a.port}',
                     'ML_REPORT_DIR':str(out),'ML_EXAMPLE_DIR':str(out/'examples'),'PYTHONDONTWRITEBYTECODE':'1'})
    client=RiskClient(e['ML_BASE_URL'],e['ML_INTERNAL_TOKEN'],manifest['bundleDigest'])
    server=None
    with (out/'service.log').open('ab') as log:
        def start():
            process=subprocess.Popen([str(ROOT/'.venv/bin/python'),'-m','uvicorn','scoring.server:app','--host','127.0.0.1','--port',str(a.port),'--no-access-log'],cwd=ROOT,env=e,stdout=log,stderr=log)
            for _ in range(100):
                if process.poll() is not None:raise RuntimeError('Staging server failed; see service.log')
                try:
                    health=client.call('/health')
                    if health['bundleDigest']!=manifest['bundleDigest']:raise RuntimeError('Port occupied by a different bundle')
                    return process
                except requests.RequestException:time.sleep(.1)
            process.terminate();process.wait(timeout=10);raise RuntimeError('Staging server not ready')
        try:
            server=start()
            schema=requests.get(e['ML_BASE_URL']+'/openapi.json',timeout=3).json()
            assert schema==json.loads((ROOT/'ml/openapi.json').read_text()),'HTTP contract changed'
            subprocess.run([str(ROOT/'.venv/bin/python'),'-m','pytest','ml/tests','-q','--junitxml='+str(out/'tests.xml')],cwd=ROOT,env=e,check=True)
            subprocess.run([str(ROOT/'.venv/bin/python'),'-m','scoring.scenarios'],cwd=ROOT,env=e,check=True)
            fixture=bundle/'scenarios.json'
            if not fixture.exists():fixture=ROOT/'ml/fixtures/scenarios.json'
            statement=json.loads(fixture.read_text())['companies'][0]['reference']
            snapshot=client.create_snapshot(client.snapshot_request(statement));request=client.risk_request(snapshot);first=client.evaluate(request)
            server.terminate();server.wait(timeout=10);server=None
            server=start()
            assert client.evaluate(request)==first,'Inference changed on restart'
            assert client.call('/internal/v2/feature-snapshots/'+snapshot['featureSnapshotId'])==snapshot
            second=client.create_snapshot(client.snapshot_request(statement));blocked=client.risk_request(second)
            db=admin();db.execute('begin');db.execute('lock ml.inferences in access exclusive mode');tick=time.monotonic()
            try:
                try:client.evaluate(blocked);raise AssertionError('Success without persistence')
                except requests.HTTPError as error:assert error.response.status_code==503
            finally:db.execute('rollback');db.close()
            assert time.monotonic()-tick<3.5
            assert client.evaluate(blocked)['score']==first['score']
            report={'passed':True,'modelHash':manifest['artifacts']['model.joblib'],'bundleDigestAtTest':manifest['bundleDigest'],
                    'schemaUnchanged':True,'scenariosPassed':True,'restartPreservesSnapshotAndInference':True,
                    'failedPersistenceReturns503':True,'idempotencyConflictsAuthenticationAndMissingRatios':'pytest tests.xml',
                    'scope':'real local HTTP + dedicated PostgreSQL; no frontend/backend lifecycle claimed'}
            (out/'compatibility.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
        finally:
            if server is not None:server.terminate();server.wait(timeout=10)


if __name__=='__main__':main()
