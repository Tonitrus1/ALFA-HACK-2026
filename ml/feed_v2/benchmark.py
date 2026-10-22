"""Locked-test comparison. Oracle metrics are explicitly synthetic, not user benefit."""
import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from .catalog import Catalog, digest, file_digest
from .dataset import load_manifest, rows, write_json
from .learned import LearnedRanker
from .metrics import clustered_interval, quality
from .ranker import RulesRanker, build_query, diversify, topic_bonus
from .schemas import RankingRequest

ALGORITHMS = ('random', 'rules', 'e5', 'e5_rules', 'catboost')


def orders(request, learned):
    ids, catalog = request.candidateIds, learned.catalog
    if not build_query(request.profile):
        scores = RulesRanker(catalog).base_scores(request)
        for i in ids:
            scores[i] += topic_bonus(request, catalog.cards[i].topic) + .03 * bool(request.profile.depth == catalog.cards[i].depth)
        raw = sorted(ids, key=lambda i: (-scores[i], i))
        final = diversify(ids, scores, catalog)
        return {name: (raw, final) for name in ALGORITHMS}
    seed = int(digest(request.exposureId)[:16], 16)
    random_order = np.random.default_rng(seed).permutation(ids).tolist()
    scores = dict(random={i: float(-j) for j, i in enumerate(random_order)},
                  rules=RulesRanker(catalog).base_scores(request),
                  e5={i: learned.features.similarities(request)[i] for i in ids},
                  catboost=learned.scores(request))
    scores['e5_rules'] = dict(scores['e5'])
    for name in ('rules', 'e5_rules'):
        for i in ids:
            scores[name][i] += topic_bonus(request, catalog.cards[i].topic) + .03 * bool(request.profile.depth == catalog.cards[i].depth)
    return {name: (sorted(ids, key=lambda i: (-scores[name][i], i)),
                   diversify(ids, scores[name], catalog)) for name in ALGORITHMS}


def semantic_scenarios(learned):
    fixtures = json.loads(Path(__file__).with_name('fixtures').joinpath('scenarios.json').read_text())['cases']
    from .integration import make_request
    results = []
    for case in fixtures:
        request = make_request(learned.catalog, request_id=case['id'], exposure_id='ex-' + case['id'],
                               candidate_ids=sorted(learned.catalog.cards), profile=case['profile'])
        result = learned.rank(request)
        actual = {learned.catalog.cards[i].topic.value for i in result.rankedIds[:3]}
        results.append(dict(id=case['id'], expected=case['expectedTop3Topics'], actual=sorted(actual),
                            passed=set(case['expectedTop3Topics']) <= actual))
    return results


def content_review(learned, path):
    document = json.loads(Path(path).read_text())
    if document['catalogDigest'] != learned.catalog.digest:
        raise ValueError('Content-review catalog mismatch')
    if (len(document['cases']) != 24
            or len({c['id'] for c in document['cases']}) != 24
            or len({digest(c['profile']) for c in document['cases']}) != 24
            or sum(c['split'] == 'development' for c in document['cases']) != 12):
        raise ValueError('Require 24 distinct review profiles with 12 development cases')
    # AI draft never satisfies the independent human-review gate.
    closed = [c for c in document['cases'] if c['split'] == 'test']
    values = defaultdict(list)
    for case in closed:
        if (set(case['grades']) != set(learned.catalog.cards)
                or any(type(v) is not int or not 0 <= v <= 3 for v in case['grades'].values())):
            raise ValueError('Content review requires complete card judgments')
        from .integration import make_request
        request = make_request(learned.catalog, request_id=case['id'], exposure_id=case['id'],
                               candidate_ids=sorted(learned.catalog.cards), profile=case['profile'])
        for name, (_, final) in orders(request, learned).items():
            values[name].append(quality(final, case['grades'])['ndcg6'])
    score = {k: float(np.mean(v)) for k, v in values.items()}
    reviewed = (document.get('reviewKind') == 'HUMAN_REVIEW' and bool(document.get('reviewer'))
                and len(closed) >= 12 and len(document['cases']) >= 24)
    return dict(status='reviewed' if reviewed else 'pending_human_review', independentHumanReview=reviewed,
                cases=len(closed), fixtureDigest=file_digest(Path(path)), draftMetrics=score,
                passed=reviewed and score['catboost'] >= score['e5_rules'] - .02)


