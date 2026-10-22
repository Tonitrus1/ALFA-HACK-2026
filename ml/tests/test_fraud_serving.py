import copy
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import joblib
import pytest
import requests

from scoring.client import RiskClient
from scoring.decision_client import DecisionClient
from scoring.features import digest
from scoring.fraud_features import matrix

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT/'ml/artifacts/fraud-demo-v1'


@pytest.fixture
def setup_attempt():
    manifest = json.loads((ROOT/'ml/artifacts/baseline/manifest.json').read_text())
    fraud_manifest = json.loads((BUNDLE/'manifest.json').read_text())
    policy = json.loads((BUNDLE/'policy.json').read_text())
    client = RiskClient(os.environ.get('ML_API_URL', 'http://127.0.0.1:8001'), os.environ['ML_INTERNAL_TOKEN'], manifest['bundleDigest'])
    reference = copy.deepcopy(json.loads((ROOT/'ml/fixtures/scenarios.json').read_text())['companies'][0]['reference'])
    return client, DecisionClient(client, fraud_manifest, policy), reference


def evaluated(setup_attempt):
    client, decision, reference = setup_attempt
    body = client.snapshot_request(reference)
    result = decision.evaluate(body, reference, 'REF:'+str(uuid4()), 20000000, 12)
    assert result['failure'] is None, result['failure']
    return client, decision, reference, body, result


def test_two_real_models_replay_concurrency_and_snapshots(setup_attempt):
    client, decision, reference, body, result = evaluated(setup_attempt)
    request = result['fraudRequest']
    with ThreadPoolExecutor(4) as pool:
        copies = list(pool.map(lambda _: client.call('/internal/v1/fraud/evaluations', request), range(4)))
    assert all(r == result['fraudInference'] for r in copies)
    assert client.call('/internal/v1/fraud/feature-snapshots', result['fraudSnapshotRequest']) == result['fraudSnapshot']
    assert client.call('/internal/v1/fraud/feature-snapshots/'+request['featureSnapshotId']) == result['fraudSnapshot']
    model = joblib.load(BUNDLE/'model.joblib')
    assert float(model.predict_proba(matrix([{'statement': reference, 'reference': reference}]))[0, 1]) == result['fraudInference']['score']
    # Same immutable attempt and same request key, different requested amount:
    # both model results are reused exactly; only the offer policy changes.
    another = decision.evaluate(body, reference, result['fraudSnapshotRequest']['referenceSnapshotId'],
                                900000000, 12, request_id=result['requestId'])
    assert another['inference'] == result['inference'] and another['fraudInference'] == result['fraudInference']
    assert another['policy']['outcome'] == 'ALTERNATIVE'


@pytest.mark.parametrize('change', ['reference', 'application', 'submission', 'digest', 'financial'])
def test_reference_substitution_and_mixed_snapshots_rejected(setup_attempt, change):
    client, _, _, _, result = evaluated(setup_attempt)
    body = copy.deepcopy(result['fraudSnapshotRequest'])
    if change == 'reference':
        body['referenceStatement']['values']['revenueMinor'] += 100
        body['referenceSnapshotDigest'] = digest(body['referenceStatement'])
    elif change == 'digest':
        body['referenceSnapshotDigest'] = '0'*64
    elif change == 'financial':
        body['financialStatement']['values']['revenueMinor'] += 100
        body['financialSnapshotDigest'] = digest(body['financialStatement'])
    else:
        body['applicationId' if change == 'application' else 'submissionSnapshotId'] = str(uuid4())
    with pytest.raises(requests.HTTPError) as exc:
        client.call('/internal/v1/fraud/feature-snapshots', body)
    assert exc.value.response.status_code == 409


def test_mixed_inference_request_digest_bundle_and_forbidden_features(setup_attempt):
    client, _, _, _, result = evaluated(setup_attempt)
    other = evaluated(setup_attempt)[-1]
    for field, value in [('riskInferenceId', other['inference']['inferenceId']),
                         ('featureSnapshotDigest', '0'*64), ('bundleDigest', '0'*64)]:
        bad = {**result['fraudRequest'], field: value}
        with pytest.raises(requests.HTTPError) as exc:
            client.call('/internal/v1/fraud/evaluations', bad)
        assert exc.value.response.status_code == 409
    # New key must also be rejected on binding, rather than only idempotency.
    bad = {**result['fraudRequest'], 'requestId': str(uuid4()), 'riskInferenceId': other['inference']['inferenceId']}
    with pytest.raises(requests.HTTPError) as exc:
        client.call('/internal/v1/fraud/evaluations', bad)
    assert exc.value.response.status_code == 409
    for field in ('score', 'target', 'features', 'family'):
        with pytest.raises(requests.HTTPError) as exc:
            client.call('/internal/v1/fraud/evaluations', {**result['fraudRequest'], field: 0})
        assert exc.value.response.status_code == 422
    bad = {**result['fraudSnapshotRequest'], 'referenceAvailableAt': '2099-01-01T00:00:00Z'}
    with pytest.raises(requests.HTTPError) as exc:
        client.call('/internal/v1/fraud/feature-snapshots', bad)
    assert exc.value.response.status_code == 422
    assert requests.get(client.base_url+'/internal/v1/fraud/bundle', timeout=3).status_code == 403


@pytest.mark.parametrize('fault', ['risk', 'fraud'])
def test_failure_of_either_model_never_approves(setup_attempt, fault):
    client, decision, reference = setup_attempt
    result = decision.evaluate(client.snapshot_request(reference), reference, str(uuid4()), 20000000, 12, fault=fault)
    assert result['policy']['rule'] == 'ML_FAILURE' and result['policy']['outcome'] == 'MANUAL'
    assert result['fraudInference'] is None
    assert (result['inference'] is None) == (fault == 'risk')
    assert result['seconds'] < 3


def test_late_response_and_response_substitution_never_approve(setup_attempt, monkeypatch):
    client, decision, reference = setup_attempt
    clock = [0.]
    monkeypatch.setattr('scoring.decision_client.time.monotonic', lambda: clock[0])
    real_call = client.call
    timeouts = []
    def late_call(path, body, **kwargs):
        timeouts.append(kwargs['timeout'])
        response = real_call(path, body, **kwargs)
        clock[0] += 1.1
        return response
    monkeypatch.setattr(client, 'call', late_call)
    result = decision.evaluate(client.snapshot_request(reference), reference, str(uuid4()), 20000000, 12)
    assert result['policy']['rule'] == 'ML_FAILURE'
    assert timeouts[0] > timeouts[1] > timeouts[2]
    assert 'Late result' in result['failure']


def test_bad_response_and_disabled_gate_do_not_approve(setup_attempt, monkeypatch):
    client, decision, reference = setup_attempt
    real_call = client.call
    def substituted(path, body, **kwargs):
        response = real_call(path, body, **kwargs)
        if path.endswith('/fraud/evaluations'):
            response['submissionSnapshotId'] = 'wrong-attempt'
        return response
    monkeypatch.setattr(client, 'call', substituted)
    result = decision.evaluate(client.snapshot_request(reference), reference, str(uuid4()), 20000000, 12)
    assert result['policy']['rule'] == 'ML_FAILURE'
    decision.fraud_manifest = {**decision.fraud_manifest, 'routingEnabled': False}
    result = decision.evaluate(client.snapshot_request(reference), reference, str(uuid4()), 20000000, 12)
    assert result['policy']['rule'] == 'ML_FAILURE' and result['inference'] is None
