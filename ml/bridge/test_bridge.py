"""Contract checks using the exact P15 wire format, plus real-DB tests in native acceptance."""
import json
from copy import deepcopy
from datetime import datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from bridge.server import backend_statement_digest, create_app
from bridge.store import Conflict
from feed.catalog import Catalog, candidate_digest
from scoring.backend_input import build_backend
from scoring.features import build, digest

TOKEN='integration-test-service-token-32-characters'

class MemoryStore:
    def __init__(self): self.rows={}
    def ready(self): pass
    def get(self,key): return self.rows.get(key)
    def call(self,key,body,prepare,execute):
        old=self.rows.get(key)
        if old and old['input_hash']!=digest(body):raise Conflict('Input conflict')
        if old is None:
            old={'input_hash':digest(body),'request':prepare(),'response':None}; self.rows[key]=old
        if old['response'] is None:old['response']=execute(old['request'])
        return old['response']

@pytest.fixture
def statement():
    return dict(periodStart='2025-01-01',periodEnd='2025-12-31',reportingStandard='DEMO',currency='RUB',
                values=dict(totalAssetsMinor=100000000,totalLiabilitiesMinor=40000000,currentAssetsMinor=50000000,
                            currentLiabilitiesMinor=20000000,equityMinor=60000000,revenueMinor=300000000,
                            netProfitMinor=10000000,ebitMinor=15000000),sourceDocumentReferences=[])

def test_backend_profile_preserves_eight_ratios(statement):
    for liability in (0,1,40000000,90000000):
        for profit in (-100,0,1500000):
            s=deepcopy(statement);s['values'].update(totalLiabilitiesMinor=liability,currentLiabilitiesMinor=0,
                                                   equityMinor=100000000-liability,netProfitMinor=profit)
            assert build_backend(s)==build(s)

def test_backend_tolerance_and_documents_are_not_repaired(statement):
    statement['values']['equityMinor']+=1000000
    statement['sourceDocumentReferences']=[dict(documentId='doc',documentVersion=2,objectVersion='v2')]
    result=build_backend(statement)
    assert result['X10']==.61
    statement['values']['equityMinor']+=1
    with pytest.raises(ValueError):build_backend(statement)

def test_source_versions_digest_and_replay(statement):
    store=MemoryStore();requests=[]
    def risk(req):
        requests.append(req)
        if req.url.path.endswith('/bundle'):return httpx.Response(200,json={'manifest':{'bundleDigest':'a'*64,'featureCodeDigest':'b'*64},'backendInputAdapterDigest':'c'*64})
        if req.url.path.endswith('/feature-snapshots'):
            b=json.loads(req.content)
            result=dict(featureSnapshotId='feature',submissionSnapshotId=b['submissionSnapshotId'],financialStatementVersion=1,
                        featureSchemaVersion=2,featureCodeDigest='b'*64,featureAsOf=b['asOf'],latestSourceAvailableAt=b['latestSourceAvailableAt'],
                        financialSnapshotId=b['financialSnapshotId'],financialSnapshotDigest=b['financialSnapshotDigest'],
                        features=build_backend(b['financialStatement']),missingFeatures=[],inputAdapterDigest='c'*64)
            result['snapshotDigest']=digest(result);return httpx.Response(200,json=result)
        b=json.loads(req.content)
        return httpx.Response(200,json=dict(b,inferenceId='inference',score=.12,scoreKind='BANKRUPTCY_PROXY',calibrationStatus='DEMONSTRATION',releaseId='baseline',modelVersion='baseline',internalReasonCodes=[]))
    app=create_app(store=store,token=TOKEN,risk_transport=httpx.MockTransport(risk),feed_transport=httpx.MockTransport(lambda r:httpx.Response(503)))
    with TestClient(app) as client:
        headers={'X-Service-Token':TOKEN,'Idempotency-Key':'risk:financial:features'}
        body=dict(applicationId='app',submissionSnapshotId='submission',financialStatementVersion=1,
                  asOf='2026-10-21T10:00:00Z',latestSourceAvailableAt='2026-10-21T10:00:00Z',purpose='DEMO_RESEARCH',
                  financialSnapshotId='financial',financialSnapshotDigest=backend_statement_digest(statement,1),financialStatement=statement)
        one=client.post('/internal/v2/feature-snapshots',json=body,headers=headers)
        assert one.status_code==200,one.text
        two=client.post('/internal/v2/feature-snapshots',json=body,headers=headers)
        assert one.json()==two.json() and len(requests)==2
        feature=one.json()
        request=dict(requestId='risk:financial',featureSnapshotId=feature['featureSnapshotId'],featureSnapshotDigest=feature['snapshotDigest'],featureSchemaVersion=2,purpose='DEMO_RESEARCH')
        headers['Idempotency-Key']='risk:financial:evaluation'
        response=client.post('/internal/v2/risk/evaluations',json=request,headers=headers)
        assert response.status_code==200,response.text
        assert response.json()['featureSnapshotDigest']==feature['snapshotDigest']
        assert 'purpose' not in response.json()
        native=json.loads(requests[-1].content)
        assert native['bundleDigest']=='a'*64 and native['featureSnapshotDigest']!=feature['snapshotDigest']
        assert requests[-1].headers['Authorization']=='Bearer '+TOKEN
        assert client.post('/internal/v2/risk/evaluations',json=request,headers=headers).json()==response.json()
        request['featureSnapshotDigest']='0'*64
        assert client.post('/internal/v2/risk/evaluations',json=request,headers=headers).status_code==409
        body.pop('latestSourceAvailableAt');headers['Idempotency-Key']='risk:financial:features'
        assert client.post('/internal/v2/feature-snapshots',json=body,headers=headers).status_code==422
        assert client.get('/health').status_code==403

