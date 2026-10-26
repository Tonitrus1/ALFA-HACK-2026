"""Opt-in real HTTP/model/database acceptance. No test doubles in the HTTP path."""
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from bridge.server import backend_statement_digest, create_app
from bridge.store import Store, Conflict
from feed.catalog import Catalog
from feed.integration import make_request

class PrivateConfig(dict):
    def __repr__(self): return '<private native configuration>'
class PrivateDsn(str):
    def __repr__(self): return '<private native database DSN>'

CONFIG=os.environ.get('INTEGRATION_NATIVE_CONFIG')
pytestmark=pytest.mark.skipif(not CONFIG,reason='Requires explicitly started dedicated native integration environment')

@pytest.fixture
def native():
    cfg=PrivateConfig(json.loads(Path(CONFIG).read_text()))
    dsn=f"postgresql://ml_runtime:{cfg['password']}@127.0.0.1:55440/integration_ml"
    return cfg,PrivateDsn(dsn)

def feature_body():
    identifier=str(uuid4())
    statement=dict(periodStart='2025-01-01',periodEnd='2025-12-31',currency='RUB',reportingStandard='DEMO',
                   values=dict(totalAssetsMinor=100000000,totalLiabilitiesMinor=40000000,currentAssetsMinor=50000000,
                               currentLiabilitiesMinor=20000000,equityMinor=60000000,revenueMinor=300000000,
                               netProfitMinor=10000000,ebitMinor=15000000),sourceDocumentReferences=[])
    return dict(applicationId='acceptance-'+identifier,submissionSnapshotId='submission-'+identifier,financialStatementVersion=1,
                asOf='2026-10-22T12:00:00Z',latestSourceAvailableAt='2026-10-22T12:00:00Z',purpose='DEMO_RESEARCH',
                financialSnapshotId=identifier,financialSnapshotDigest=backend_statement_digest(statement,1),financialStatement=statement)

def test_concurrent_real_inference_and_durable_replay(native):
    cfg,dsn=native;body=feature_body();headers={'X-Service-Token':cfg['token'],'Idempotency-Key':'risk:'+body['financialSnapshotId']+':features'}
    with httpx.Client(base_url='http://127.0.0.1:18000',timeout=5) as c:
        feature=c.post('/internal/v2/feature-snapshots',json=body,headers=headers)
        assert feature.status_code==200,feature.text
        snap=feature.json()
        request=dict(requestId='risk:'+body['financialSnapshotId'],featureSnapshotId=snap['featureSnapshotId'],featureSnapshotDigest=snap['snapshotDigest'],featureSchemaVersion=2,purpose='DEMO_RESEARCH')
        headers['Idempotency-Key']=request['requestId']+':evaluation'
        def invoke(_):return c.post('/internal/v2/risk/evaluations',json=request,headers=headers)
        with ThreadPoolExecutor(max_workers=4) as pool:responses=list(pool.map(invoke,range(8)))
        assert all(r.status_code==200 for r in responses),[(r.status_code,r.text) for r in responses]
        assert len({r.json()['inferenceId'] for r in responses})==1
        # A fresh Store object reads the same committed response; no process-local cache is required.
        saved=Store(dsn).get('risk:'+request['requestId'])
        assert saved['response']==responses[0].json()
        assert responses[0].json()['scoreKind']=='BANKRUPTCY_PROXY'
        assert 0<=responses[0].json()['score']<=1

def test_pending_failure_never_repins_release(native):
    _,dsn=native;key='pin-test:'+str(uuid4());store=Store(dsn)
    def fail(pinned):raise RuntimeError('simulated transport failure after durable pin')
    with pytest.raises(RuntimeError):store.call(key,{'input':1},lambda:{'bundle':'original'},fail)
    assert Store(dsn).call(key,{'input':1},lambda:{'bundle':'replacement'},lambda pinned:pinned)=={'bundle':'original'}
    with pytest.raises(Conflict):store.call(key,{'input':2},lambda:{},lambda x:x)

def test_real_feed_and_repeated_ranking(native):
    cfg,_=native;catalog=Catalog();identifier=str(uuid4())
    request=make_request(catalog,request_id=identifier,exposure_id=identifier,candidate_ids=sorted(catalog.cards),profile={'task':'EQUIPMENT','help':'COST','depth':'PRACTICAL'})
    with httpx.Client(base_url='http://127.0.0.1:18000',timeout=5) as c:
        headers={'X-Service-Token':cfg['token'],'Idempotency-Key':identifier}
        response=c.post('/internal/v2/feed/rankings',json=request.model_dump(mode='json',exclude_none=True),headers=headers)
        assert response.status_code==200,response.text
        assert response.json()['mode']=='MODEL'
        assert set(response.json()['rankedIds'])==set(catalog.cards)
        assert c.post('/internal/v2/feed/rankings',json=request.model_dump(mode='json',exclude_none=True),headers=headers).json()==response.json()

def test_persistence_failure_never_returns_success(native,monkeypatch):
    cfg,dsn=native
    monkeypatch.setenv('RISK_BASE_URL','http://127.0.0.1:18001')
    monkeypatch.setenv('FEED_BASE_URL','http://127.0.0.1:18002')
    class ReadOnlyStore(Store):
        def connect(self):
            connection=super().connect()
            connection.read_only=True
            return connection
    app=create_app(store=ReadOnlyStore(dsn),token=cfg['token'])
    body=feature_body()
    with TestClient(app) as c:
        r=c.post('/internal/v2/feature-snapshots',json=body,headers={'X-Service-Token':cfg['token'],'Idempotency-Key':'risk:'+body['financialSnapshotId']+':features'})
        assert r.status_code==503,r.text
