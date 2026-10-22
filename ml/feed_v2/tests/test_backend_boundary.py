import pytest
import httpx

from ml.feed_v2.backend_reference import FeedbackProjection
from ml.feed_v2.integration import FeedClient, eligible_ids, feed_cards, replay_page
from ml.feed_v2.ranker import RulesRanker


def event(id='event-1', action='HELPFUL', item='cash-01', exposure='ex-1'):
    return dict(clientEventId=id, action=action, itemId=item, exposureId=exposure,
                occurredAt='2026-10-21T10:00:00Z')


def test_latest_reaction_replay_and_visibility(catalog):
    state = FeedbackProjection(catalog)
    state.issue('ex-1', ['cash-01', 'cash-02'])
    assert not state.viewed
    assert state.apply(event())
    assert not state.apply(event())
    state.apply(event(id='same-reaction-new-event'))
    assert state.topic_reactions['CASH_GAP'] == {'helpful': 1, 'notInterested': 0}
    state.apply(event(id='event-2', action='NOT_INTERESTED'))
    assert state.hidden == {'cash-01'} and not state.helpful
    assert state.topic_reactions['CASH_GAP'] == {'helpful': 0, 'notInterested': 1}
    assert 'cash-01' not in eligible_ids(catalog, hidden=state.hidden)
    state.apply(event(id='event-3'))
    assert state.helpful == {'cash-01'} and not state.hidden
    view = event(id='view-1', action='VIEW')
    for fraction, ms in [(.49, 2000), (.9, 999)]:
        with pytest.raises(ValueError): state.apply(view, visible_fraction=fraction, visible_ms=ms)
    state.apply(view, visible_fraction=.5, visible_ms=1000)
    assert state.viewed == {'cash-01'}


def test_foreign_contexts_unissued_and_event_conflicts(catalog):
    a, b = FeedbackProjection(catalog), FeedbackProjection(catalog)
    a.issue('ex-1', ['cash-01'])
    with pytest.raises(ValueError): b.apply(event())
    with pytest.raises(ValueError): a.apply(event(item='cash-02'))
    a.apply(event())
    with pytest.raises(ValueError): a.apply(event(action='NOT_INTERESTED'))
    with pytest.raises(ValueError): a.issue('ex-1', ['cash-02'])


def test_cursor_replay_omits_hidden_without_refill_or_reorder():
    page = {'cards': [{'contentId': i} for i in ['cash-01', 'cost-01', 'equipment-01']],
            'nextCursor': 'opaque-cursor', 'hasMore': True,
            'rankingMetadata': {'exposureId': 'ex-1'}}
    replay = replay_page(page, hidden=['cost-01'])
    assert [c['contentId'] for c in replay['cards']] == ['cash-01', 'equipment-01']
    assert replay['nextCursor'] == page['nextCursor'] and replay['rankingMetadata'] == page['rankingMetadata']
    assert len(page['cards']) == 3


@pytest.mark.parametrize('status', [429, 500, 502, 503, 504])
def test_backend_fallback_on_unavailability(catalog, request_body, status):
    client = FeedClient(catalog, 'http://feed', 'test-token', httpx.MockTransport(lambda r: httpx.Response(status)))
    try:
        assert client.rank(request_body) == RulesRanker(catalog).rank(request_body)
    finally:
        client.close()


def test_backend_transport_timeout_and_invalid_permutation(catalog, request_body):
    def timeout(request): raise httpx.ReadTimeout('timeout')
    for transport in [httpx.MockTransport(timeout),
                      httpx.MockTransport(lambda r: httpx.Response(200, json=RulesRanker(catalog).rank(request_body).model_dump(mode='json') | {'rankedIds': ['foreign']}))]:
        client = FeedClient(catalog, 'http://feed', 'test-token', transport)
        try: assert client.rank(request_body).mode == 'RULES'
        finally: client.close()


@pytest.mark.parametrize('status', [403, 409, 422])
def test_backend_does_not_hide_auth_or_catalog_errors(catalog, request_body, status):
    client = FeedClient(catalog, 'http://feed', 'test-token', httpx.MockTransport(lambda r: httpx.Response(status)))
    try:
        with pytest.raises(httpx.HTTPStatusError): client.rank(request_body)
    finally: client.close()


def test_client_sends_canonical_auth_header(catalog, request_body):
    def remote(request):
        assert request.headers['X-Service-Token'] == 'test-service-token'
        assert 'Authorization' not in request.headers
        assert request.headers['Idempotency-Key'] == request_body.requestId
        return httpx.Response(200, json=RulesRanker(catalog).rank(request_body).model_dump(mode='json'))
    client = FeedClient(catalog, 'http://feed', 'test-service-token', httpx.MockTransport(remote))
    try:
        assert client.rank(request_body).scope == 'FEED'
    finally:
        client.close()


@pytest.mark.parametrize('defect', ['missing_scope', 'wrong_scope', 'empty_reason', 'long_reason',
                                  'duplicate_id', 'missing_explanation', 'extra_explanation'])
def test_backend_rejects_invalid_success_responses(catalog, request_body, defect):
    payload = RulesRanker(catalog).rank(request_body).model_dump(mode='json')
    payload['mode'] = 'MODEL'
    if defect == 'missing_scope':
        payload.pop('scope')
    elif defect == 'wrong_scope':
        payload['scope'] = 'PRODUCT'
    elif defect == 'empty_reason':
        payload['reasonCategory'] = ''
    elif defect == 'long_reason':
        payload['reasonCategory'] = 'x' * 129
    elif defect == 'duplicate_id':
        payload['rankedIds'][0] = payload['rankedIds'][1]
    elif defect == 'missing_explanation':
        payload['explanations'].pop(payload['rankedIds'][0])
    else:
        payload['explanations']['foreign'] = next(iter(payload['explanations'].values()))
    client = FeedClient(catalog, 'http://feed', 'test-token',
                        httpx.MockTransport(lambda r: httpx.Response(200, json=payload)))
    try:
        assert client.rank(request_body) == RulesRanker(catalog).rank(request_body)
    finally:
        client.close()


def test_card_reactions_are_supplied_by_backend_state(catalog, request_body):
    ranked = RulesRanker(catalog).rank(request_body)
    item = ranked.rankedIds[0]
    cards = feed_cards(catalog, ranked, reactions={item: 'HELPFUL'})
    assert cards[0]['userReaction'] == 'HELPFUL'
    assert all(c['userReaction'] is None for c in cards[1:])


def test_replay_refreshes_reactions_without_changing_snapshot():
    snapshot = {'cards': [{'contentId': 'cash-01', 'userReaction': None},
                          {'contentId': 'cost-01', 'userReaction': None}],
                'nextCursor': 'same-cursor', 'rankingMetadata': {'exposureId': 'same-exposure'}}
    replay = replay_page(snapshot, hidden=['cost-01'], reactions={'cash-01': 'HELPFUL'})
    assert replay['cards'] == [{'contentId': 'cash-01', 'userReaction': 'HELPFUL'}]
    assert replay['nextCursor'] == snapshot['nextCursor']
    assert replay['rankingMetadata'] == snapshot['rankingMetadata']
    assert snapshot['cards'][0]['userReaction'] is None
    assert len(snapshot['cards']) == 2
