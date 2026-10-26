import copy,json,os,time,uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np
import joblib
import pytest
import requests
from jsonschema import Draft202012Validator
from scoring.client import RiskClient
from scoring.features import matrix,digest
ROOT=Path(__file__).resolve().parents[2]
BUNDLE=Path(os.environ.get('MODEL_BUNDLE',ROOT/'ml/artifacts/baseline'))
BASE_URL=os.environ.get('ML_BASE_URL','http://127.0.0.1:8001')
@pytest.fixture
def client():
    m=json.loads((BUNDLE/'manifest.json').read_text());return RiskClient(BASE_URL,os.environ['ML_INTERNAL_TOKEN'],m['bundleDigest'])
@pytest.fixture
def request_body(client):return client.snapshot_request(json.loads((ROOT/'ml/fixtures/scenarios.json').read_text())['companies'][0]['reference'])
def test_feature_and_risk_replay_concurrency_and_contract(client,request_body):
    a=client.create_snapshot(request_body);b=client.create_snapshot(request_body);assert a==b
    schema=json.loads((ROOT/'docs/architecture/contracts/feature-snapshot.schema.json').read_text());Draft202012Validator(schema).validate(a)
    body=client.risk_request(a)
    with ThreadPoolExecutor(4) as pool:responses=list(pool.map(lambda _:client.evaluate(body),range(4)))
    assert all(r==responses[0] for r in responses)
    response=responses[0];assert response['calibrationStatus']=='DEMONSTRATION' and response['scoreKind']=='BANKRUPTCY_PROXY'
    model=joblib.load(BUNDLE/'model.joblib');assert response['score']==float(model.predict_proba(matrix([request_body['financialStatement']]))[0,1])
    internal=json.loads((ROOT/'docs/architecture/contracts/internal.openapi.json').read_text())
    Draft202012Validator({'$ref':'#/components/schemas/MLRiskResult','components':internal['components']}).validate(response)
    bad={**body,'featureSnapshotDigest':'0'*64}
    with pytest.raises(requests.HTTPError) as e:client.evaluate(bad)
    assert e.value.response.status_code==409

def test_feature_input_digest_and_identity_conflicts(client,request_body):
    client.create_snapshot(request_body);bad=copy.deepcopy(request_body);bad['financialStatement']['values']['ebitMinor']+=100;bad['financialSnapshotDigest']=digest(bad['financialStatement'])
    with pytest.raises(requests.HTTPError) as e:client.create_snapshot(bad)
    assert e.value.response.status_code==409
    bad=copy.deepcopy(request_body);bad['submissionSnapshotId']=str(uuid.uuid4());bad['financialSnapshotDigest']='0'*64
    with pytest.raises(requests.HTTPError) as e:client.create_snapshot(bad)
    assert e.value.response.status_code==409

def test_forbidden_purpose_schema_raw_features_and_future_source(client,request_body):
    snap=client.create_snapshot(request_body);b=client.risk_request(snap)
    for body in [{**b,'purpose':'CREDIT_RISK'},{**b,'featureSchemaVersion':1},{**b,'score':0},{**b,'target_12m':0}]:
        with pytest.raises(requests.HTTPError) as e:client.evaluate(body)
        assert e.value.response.status_code==422
    bad={**request_body,'latestSourceAvailableAt':'2099-01-01T00:00:00Z'}
    with pytest.raises(requests.HTTPError) as e:client.create_snapshot(bad)
    assert e.value.response.status_code==422
    r=requests.get(BASE_URL+'/health');assert r.status_code==403

def test_zero_denominator_online(client,request_body):
    v=request_body['financialStatement']['values'];v.update(totalLiabilitiesMinor=0,currentLiabilitiesMinor=0,equityMinor=v['totalAssetsMinor']);request_body['financialSnapshotDigest']=digest(request_body['financialStatement'])
    snap=client.create_snapshot(request_body);assert set(snap['missingFeatures'])=={'X4','X8'}
    assert np.isfinite(client.evaluate(client.risk_request(snap))['score'])
