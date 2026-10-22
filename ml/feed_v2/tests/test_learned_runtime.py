import json
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from ml.feed_v2.catalog import Catalog, digest
from ml.feed_v2.integration import FeedClient
from ml.feed_v2.learned import LearnedRanker
from ml.feed_v2.schemas import Profile
from ml.feed_v2.server import create_app


def test_factory_runs_e5_features_then_catboost(monkeypatch, learned_model, request_body):
    import os
    monkeypatch.setenv('FEED_RANKER', 'catboost')
    monkeypatch.setenv('FEED_BUNDLE', os.environ.get('FEED_LEARNED_TEST_BUNDLE', '.local/feed-catboost'))
    token = 'hybrid-factory-integration-test-token'
    app = create_app(token=token)
    with TestClient(app) as client:
        ranker = app.state.ranker
        assert isinstance(ranker, LearnedRanker)
        with patch.object(ranker.semantic.encoder, 'encode', wraps=ranker.semantic.encoder.encode) as encode:
            with patch.object(ranker.model, 'predict', wraps=ranker.model.predict) as predict:
                response = client.post('/internal/v2/rankings',
                    headers={'X-Service-Token': token, 'Idempotency-Key': request_body.requestId},
                    json=request_body.model_dump(mode='json'))
        assert response.status_code == 200
        assert response.json()['mode'] == 'MODEL'
        assert response.json()['releaseId'] == learned_model.release_id
        assert response.json()['rankedIds'] == learned_model.rank(request_body).rankedIds
        encode.assert_called_once()
        predict.assert_called_once()


def test_learned_real_offline_http_and_replay(monkeypatch, learned_model, request_body):
    monkeypatch.setenv('FEED_RANKER', 'catboost')
    token = 'offline-learned-api-test-token'
    with TestClient(create_app(token=token, ranker_factory=lambda *a, **kw: learned_model)) as client:
        headers = {'X-Service-Token':token,'Idempotency-Key':request_body.requestId}
        body = request_body.model_dump(mode='json')
        with patch('socket.socket.connect', side_effect=AssertionError('Network forbidden')):
            a = client.post('/internal/v2/rankings', headers=headers, json=body)
            b = client.post('/internal/v2/rankings', headers=headers, json=body)
        assert a.status_code == 200 and a.json() == b.json()
        assert a.json()['releaseId'].startswith('feed-catboost-')
        assert set(a.json()['rankedIds']) == set(request_body.candidateIds)
        assert client.post('/internal/v2/rankings', headers=headers,json=body|{'profile':{}}).json()['mode']=='RULES'
        assert client.get('/health',headers=headers).json()['releaseId'] == learned_model.release_id


def test_factory_selects_catboost_and_startup_failure_falls_back(monkeypatch, request_body):
    import httpx
    monkeypatch.setenv('FEED_RANKER','catboost')
    with TestClient(create_app(bundle=Path('/missing-test-bundle'), token='startup-failure-test-token')) as client:
        response = client.post('/internal/v2/rankings',json=request_body.model_dump(mode='json'),
            headers={'X-Service-Token':'startup-failure-test-token','Idempotency-Key':request_body.requestId})
        assert response.status_code == 503 and response.json()['fallbackAction']=='RULES'
        boundary = FeedClient(Catalog(),
            'http://feed','test-token',httpx.MockTransport(lambda r:httpx.Response(503)))
        try:
            assert boundary.rank(request_body).mode == 'RULES'
        finally:
            boundary.close()


def test_learned_corruption_rejected_before_encoder(tmp_path, learned_model):
    import os
    source=Path(os.environ.get('FEED_LEARNED_TEST_BUNDLE','.local/feed-catboost'))
    for name in ('manifest.json','model.cbm','training-report.json'):
        shutil.copy2(source/name,tmp_path/name)
    (tmp_path/'model.cbm').write_bytes(b'corrupted model')
    with patch('ml.feed_v2.learned.ModelRanker', side_effect=AssertionError('must validate first')):
        with pytest.raises(ValueError,match='checksum'):
            LearnedRanker(learned_model.catalog,tmp_path)


def test_learned_rejects_wrong_feature_schema(tmp_path, learned_model):
    import os
    source=Path(os.environ.get('FEED_LEARNED_TEST_BUNDLE','.local/feed-catboost'))
    manifest=json.loads((source/'manifest.json').read_text())
    manifest.pop('bundleDigest')
    manifest['featureSchemaVersion']='foreign-schema'
    manifest['bundleDigest']=digest(manifest)
    (tmp_path/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='feature/catalog/library'):
        LearnedRanker(learned_model.catalog,tmp_path)


def test_learned_single_and_partial_candidate_set(learned_model,request_body):
    from ml.feed_v2.integration import make_request
    for ids in [request_body.candidateIds[:1],request_body.candidateIds[-4:]]:
        request=make_request(learned_model.catalog,request_id='short',exposure_id='short-ex',candidate_ids=ids,profile=request_body.profile)
        assert set(learned_model.rank(request).rankedIds)==set(ids)
    assert learned_model.rank(request_body.model_copy(update={'profile':Profile()})).mode=='RULES'
