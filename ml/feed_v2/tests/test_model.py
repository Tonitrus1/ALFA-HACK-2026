import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from ml.feed_v2.integration import eligible_ids, make_request
from ml.feed_v2.ranker import ModelRanker
from ml.feed_v2.schemas import RankingRequest


def test_real_e5_reviewed_scenarios_and_paraphrases(real_model, catalog):
    outputs = []
    for case in json.loads(Path('ml/feed_v2/fixtures/scenarios.json').read_text())['cases']:
        request = make_request(catalog, request_id=case['id'], exposure_id='ex-' + case['id'],
                               candidate_ids=sorted(catalog.cards), profile=case['profile'])
        with patch('socket.socket.connect', side_effect=AssertionError('Network forbidden during inference')):
            result = real_model.rank(request)
        assert result.mode == 'MODEL'
        assert set(case['expectedTop3Topics']) <= {catalog.cards[i].topic.value for i in result.rankedIds[:3]}
        vector = real_model.encoder.encode([case['paraphrase']])[0]
        assert vector.shape == (384,) and np.isclose(np.linalg.norm(vector), 1)
        scores = {i: float(real_model.vectors[i] @ vector) for i in request.candidateIds}
        paraphrased = real_model.result(request, scores, 'MODEL', real_model.release_id)
        assert set(case['expectedTop3Topics']) & {catalog.cards[i].topic.value for i in paraphrased.rankedIds[:3]}
        outputs.append(result.rankedIds[:6])
    assert outputs[0] != outputs[1]


def test_real_reactions_change_next_portion(real_model, catalog, request_body):
    first = real_model.rank(request_body).rankedIds[:6]
    remaining = eligible_ids(catalog, issued=first, hidden=['cash-01'])
    a = make_request(catalog, request_id='next-1', exposure_id='ex-next-1', candidate_ids=remaining,
                     profile=request_body.profile)
    b = a.model_copy(update={'topicReactions': RankingRequest.model_validate(a.model_dump() | {
        'topicReactions': {'CASH_GAP': {'helpful': 2}, 'WORKING_CAPITAL': {'notInterested': 2}}
    }).topicReactions})
    before, after = real_model.rank(a), real_model.rank(b)
    assert before.rankedIds[:6] != after.rankedIds[:6]
    assert set(after.rankedIds) == set(remaining)


def test_bundle_corruption_rejected(tmp_path, catalog):
    # Failure is checked before any model initialization.
    (tmp_path / 'manifest.json').write_text('{"bundleDigest":"' + '0' * 64 + '"}')
    with pytest.raises(ValueError, match='manifest digest'):
        ModelRanker(catalog, tmp_path)