def test_feed_legacy_and_modern_fallback_are_deterministic():
    catalog=Catalog();ids=sorted(catalog.cards)
    store=MemoryStore()
    app=create_app(store=store,token=TOKEN,risk_transport=httpx.MockTransport(lambda r:httpx.Response(503)),feed_transport=httpx.MockTransport(lambda r:httpx.Response(503)))
    import hashlib
    body=dict(requestId='feed1',scope='FEED',candidateIds=ids,candidateSetDigest=hashlib.sha256('\n'.join(ids).encode()).hexdigest(),catalogVersion=catalog.version,
              eligibilityVersion=None,stage=None,contextCategory=None,fundingPurpose='EQUIPMENT',contextText='ignored confidential text',candidateTexts=None)
    with TestClient(app) as c:
        headers={'X-Service-Token':TOKEN,'Idempotency-Key':'feed1'}
        r=c.post('/internal/v2/rankings',json=body,headers=headers)
        assert r.status_code==200,r.text
        assert r.json()['mode']=='RULES' and set(r.json()['rankedIds'])==set(ids)
        assert r.json()['candidateSetDigest']==body['candidateSetDigest']
        assert 'confidential' not in json.dumps(store.rows)
        body['candidateSetDigest']='0'*64
        assert c.post('/internal/v2/rankings',json=body,headers=headers).status_code==409


def test_feed_retry_cannot_repin_model_release():
    from feed.ranker import RulesRanker
    catalog=Catalog();body=__import__('feed.integration',fromlist=['make_request']).make_request(catalog,request_id='pinned-feed',exposure_id='pinned-exposure',candidate_ids=sorted(catalog.cards),profile={'task':'EQUIPMENT'})
    calls=[]
    def feed(req):
        if req.url.path=='/health':return httpx.Response(200,json={'releaseId':'release-A','bundleDigest':'a'*64})
        calls.append(req)
        if len(calls)==1:return httpx.Response(409)
        result=RulesRanker(catalog).rank(body).model_dump(mode='json');result.update(mode='MODEL',releaseId='release-B')
        return httpx.Response(200,json=result)
    store=MemoryStore();app=create_app(store=store,token=TOKEN,feed_transport=httpx.MockTransport(feed))
    with TestClient(app) as c:
        headers={'X-Service-Token':TOKEN,'Idempotency-Key':body.requestId}
        assert c.post('/internal/v2/feed/rankings',json=body.model_dump(mode='json'),headers=headers).status_code==409
        assert c.post('/internal/v2/feed/rankings',json=body.model_dump(mode='json'),headers=headers).status_code==409
        assert store.get('feed:'+body.requestId)['request']['releaseId']=='release-A'
