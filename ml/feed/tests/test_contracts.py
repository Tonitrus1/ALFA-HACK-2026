import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from ml.feed.catalog import candidate_digest
from ml.feed.schemas import RankingRequest, RankingResult

ROOT = Path('docs/architecture/contracts')
EXAMPLES = Path('ml/feed/examples')


def validator(kind, name):
    document = json.loads((ROOT / (kind + '.openapi.json')).read_text())
    return Draft202012Validator({'$ref': '#/components/schemas/' + name,
                                'components': document['components']})


def test_requests_responses_and_cards_match_canonical_contracts(catalog):
    for path in EXAMPLES.glob('*.request.json'):
        value = json.loads(path.read_text())
        validator('internal', 'MLRankingRequest').validate(value)
        RankingRequest.model_validate(value)
    for path in EXAMPLES.glob('*.response.json'):
        value = json.loads(path.read_text())
        validator('internal', 'MLRankingResult').validate(value)
        RankingResult.model_validate(value)
    for path in EXAMPLES.glob('*.feed.json'):
        value = json.loads(path.read_text())
        validator('public', 'Feed').validate(value)
        for card in value['cards']:
            source = catalog.cards[card['contentId']]
            assert card['title'] == source.title and card['text'] == source.text
            assert card['version'] == source.version
    for path in EXAMPLES.glob('feedback-*.json'):
        validator('public', 'MLRecommendationFeedback').validate(json.loads(path.read_text()))
    validator('public', 'FeedPreferences').validate(json.loads((EXAMPLES / 'preferences.json').read_text()))


def test_feed_schema_requires_empty_profile_but_product_is_unchanged(request_body):
    schema = validator('internal', 'MLRankingRequest')
    value = request_body.model_dump(mode='json', exclude_none=True)
    assert schema.is_valid(value | {'profile': {}})
    assert not schema.is_valid({k: v for k, v in value.items() if k != 'profile'})
    assert not schema.is_valid(value | {'contextText': 'raw untrusted text'})
    product = dict(requestId='product', scope='PRODUCT', candidateIds=['product-a'],
                   candidateSetDigest=candidate_digest(['product-a']), catalogVersion=1,
                   eligibilityVersion=1, stage='NEED', contextCategory='SME', fundingPurpose='Оборот',
                   contextText='Закупка', candidateTexts=[{'itemId': 'product-a', 'text': 'Продукт'}])
    assert schema.is_valid(product)
    assert not schema.is_valid({k: v for k, v in product.items() if k != 'contextText'})


def test_feed_cursor_contract():
    schema = validator('public', 'Feed')
    empty = json.loads((EXAMPLES / 'empty.feed.json').read_text())
    assert schema.is_valid(empty)
    assert not schema.is_valid(empty | {'hasMore': True})
    assert not schema.is_valid(empty | {'nextCursor': 'unnecessary'})


def test_saved_cards_and_cursor_contract():
    schema = validator('public', 'SavedFeed')
    saved = json.loads((EXAMPLES / 'saved-cards.json').read_text())
    empty = json.loads((EXAMPLES / 'saved-empty.json').read_text())
    schema.validate(saved)
    schema.validate(empty)
    assert not schema.is_valid(saved | {'hasMore': True})
    schema.validate(saved | {'hasMore': True, 'nextCursor': 'saved-cursor'})
    assert not schema.is_valid(saved | {'nextCursor': 'unexpected'})
    for field in ['exposureId', 'savedVersion', 'catalogDigest']:
        assert not schema.is_valid({k: v for k, v in saved.items() if k != field})
    assert not schema.is_valid(saved | {'savedVersion': -1})
    for reaction in ['NOT_INTERESTED', None]:
        invalid = deepcopy(saved)
        invalid['cards'][0]['userReaction'] = reaction
        assert not schema.is_valid(invalid)
    spec = json.loads((ROOT / 'public.openapi.json').read_text())
    op = spec['paths']['/api/v1/feed/saved']['get']
    assert op['operationId'] == 'getSavedFeed'
    assert op['responses']['200']['content']['application/json']['schema'] == {
        '$ref': '#/components/schemas/SavedFeed'}
    assert {'companyId', 'X-Company-Context'} == {
        p['name'] for p in op['parameters'] if p.get('required')}


def test_result_boundary_matches_canonical_required_fields():
    result = json.loads((EXAMPLES / 'purchase-cost.response.json').read_text())
    canonical = validator('internal', 'MLRankingResult')
    for patch in [{'scope': 'PRODUCT'}, {'reasonCategory': ''}, {'reasonCategory': 'x' * 129}]:
        invalid = result | patch
        if patch.get('scope') != 'PRODUCT':
            assert not canonical.is_valid(invalid)
        with pytest.raises(ValidationError):
            RankingResult.model_validate(invalid)
    missing_scope = {k: v for k, v in result.items() if k != 'scope'}
    assert not canonical.is_valid(missing_scope)
    with pytest.raises(ValidationError):
        RankingResult.model_validate(missing_scope)


def test_exported_openapi_is_current():
    from ml.feed.server import create_app

    exported = json.loads(Path('ml/feed/openapi.json').read_text())
    assert exported == create_app(token='test-schema-token-not-secret').openapi()
