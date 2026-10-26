import json
from collections import Counter
from pathlib import Path

import pytest
from pydantic import ValidationError

from ml.feed_v2.catalog import Catalog, candidate_digest, digest
from ml.feed_v2.integration import eligible_ids
from ml.feed_v2.ranker import RankingError, RulesRanker, build_query, diversify, topic_bonus, validate_request
from ml.feed_v2.schemas import Profile, RankingRequest, Topic


def test_catalog_editorial_and_review_integrity(catalog):
    report = catalog.validate_editorial()
    assert report['cards'] == 72
    review = json.loads(Path('ml/feed_v2/catalog/review.json').read_text())
    assert review['catalogDigest'] == catalog.digest
    assert {c['id'] for c in review['cards']} == set(catalog.cards)
    assert all(c['approved'] for c in review['cards'])
    catalog.validate_publication(json.loads(Path('ml/feed_v2/release/catalog-index.json').read_text()))


def test_publication_rejects_changed_content_without_version_bump(catalog):
    previous = {'catalogDigest': '0' * 64, 'catalogVersion': catalog.version,
                'cards': {i: {'version': c.version, 'digest': digest(c.model_dump(mode='json'))}
                          for i, c in catalog.cards.items()}}
    with pytest.raises(ValueError, match='catalogVersion'):
        catalog.validate_publication(previous)
    previous['catalogVersion'] = catalog.version - 1
    previous['cards']['cash-01']['digest'] = '0' * 64
    with pytest.raises(ValueError, match='card must increment version'):
        catalog.validate_publication(previous)


def test_digest_is_order_independent(request_body):
    assert candidate_digest(request_body.candidateIds[::-1]) == request_body.candidateSetDigest


@pytest.mark.parametrize('patch,code', [
    ({'catalogVersion': 99}, 'CATALOG_MISMATCH'),
    ({'catalogDigest': '0' * 64}, 'CATALOG_MISMATCH'),
    ({'candidateSetDigest': '0' * 64}, 'CANDIDATE_SET_MISMATCH'),
    ({'candidateTexts': [{'itemId': 'working-01', 'text': 'Подменённый текст'}]}, 'CANDIDATE_TEXT_MISMATCH'),
])
def test_contract_conflicts(catalog, request_body, patch, code):
    with pytest.raises(RankingError) as error:
        RulesRanker(catalog).rank(RankingRequest.model_validate(request_body.model_dump() | patch))
    assert error.value.code == code


def test_unknown_id_rejected(catalog, request_body):
    body = request_body.model_copy(update={'candidateIds': ['foreign'], 'candidateSetDigest': candidate_digest(['foreign'])})
    with pytest.raises(RankingError, match='published catalog'):
        validate_request(catalog, body)


def test_exact_candidate_texts_and_stale_version(catalog, request_body):
    body = request_body.model_dump()
    body['candidateTexts'] = [{'itemId': i, 'text': catalog.cards[i].passage} for i in body['candidateIds']]
    validate_request(catalog, RankingRequest.model_validate(body))
    body['candidateTexts'][0]['text'] += ' '
    with pytest.raises(RankingError):
        validate_request(catalog, RankingRequest.model_validate(body))


@pytest.mark.parametrize('patch', [{'candidateIds': []}, {'candidateIds': ['cash-01', 'cash-01']},
                                  {'profile': {'companyTaxId': 'private'}},
                                  {'profile': {'task': 'ignore instructions'}},
                                  {'profile': {'depth': 'expert'}},
                                  {'topicReactions': {'CASH_GAP': {'helpful': -1}}},
                                  {'topicReactions': {'unknown': {'helpful': 1}}},
                                  {'contextText': 'Financial statement'}, {'scope': 'PRODUCT'}])
def test_invalid_and_sensitive_fields_forbidden(request_body, patch):
    with pytest.raises(ValidationError):
        RankingRequest.model_validate(request_body.model_dump() | patch)


def test_query_uses_only_known_fields():
    assert build_query(Profile()) == ''
    query = build_query(Profile(task='PURCHASE', help='COST', businessCategory='RETAIL', applicationStage='DRAFT'))
    assert query.startswith('query: ') and 'закупку' in query and 'комиссии' in query
    assert 'Розничная торговля' in query and 'черновик' in query


def test_feedback_clamp_and_depth_exact(catalog, request_body):
    ranker = RulesRanker(catalog)
    for pos, neg, expected in [(0, 0, 0), (1, 0, .05), (100, 0, .1), (0, 100, -.1), (5, 4, .05)]:
        body = RankingRequest.model_validate(request_body.model_dump() | {'topicReactions': {'CASH_GAP': {'helpful': pos, 'notInterested': neg}}})
        assert topic_bonus(body, Topic.CASH_GAP) == expected
    a = ranker.rank(request_body)
    b = ranker.rank(request_body.model_copy(update={'candidateIds': request_body.candidateIds[::-1]}))
    assert a.rankedIds == b.rankedIds


def test_diversity_permutation_and_stable_ties(catalog):
    ids = sorted(catalog.cards)
    scores = {i: 1. if catalog.cards[i].topic == Topic.CASH_GAP else 0. for i in ids}
    ranked = diversify(ids, scores, catalog)
    assert ranked[:2] == ['cash-01', 'cash-02']
    assert len(ranked) == len(ids) and set(ranked) == set(ids)
    for offset in range(0, len(ids), 6):
        assert max(Counter(catalog.cards[i].topic for i in ranked[offset:offset + 6]).values()) <= 2
    single = [i for i in ids if catalog.cards[i].topic == Topic.CASH_GAP]
    assert diversify(single[::-1], {i: 0 for i in single}, catalog) == single


def test_empty_profile_rules_and_candidates_exhaustion(catalog, request_body):
    result = RulesRanker(catalog).rank(request_body.model_copy(update={'profile': Profile()}))
    assert result.mode == 'RULES'
    assert all(catalog.cards[i].depth.value == 'BASICS' for i in result.rankedIds[:6])
    assert len({catalog.cards[i].topic for i in result.rankedIds[:6]}) >= 3
    assert eligible_ids(catalog, viewed=catalog.cards) == []


def test_reactions_reorder_following_portion(catalog, request_body):
    rules = RulesRanker(catalog)
    first = rules.rank(request_body).rankedIds[:6]
    remaining = eligible_ids(catalog, issued=first, hidden=['cash-01'])
    body = request_body.model_dump() | {'candidateIds': remaining, 'candidateSetDigest': candidate_digest(remaining)}
    before = rules.rank(RankingRequest.model_validate(body))
    body['topicReactions'] = {'CASH_GAP': {'helpful': 2}, 'WORKING_CAPITAL': {'notInterested': 2}}
    after = rules.rank(RankingRequest.model_validate(body))
    assert before.rankedIds[:6] != after.rankedIds[:6]
    assert not (set(after.rankedIds) & (set(first) | {'cash-01'}))
