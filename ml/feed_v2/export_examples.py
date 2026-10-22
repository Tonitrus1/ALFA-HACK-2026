"""Regenerate snapshots from the one catalog and the prepared real E5 bundle."""
import json
from pathlib import Path

from .catalog import Catalog, candidate_digest
from .integration import feed_cards, make_request
from .ranker import ModelRanker, RulesRanker
from .server import create_app


def main():
    catalog = Catalog()
    engine = ModelRanker(catalog, Path('.local/feed-bundle'))
    root = Path(__file__).parent / 'examples'
    fixtures = json.loads(Path(__file__).with_name('fixtures').joinpath('scenarios.json').read_text())

    def write(name, value):
        (root / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

    for case in fixtures['cases'][:2]:
        request = make_request(catalog, request_id=case['id'], exposure_id='ex-' + case['id'],
                               candidate_ids=sorted(catalog.cards), profile=case['profile'])
        result = engine.rank(request)
        write(case['id'] + '.request.json', request.model_dump(mode='json', exclude_none=True))
        write(case['id'] + '.response.json', result.model_dump(mode='json'))
        write(case['id'] + '.feed.json', {
            'cards': feed_cards(catalog, result), 'rankingMode': result.mode,
            'rankingMetadata': {'exposureId': result.exposureId, 'releaseId': result.releaseId,
                                'mode': result.mode, 'candidateSetDigest': result.candidateSetDigest,
                                'catalogVersion': catalog.version, 'catalogDigest': catalog.digest},
            'hasMore': True, 'nextCursor': 'opaque-backend-cursor-example'})
    cold = make_request(catalog, request_id='intro', exposure_id='ex-intro',
                        candidate_ids=sorted(catalog.cards), profile={})
    write('intro.request.json', cold.model_dump(mode='json', exclude_none=True))
    write('intro.response.json', RulesRanker(catalog).rank(cold).model_dump(mode='json'))
    write('preferences.json', fixtures['cases'][0]['profile'])
    for action in ['VIEW', 'HELPFUL', 'NOT_INTERESTED']:
        write('feedback-' + action.lower() + '.json', {
            'clientEventId': 'event-' + action.lower(), 'exposureId': 'ex-purchase-cost',
            'itemId': 'working-03', 'action': action, 'occurredAt': '2026-10-21T10:00:00Z'})
    write('empty.feed.json', {'cards': [], 'rankingMode': 'RULES', 'hasMore': False,
                             'rankingMetadata': {'exposureId': 'ex-empty', 'releaseId': 'feed-rules-v1',
                                                 'mode': 'RULES', 'candidateSetDigest': candidate_digest([]),
                                                 'catalogVersion': catalog.version, 'catalogDigest': catalog.digest}})
    saved_cards = feed_cards(catalog, RulesRanker(catalog).rank(cold),
                            reactions={i: 'HELPFUL' for i in cold.candidateIds})[:2]
    for card in saved_cards:
        card.update(reasonCategory='SAVED_HELPFUL', reason='Вы отметили этот материал как полезный.')
    write('saved-cards.json', {'cards': saved_cards, 'exposureId': 'ex-saved-example',
                             'catalogVersion': catalog.version, 'catalogDigest': catalog.digest,
                             'savedVersion': 2, 'hasMore': False})
    write('saved-empty.json', {'cards': [], 'exposureId': 'ex-saved-empty',
                             'catalogVersion': catalog.version, 'catalogDigest': catalog.digest,
                             'savedVersion': 0, 'hasMore': False})
    Path(__file__).with_name('openapi.json').write_text(
        json.dumps(create_app(token='example-for-schema-export-only').openapi(), ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
