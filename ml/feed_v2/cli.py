"""CLI for integrators: rank one JSON request or evaluate the prepared E5 bundle."""
import argparse
import json
import platform
import time
from pathlib import Path

import numpy as np

from .catalog import Catalog
from .integration import feed_cards, make_request
from .ranker import ModelRanker, RulesRanker
from .schemas import RankingRequest


def evaluate(bundle: Path, output: Path):
    catalog = Catalog()
    model = ModelRanker(catalog, bundle)
    fixtures = json.loads(Path(__file__).with_name('fixtures').joinpath('scenarios.json').read_text())
    cases = []
    durations = []
    for case in fixtures['cases']:
        request = make_request(catalog, request_id=case['id'], exposure_id='ex-' + case['id'],
                               candidate_ids=sorted(catalog.cards), profile=case['profile'])
        ranked = model.rank(request)
        top3 = {catalog.cards[i].topic.value for i in ranked.rankedIds[:3]}
        # Diagnostic paraphrases do not enter the public/internal profile API.
        vector = model.encoder.encode([case['paraphrase']])[0]
        scores = {i: float(model.vectors[i] @ vector) for i in request.candidateIds}
        paraphrased = model.result(request, scores, 'MODEL', model.release_id)
        paraphrase_topics = {catalog.cards[i].topic.value for i in paraphrased.rankedIds[:3]}
        cases.append(dict(id=case['id'], expectedTop3Topics=case['expectedTop3Topics'],
                          actualTop3Topics=sorted(top3), top6=feed_cards(catalog, ranked),
                          expectedTopicsPresent=set(case['expectedTop3Topics']) <= top3,
                          paraphraseTop3=paraphrased.rankedIds[:3],
                          paraphraseRelevant=bool(set(case['expectedTop3Topics']) & paraphrase_topics),
                          paraphraseAllExpectedTopicsPresent=set(case['expectedTop3Topics']) <= paraphrase_topics))
        for _ in range(6):
            start = time.perf_counter()
            model.rank(request)
            durations.append((time.perf_counter() - start) * 1000)
    report = dict(releaseId=model.release_id, bundleDigest=model.bundle_digest,
                  catalogDigest=catalog.digest, runtime=platform.platform(),
                  processor=platform.machine(), cpuThreads=4, candidates=len(catalog.cards),
                  timing={'samples': len(durations), 'warm': True, 'unit': 'ms',
                          'p50': float(np.percentile(durations, 50)),
                          'p95': float(np.percentile(durations, 95)), 'max': max(durations)},
                  cases=cases,
                  limitations=['MVP scenarios are hand-reviewed checks, not an estimate of user benefit.',
                               'Free paraphrases can change the order and drop a secondary theme from top 3.',
                               'Only typed profile fields are accepted by the FEED API.',
                               'No advantage over other algorithms or real-world usefulness is established.'])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    if not all(c['expectedTopicsPresent'] and c['paraphraseRelevant'] for c in cases):
        raise SystemExit('Relevance checks failed; inspect ' + str(output))
    if report['timing']['p95'] > 2000:
        raise SystemExit('Warm p95 exceeds the 2 second target')
    print(json.dumps({'report': str(output), 'casesPassed': len(cases), 'timing': report['timing']}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, default=Path('.local/feed-bundle'))
    sub = parser.add_subparsers(dest='command', required=True)
    rank = sub.add_parser('rank')
    rank.add_argument('request', type=Path)
    rank.add_argument('--rules', action='store_true')
    evaluation = sub.add_parser('evaluate')
    evaluation.add_argument('--output', type=Path, default=Path('reports/feed-evaluation.json'))
    args = parser.parse_args()
    if args.command == 'evaluate':
        evaluate(args.bundle, args.output)
    else:
        catalog = Catalog()
        engine = RulesRanker(catalog) if args.rules else ModelRanker(catalog, args.bundle)
        request = RankingRequest.model_validate_json(args.request.read_text())
        print(engine.rank(request).model_dump_json(indent=2))


if __name__ == '__main__':
    main()