def benchmark(data, bundle, output, review=None, split='test'):
    output = Path(output)
    if output.exists():
        raise FileExistsError('A benchmark report is immutable; select a new output')
    manifest = load_manifest(data, truth=True)
    learned = LearnedRanker(Catalog(), bundle)
    if manifest['catalogDigest'] != learned.catalog.digest:
        raise ValueError('Benchmark catalog mismatch')
    oracle = {r['exposureId']: r for r in rows(data, 'private/truth.parquet') if r['split'] == split}
    values, slices, coverage = defaultdict(list), defaultdict(lambda: defaultdict(list)), defaultdict(set)
    clusters = defaultdict(lambda: defaultdict(list))
    contexts, count = set(), 0
    for row in rows(data, 'requests.parquet'):
        if row['split'] != split:
            continue
        request = RankingRequest.model_validate_json(row['requestJson'])
        truth = oracle.pop(row['exposureId'])
        if truth['candidateIds'] != request.candidateIds or truth['subjectId'] != row['subjectId']:
            raise ValueError('Oracle/request lineage mismatch')
        expected = dict(zip(truth['candidateIds'], truth['utilities']))
        relevance = {i: int(np.digitize(u, [.35, .55, .75])) for i, u in expected.items()}
        context = row['subjectId'] + '/' + row['companyId']
        contexts.add(context)
        p = request.profile
        groups = ['business:' + (p.businessCategory or 'MISSING'), 'depth:' + (p.depth or 'MISSING'),
                  'task:' + (p.task or 'MISSING'), 'profile:' + ('empty' if not build_query(p) else 'present'),
                  'history:' + ('present' if request.topicReactions else 'empty')]
        for name, (raw, final) in orders(request, learned).items():
            for phase, ordered in [('raw', raw), ('diversified', final)]:
                scores = quality(ordered, relevance)
                scores['topics6'] = len({learned.catalog.cards[i].topic for i in ordered[:6]})
                # Expected explicit rejection under the simulator's response model.
                rates = []
                for pos, i in enumerate(ordered[:6]):
                    sat = expected[i]
                    visible = .93 * np.exp(-manifest['config']['positionDecay'] * pos)
                    rates.append(visible * (1 - (.12 + .7 * sat) * (.15 + .55 * sat)) * (.07 + .5 * (1 - sat)) * .96)
                scores['simulatedExpectedNotInterestedRate6'] = float(np.mean(rates))
                key = name + '/' + phase
                values[key].append(scores)
                coverage[key].update(ordered[:6])
                if phase == 'diversified':
                    clusters[context][name].append(scores['ndcg6'])
                    for group in groups:
                        slices[group][name].append(scores['ndcg6'])
        count += 1
    if not count or oracle:
        raise ValueError('Missing/extra oracle rows')
    metrics = {k: {m: float(np.mean([r[m] for r in v])) for m in v[0]} | {
        'catalogCoverage6': len(coverage[k]) / len(learned.catalog.cards)} for k, v in values.items()}
    differences = [float(np.mean(v['catboost']) - np.mean(v['e5_rules'])) for v in clusters.values()]
    interval = clustered_interval(differences)
    base = metrics['e5_rules/diversified']['ndcg6']
    improvement = metrics['catboost/diversified']['ndcg6'] / base - 1 if base else 0.
    scenarios = semantic_scenarios(learned)
    human = content_review(learned, review) if review else dict(status='pending_human_review', passed=False)
    gates = dict(relativeNDCG6=improvement >= .03, positiveClusterCI=interval[0] > 0,
                 semanticScenarios=all(c['passed'] for c in scenarios), humanReview=human['passed'])
    report = dict(isSynthetic=True, split=split, requests=count, contexts=len(contexts),
        releaseId=learned.release_id, datasetManifestDigest=file_digest(Path(data) / 'manifest.json'),
        metrics=metrics, clusteredDifferenceCI95=interval, relativeNDCG6Improvement=improvement,
        slices={k: {n: dict(ndcg6=float(np.mean(v)), requests=len(v)) for n, v in groups.items()} for k, groups in slices.items()},
        semanticScenarios=scenarios, contentReview=human, gates=gates,
        defaultRanker='catboost' if all(gates.values()) else 'e5',
        limitations=['Oracle relevance and rejection rates are properties of a synthetic world.',
                     'No real-user uplift, causal A/B effect, or unbiased click estimate is established.',
                     'Position is excluded from model features; selection bias is not eliminated.',
                     'AI draft content grades cannot satisfy the human-review gate.'])
    write_json(output, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--bundle', type=Path, default=Path('.local/feed-catboost'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--review', type=Path, default=Path('ml/feed_v2/fixtures/content-review.json'))
    args = parser.parse_args()
    report = benchmark(args.data, args.bundle, args.output, args.review)
    print(json.dumps({k: report[k] for k in ('relativeNDCG6Improvement','clusteredDifferenceCI95','gates','defaultRanker')}, indent=2))


if __name__ == '__main__':
    main()
