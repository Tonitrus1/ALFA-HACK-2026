"""Reproducible ML-only feed demonstration, with the real HTTP contract."""
import argparse
import json
from pathlib import Path

from .backend_reference import FeedbackProjection
from .catalog import Catalog
from .dataset import write_json
from .integration import eligible_ids, feed_cards, make_request
from .learned import LearnedRanker


def demo(bundle, output):
    catalog = Catalog()
    model = LearnedRanker(catalog, bundle)
    state = FeedbackProjection(catalog)
    profile = dict(task='PURCHASE', help='COST', depth='EXPLAINED', businessCategory='RETAIL')
    first_request = make_request(catalog, request_id='demo-first', exposure_id='demo-ex-1',
        candidate_ids=sorted(catalog.cards), profile=profile)
    first = model.rank(first_request)
    selected = first.rankedIds[:6]
    state.issue('demo-ex-1', selected)
    # React to two different topics, then rank only the unissued remainder.
    positive = selected[0]
    negative = next(i for i in selected if catalog.cards[i].topic != catalog.cards[positive].topic)
    events = []
    for j, (item, action) in enumerate(((positive, 'HELPFUL'), (negative, 'NOT_INTERESTED'))):
        event = dict(clientEventId=f'demo-event-{j}', itemId=item, exposureId='demo-ex-1',
                     action=action, occurredAt=f'2026-10-22T10:00:0{j}Z')
        state.apply(event)
        events.append(event)
    remaining = eligible_ids(catalog, issued=selected, hidden=state.hidden)
    before_request = make_request(catalog, request_id='demo-before', exposure_id='demo-ex-2',
        candidate_ids=remaining, profile=profile)
    after_request = make_request(catalog, request_id='demo-after', exposure_id='demo-ex-2',
        candidate_ids=remaining, profile=profile, topic_reactions=state.topic_reactions)
    before, after = model.rank(before_request), model.rank(after_request)
    report = dict(isSynthetic=True, releaseId=model.release_id, profile=profile,
        firstRequest=first_request.model_dump(mode='json'), firstPage=feed_cards(catalog, first),
        acceptedEvents=events, nextRequest=after_request.model_dump(mode='json'),
        nextPageWithoutReactions=feed_cards(catalog, before), nextPageWithReactions=feed_cards(catalog, after),
        nextPageChanged=before.rankedIds[:6] != after.rankedIds[:6],
        reactions=state.topic_reactions,
        limitations=['No backend or UI is implemented; this is the ML integration scenario.',
                     'Reaction-driven change is measured, not forced by adding manual boosts.'])
    write_json(output, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, default=Path('.local/feed-catboost'))
    parser.add_argument('--output', type=Path, default=Path('reports/hackathon/demo.json'))
    args = parser.parse_args()
    result = demo(args.bundle, args.output)
    print(json.dumps({k: result[k] for k in ('releaseId', 'nextPageChanged')}, indent=2))


if __name__ == '__main__':
    main()
