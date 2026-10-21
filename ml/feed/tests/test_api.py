import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from ml.feed.server import create_app

TOKEN = 'test-feed-internal-token-123'


def unavailable(*args, **kwargs):
    raise FileNotFoundError('Weights unavailable')


def test_auth_validation_and_failure_modes(request_body):
    with TestClient(create_app(token=TOKEN, ranker_factory=unavailable)) as client:
        assert client.get('/health').status_code == 403
        headers = {'X-Service-Token': TOKEN, 'Idempotency-Key': request_body.requestId}
        assert client.get('/health', headers=headers).status_code == 503
        payload = request_body.model_dump(mode='json', exclude_none=True)
        response = client.post('/internal/v2/rankings', headers=headers, json=payload)
        assert response.status_code == 503 and response.json()['fallbackAction'] == 'RULES'
        assert response.headers['Cache-Control'] == 'no-store'
        for bad in [{}, payload | {'candidateIds': []}, payload | {'profile': {'taxId': 'sensitive'}}]:
            response = client.post('/internal/v2/rankings', headers=headers, json=bad)
            assert response.status_code == 422
            assert 'sensitive' not in response.text
        response = client.post('/internal/v2/rankings', headers=headers, json=payload | {'catalogVersion': 99})
        assert response.status_code == 409 and response.json()['code'] == 'CATALOG_MISMATCH'
        response = client.post('/internal/v2/rankings', headers=headers, json=payload | {'profile': {}})
        assert response.status_code == 200 and response.json()['mode'] == 'RULES'
        assert response.json()['exposureId'] == payload['exposureId']
        assert client.post('/internal/v2/rankings', headers={'X-Service-Token': TOKEN}, json=payload).status_code == 422
        assert client.post('/internal/v2/rankings', headers=headers | {'Idempotency-Key': 'other'}, json=payload).status_code == 409


def test_token_required():
    with pytest.raises(RuntimeError): create_app(token='short')


def test_model_http_and_replay(real_model, request_body):
    with TestClient(create_app(token=TOKEN, ranker_factory=lambda *a, **kw: real_model)) as client:
        headers = {'X-Service-Token': TOKEN, 'Idempotency-Key': request_body.requestId}
        body = request_body.model_dump(mode='json', exclude_none=True)
        assert client.get('/health', headers=headers).status_code == 200
        a = client.post('/internal/v2/rankings', headers=headers, json=body)
        b = client.post('/internal/v2/rankings', headers=headers, json=body)
        assert a.status_code == 200 and a.json() == b.json() and a.json()['mode'] == 'MODEL'


def test_canonical_service_identity_and_documented_errors(request_body):
    canonical = json.loads(Path('docs/architecture/contracts/internal.openapi.json').read_text())
    with TestClient(create_app(token=TOKEN, ranker_factory=unavailable)) as client:
        spec = client.get('/openapi.json').json()
        identity = canonical['components']['securitySchemes']['ServiceIdentity']
        runtime_identity = spec['components']['securitySchemes']['ServiceIdentity']
        assert {k: runtime_identity[k] for k in ('type', 'in', 'name')} == {
            k: identity[k] for k in ('type', 'in', 'name')}
        operation = spec['paths']['/internal/v2/rankings']['post']
        assert operation['security'] == [{'ServiceIdentity': []}]
        assert operation['operationId'] == 'rankEligibleCandidates'
        assert {'200', '403', '409', '422', '503'} <= set(operation['responses'])
        body = request_body.model_dump(mode='json', exclude_none=True)
        headers = {identity['name']: TOKEN, 'Idempotency-Key': request_body.requestId}
        responses = [
            client.post('/internal/v2/rankings', headers={'Authorization': 'Bearer ' + TOKEN}, json=body),
            client.post('/internal/v2/rankings', headers=headers, json=body | {'catalogVersion': 999}),
            client.post('/internal/v2/rankings', headers=headers, json={}),
            client.post('/internal/v2/rankings', headers=headers, json=body),
        ]
        assert [r.status_code for r in responses] == [403, 409, 422, 503]
        for response in responses:
            definition = operation['responses'][str(response.status_code)]
            schema = definition['content']['application/json']['schema']
            assert schema == {'$ref': '#/components/schemas/MLError'}
            Draft202012Validator({**schema, 'components': spec['components']}).validate(response.json())
            Draft202012Validator({'$ref': '#/components/schemas/MLError',
                                  'components': canonical['components']}).validate(response.json())
            assert response.headers['Cache-Control'] == 'no-store'
        assert responses[-1].headers['Retry-After'] == '5'
        assert client.get('/health', headers=headers).status_code == 503
