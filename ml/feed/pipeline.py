"""Reproduce the complete ML-only hackathon delivery without overwriting a run."""
import argparse
import json
from pathlib import Path

from .benchmark import benchmark
from .cli import evaluate
from .dataset import write_json
from .demo import demo
from .prepare import prepare
from .simulate import generate
from .smoke import smoke
from .train_ranker import train
from .validate_data import validate


def pipeline(work, reports, model_source=None, download=False, users=5000, with_http=True):
    if work.exists() or reports.exists():
        raise FileExistsError('Use new work and reports directories for each immutable run')
    work.mkdir(parents=True)
    reports.mkdir(parents=True)
    config = json.loads(Path(__file__).with_name('simulation.json').read_text())
    config['users'] = users
    prepare(work / 'e5', download, model_source)
    evaluate(work / 'e5', reports / 'e5-scenarios.json')
    generate(work / 'data', config)
    write_json(reports / 'data-validation.json', validate(work / 'data'))
    training = train(work / 'data', work / 'e5', work / 'catboost')
    write_json(reports / 'training.json', training)
    report = benchmark(work / 'data', work / 'catboost', reports / 'benchmark.json',
                       Path(__file__).with_name('fixtures') / 'content-review.json')
    for name, delta in [('position', {'positionDecay': .45, 'seed': 20261023}),
                        ('intent', {'intentStrength': .2, 'seed': 20261024})]:
        stress = config | {'users': min(users, 500)} | delta
        generate(work / ('data-' + name), stress)
        write_json(reports / ('validation-' + name + '.json'), validate(work / ('data-' + name)))
        benchmark(work / ('data-' + name), work / 'catboost', reports / ('benchmark-' + name + '.json'),
                  Path(__file__).with_name('fixtures') / 'content-review.json')
    demo(work / 'catboost', reports / 'demo.json')
    if with_http:
        performance = smoke(work / 'catboost', reports / 'http-load.json')
        if not all(performance['gates'].values()):
            raise RuntimeError('Performance gates failed; inspect http-load.json')
    summary = dict(defaultRanker=report['defaultRanker'], gates=report['gates'],
                   isSynthetic=True, learnedBundle=str(work / 'catboost'), e5Bundle=str(work / 'e5'),
                   humanReviewPending=not report['gates']['humanReview'])
    write_json(reports / 'summary.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--reports', type=Path, required=True)
    parser.add_argument('--model-source', type=Path)
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--users', type=int, default=5000)
    parser.add_argument('--skip-http', action='store_true')
    args = parser.parse_args()
    print(json.dumps(pipeline(args.work, args.reports, args.model_source, args.download,
                              args.users, not args.skip_http), indent=2))


if __name__ == '__main__':
    main()
