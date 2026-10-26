"""Seeded behavioral simulation; rewards never call a recommendation model."""
import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from .backend_reference import FeedbackProjection
from .catalog import Catalog, file_digest
from .dataset import ALL_FILES, Sink, VERSION, write_json
from .integration import eligible_ids, make_request
from .ranker import RulesRanker
from .schemas import Business, Depth, Help, Stage, Task, Topic


def utility(card, latent, profile):
    """Expected satisfaction in this stylized world, not empirical relevance."""
    z = -1.7 + 1.8 * latent['topics'][list(Topic).index(card.topic)]
    z += .65 * (card.depth.value == latent['depth'])
    z += .3 * (card.format == latent['format'])
    z += .55 * bool(profile.get('businessCategory') in card.businessCategories)
    z += .35 * bool(profile.get('applicationStage') in card.applicationStages)
    return float(1 / (1 + np.exp(-z)))


def generate(output, config=None):
    output = Path(output)
    if output.exists():
        raise FileExistsError('Use a new output directory to preserve dataset identity')
    config = config or json.loads(Path(__file__).with_name('simulation.json').read_text())
    if config['users'] < 10 or min(config['sessions'], config['pages']) < 1 or config['pageSize'] != 6:
        raise ValueError('Need >=10 contexts, positive sessions/pages and page size six')
    for key in ('randomPolicyShare', 'emptyProfileShare', 'partialProfileShare', 'intentStrength'):
        if not 0 <= config[key] <= 1:
            raise ValueError('Probability outside [0,1]: ' + key)
    if config['emptyProfileShare'] + config['partialProfileShare'] > 1 or config['positionDecay'] < 0:
        raise ValueError('Invalid profile mixture/position decay')
    rng = np.random.default_rng(config['seed'])
    catalog, rules = Catalog(), RulesRanker(Catalog())
    catalog.validate_editorial()
    sinks = {name: Sink(output / name) for name in ALL_FILES}
    assignments = rng.permutation(config['users'])
    splits = {int(u): ('train' if j < int(.7 * config['users']) else
                       'validation' if j < int(.85 * config['users']) else 'test')
              for j, u in enumerate(assignments)}
    accepted_order = 0
    base = datetime(2026, 10, 1, tzinfo=timezone.utc)
    try:
        for user in range(config['users']):
            context = dict(subjectId=f'SIM-U-{user:05}', companyId=f'SIM-C-{user:05}',
                           split=splits[user], isSynthetic=True)
            profile = dict(task=str(rng.choice([v.value for v in Task])), help=str(rng.choice([v.value for v in Help])),
                           depth=str(rng.choice([v.value for v in Depth])), businessCategory=str(rng.choice([v.value for v in Business])),
                           applicationStage=str(rng.choice([v.value for v in Stage])))
            # Sample latent preferences first; observable answers can be incomplete/noisy.
            intent = np.asarray(config['topicAffinity'][profile['task']])
            intent += np.asarray(config['helpAffinity'][profile['help']])
            topics = config['intentStrength'] * intent + rng.gamma(1.2, .45, 6)
            latent = dict(topics=topics.tolist(), depth=profile['depth'] if rng.random() < .8 else str(rng.choice([v.value for v in Depth])),
                          format=str(rng.choice(['ADVICE', 'SCENARIO', 'CHECKLIST'])))
            kind = rng.random()
            if kind < config['emptyProfileShare']:
                profile = {}
            elif kind < config['emptyProfileShare'] + config['partialProfileShare']:
                profile = {k: v for k, v in profile.items() if rng.random() < .5}
            state = FeedbackProjection(catalog)
            for session in range(config['sessions']):
                issued = set()
                session_id = f's-{user}-{session}'
                for page in range(config['pages']):
                    ids = eligible_ids(catalog, viewed=state.viewed, hidden=state.hidden, issued=issued)
                    if not ids:
                        break
                    exposure = f'ex-{user}-{session}-{page}'
                    now = base + timedelta(days=session, seconds=user * 10 + page * 120)
                    request = make_request(catalog, request_id='r-' + exposure, exposure_id=exposure,
                                           candidate_ids=ids, profile=profile, topic_reactions=state.topic_reactions)
                    policy = 'RANDOM' if rng.random() < config['randomPolicyShare'] else 'RULES'
                    ranked = rng.permutation(ids).tolist() if policy == 'RANDOM' else rules.rank(request).rankedIds
                    selected = ranked[:6]
                    state.issue(exposure, selected)
                    issued.update(selected)
                    shared = context | dict(exposureId=exposure, sessionId=session_id)
                    sinks['requests.parquet'].append(shared | dict(requestJson=request.model_dump_json(),
                        requestedAt=now.isoformat(), policy=policy,
                        releaseId='synthetic-random-v1' if policy == 'RANDOM' else 'feed-rules-v1',
                        experimentId='', variant='', randomizationUnit='context'))
                    expected = {i: utility(catalog.cards[i], latent, profile) for i in ids}
                    sinks['private/truth.parquet'].append(shared | dict(candidateIds=ids,
                        utilities=[expected[i] for i in ids], latentJson=json.dumps(latent)))
                    for position, item in enumerate(selected, 1):
                        sinks['issued.parquet'].append(shared | dict(itemId=item, position=position,
                            cardVersion=catalog.cards[item].version, issuedAt=now.isoformat()))
                        sat = expected[item]
                        visible = rng.random() < .93 * np.exp(-config['positionDecay'] * (position - 1))
                        actions = []
                        if visible:
                            actions.append('VIEW')
                            if rng.random() < .12 + .7 * sat:
                                actions.append('CLICK')
                                if rng.random() < .15 + .55 * sat:
                                    actions.append('HELPFUL')
                            if 'HELPFUL' not in actions and rng.random() < .07 + .5 * (1 - sat):
                                actions.append('NOT_INTERESTED')
                            # Exercise replacement rather than treating reactions as increments.
                            if actions[-1] == 'NOT_INTERESTED' and rng.random() < .04:
                                actions.append('HELPFUL')
                        for offset, action in enumerate(actions):
                            accepted_order += 1
                            at = (now + timedelta(seconds=position * 5 + offset + 1)).isoformat()
                            event = dict(clientEventId=f'e-{accepted_order}', itemId=item,
                                         exposureId=exposure, action=action, occurredAt=at)
                            state.apply(event, visible_fraction=.75, visible_ms=1200)
                            assert not state.apply(event, visible_fraction=.75, visible_ms=1200)
                            sinks['events.parquet'].append(shared | event | dict(acceptedOrder=accepted_order,
                                acceptedAt=at, visibleFraction=.75 if action == 'VIEW' else 0.,
                                visibleMs=1200 if action == 'VIEW' else 0))
    finally:
        for sink in sinks.values():
            sink.close()
    manifest = dict(generatorVersion=VERSION, isSynthetic=True, timestampsAreSynthetic=True,
                    config=config, catalogVersion=catalog.version, catalogDigest=catalog.digest,
                    counts={n: s.count for n, s in sinks.items()},
                    files={n: file_digest(output / n) for n in ALL_FILES},
                    limitations=['Synthetic outcomes describe the configured world, not real users.',
                                 'Private truth must never enter training features or labels.'])
    write_json(output / 'manifest.json', manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--config', type=Path, default=Path(__file__).with_name('simulation.json'))
    parser.add_argument('--users', type=int)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    if args.users is not None:
        config['users'] = args.users
    print(json.dumps(generate(args.output, config)['counts'], indent=2))


if __name__ == '__main__':
    main()
