"""Opt-in real HTTP/PG/Risk/Fraud acceptance. All reference data is explicitly synthetic."""
import copy,json,os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4
import httpx,pytest
from scoring.features import digest
from bridge.server import backend_statement_digest
pytestmark=pytest.mark.skipif(os.environ.get('FRAUD_NATIVE_ENABLED')!='1',reason='Requires native synthetic fraud stack')
class PrivateConfig(dict):
    def __repr__(self):return '<private local config>'

def test_real_dual_inference_replay_and_reference_substitution():
    cfg=PrivateConfig(json.loads(Path(os.environ['INTEGRATION_NATIVE_CONFIG']).read_text()))
    ref=json.loads(Path('reports/ui-feed-antifraud/synthetic-reference-manifest.json').read_text())[0]
    sid=str(uuid4()); body=dict(applicationId='dual-'+sid,submissionSnapshotId='submission-'+sid,
        financialStatementVersion=1,asOf='2026-10-22T12:00:00Z',latestSourceAvailableAt='2026-10-22T12:00:00Z',
        purpose='DEMO_RESEARCH',financialSnapshotId=sid,financialSnapshotDigest=backend_statement_digest(ref['statement'],1),financialStatement=ref['statement'])
    with httpx.Client(base_url='http://127.0.0.1:18000',headers={'X-Service-Token':cfg['token']},timeout=8) as c:
        features=c.post('/internal/v2/feature-snapshots',json=body,headers={'Idempotency-Key':'risk:'+sid+':features'});assert features.status_code==200
        f=features.json();r=c.post('/internal/v2/risk/evaluations',json=dict(requestId='risk:'+sid,featureSnapshotId=f['featureSnapshotId'],featureSnapshotDigest=f['snapshotDigest'],featureSchemaVersion=2,purpose='DEMO_RESEARCH'),headers={'Idempotency-Key':'risk:'+sid+':evaluation'});assert r.status_code==200
        request=dict(companyId='company-a',applicationId=body['applicationId'],attemptId=str(uuid4()),financialSnapshotId=sid,riskInferenceId=r.json()['inferenceId'],reference=ref)
        headers={'Idempotency-Key':'fraud:'+request['attemptId']}
        def call(_):return c.post('/internal/compat/v1/fraud/evaluations',json=request,headers=headers)
        with ThreadPoolExecutor(4) as pool:results=list(pool.map(call,range(4)))
        assert all(x.status_code==200 for x in results)
        result=results[0].json();assert all(x.json()==result for x in results)
        assert result['riskInferenceId']==r.json()['inferenceId'] and result['backendFinancialSnapshotDigest']==body['financialSnapshotDigest']
        assert result['referenceSource']=='SYNTHETIC_DEMO' and result['scoreKind']=='SYNTHETIC_MANIPULATION_PROXY'
        changed=copy.deepcopy(request);changed['reference']['statement']['values']['netProfitMinor']+=1
        changed['reference']['statementDigest']=digest(changed['reference']['statement']);changed['reference']['recordDigest']=digest({k:v for k,v in changed['reference'].items() if k!='recordDigest'})
        assert c.post('/internal/compat/v1/fraud/evaluations',json=changed,headers=headers).status_code==409
        foreign=copy.deepcopy(request);foreign['companyId']='company-b'
        assert c.post('/internal/compat/v1/fraud/evaluations',json=foreign,headers=headers).status_code==409
