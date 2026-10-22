"""Replay saved synthetic evidence offline; never train, generate data or activate."""
import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ml'))
from scoring.bundle import file_hash, load_bundle, predict_probability
from scoring.evaluation import evaluate, financial_eligible
from scoring.features import matrix, statement_from_row

VERSION = 'scoring-v2-351935cfd80c'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def compare(actual, expected, location='result'):
    """Compare all recorded values, allowing only floating-point roundoff."""
    if isinstance(expected, dict):
        require(isinstance(actual, dict) and actual.keys() == expected.keys(), location + ': keys differ')
        for key in expected:
            compare(actual[key], expected[key], location + '.' + key)
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), location + ': length differs')
        for i, value in enumerate(expected):
            compare(actual[i], value, f'{location}[{i}]')
    elif isinstance(expected, float):
        require(isinstance(actual, (float, int)) and np.isclose(actual, expected, rtol=0, atol=1e-12), location + ': number differs')
    else:
        require(actual == expected, location + ': value differs')


def replay(evidence, candidate, baseline, dataset):
    evidence, candidate, baseline, dataset = map(Path, (evidence, candidate, baseline, dataset))
    for line in (evidence / 'SHA256SUMS').read_text().splitlines():
        checksum, name = line.split(maxsplit=1)
        path = (evidence / name).resolve()
        require(evidence.resolve() in path.parents and path.is_file(), 'Unsafe evidence path')
        require(file_hash(path) == checksum, 'Evidence checksum mismatch: ' + name)
    saved = json.loads((evidence / 'independent_result.json').read_text())
    protocol = json.loads((evidence / 'independent_protocol.json').read_text())
    provenance = json.loads((evidence / 'provenance.json').read_text())
    compare(protocol, saved['protocol'], 'protocol')
    require(protocol['beforeEvaluation'] and protocol['noFurtherSelection'], 'Unexpected experiment protocol')
    compare(protocol['bootstrap'], {'replicates': 1000, 'seed': 20261021, 'pairedCompanyResampling': True}, 'bootstrap protocol')
    criteria = {'recallDifferenceLower95Above': 0., 'APDifferenceAtLeast': 0., 'LoglossDifferenceAtMost': .002}
    compare(protocol['promotionCriteria'], criteria, 'promotion criteria')
    require(file_hash(evidence / 'archive/generator_source_reference.py.txt') == protocol['generatorSourceHash'], 'Generator source hash mismatch')
    model, manifest, policy = load_bundle(candidate)
    old, old_manifest, _ = load_bundle(baseline)
    require(manifest['bundleDigest'] == provenance['candidateBundleDigest'], 'Unexpected candidate bundle')
    require(old_manifest['bundleDigest'] == provenance['baselineBundleDigest'], 'Unexpected baseline bundle')
    require(manifest['artifacts']['model.joblib'] == protocol['candidateModelHash'], 'Candidate model hash mismatch')
    require(old_manifest['artifacts']['model.joblib'] == protocol['baselineModelHash'], 'Baseline model hash mismatch')
    compare(saved, json.loads((candidate / 'independent-validation.json').read_text()), 'sealed evidence')
    training_protocol = json.loads((candidate / 'protocol.json').read_text())
    require(file_hash(evidence / 'archive/train.py.txt') == training_protocol['sourceHash'], 'Historical training source mismatch')
    require(file_hash(evidence / 'archive/learning.py.txt') == training_protocol['learningSourceHash'], 'Historical learning source mismatch')
    published = {name: checksum for checksum, name in (line.split(maxsplit=1) for line in (dataset / 'MANIFEST.sha256').read_text().splitlines())}
    for name, checksum in provenance['datasetFiles'].items():
        require(file_hash(dataset / name) == checksum, 'Dataset checksum mismatch: ' + name)
        if name != 'MANIFEST.sha256':
            require(published[name] == checksum, 'Dataset manifest mismatch: ' + name)
    require(manifest['datasetHash'] == provenance['datasetFiles']['simulation_splits/train.parquet'], 'Candidate training data mismatch')
    holdout = evidence / 'independent_holdout.parquet'
    require(file_hash(holdout) == saved['dataHash'], 'Holdout hash mismatch')
    records = pq.read_table(holdout).to_pylist()
    require(len(records) == protocol['rows'], 'Holdout row count mismatch')
    require(all(r['split'] == 'independent' and r['financial_is_synthetic'] and r['label_is_synthetic'] for r in records), 'Expected independent synthetic rows')
    fields = provenance['financialFields']
    ids = {r['company_id'] for r in records}
    vectors = {tuple(r[k] for k in fields) for r in records}
    require(len(ids) == len(records) and len(vectors) == len(records), 'Duplicate holdout ID/financial vector')
    original = pq.read_table(dataset / 'training_simulation.parquet').to_pylist()
    require(not ids.intersection(r['company_id'] for r in original), 'Holdout overlaps original IDs')
    require(not vectors.intersection(tuple(r[k] for k in fields) for r in original), 'Holdout overlaps original financial vectors')
    for split in ('train', 'validation', 'test'):
        rows = pq.read_table(dataset / f'simulation_splits/{split}.parquet').to_pylist()
        require(not ids.intersection(r['company_id'] for r in rows), 'Holdout overlaps split IDs: ' + split)
        require(not vectors.intersection(tuple(r[k] for k in fields) for r in rows), 'Holdout overlaps split finances: ' + split)
    statements = [statement_from_row(r) for r in records]
    x = matrix(statements)
    y = np.array([r['target_12m'] for r in records])
    eligible = np.array([financial_eligible(s) for s in statements])
    p, b = predict_probability(model, x), predict_probability(old, x)
    reports = {n: {'all': evaluate(y, pp), 'eligible': evaluate(y[eligible], pp[eligible])} for n, pp in [('candidate', p), ('baseline', b)]}
    mask = eligible & (p >= policy['T_manual'])
    fixed = {'reviewed': int(mask.sum()), 'coverage': float(mask.sum() / eligible.sum()),
             'eventsFound': int(y[mask].sum()), 'recall': float(y[mask].sum() / y[eligible].sum()), 'threshold': policy['T_manual']}
    selected_ids = np.flatnonzero(eligible)
    rng = np.random.default_rng(protocol['bootstrap']['seed'])
    differences = []
    for _ in range(protocol['bootstrap']['replicates']):
        ii = rng.choice(selected_ids, len(selected_ids), replace=True)
        a, bb = evaluate(y[ii], p[ii]), evaluate(y[ii], b[ii])
        differences.append([a['top5']['recall'] - bb['top5']['recall'], a['averagePrecision'] - bb['averagePrecision'], a['logLoss'] - bb['logLoss']])
    intervals = {k: np.quantile(np.array(differences)[:, i], [.025, .975]).tolist() for i, k in enumerate(['recall5', 'averagePrecision', 'logLoss'])}
    a, bb = reports['candidate']['eligible'], reports['baseline']['eligible']
    point = {'recall5': a['top5']['recall'] - bb['top5']['recall'], 'averagePrecision': a['averagePrecision'] - bb['averagePrecision'], 'logLoss': a['logLoss'] - bb['logLoss']}
    checks = {'primaryRecallLower95Positive': intervals['recall5'][0] > criteria['recallDifferenceLower95Above'],
              'APNotWorse': point['averagePrecision'] >= criteria['APDifferenceAtLeast'], 'ordinaryLoglossGuard': point['logLoss'] <= criteria['LoglossDifferenceAtMost']}
    recomputed = {**saved, 'protocol': protocol, 'dataHash': file_hash(holdout), 'modelVersion': manifest['modelVersion'],
                  'baselineVersion': old_manifest['modelVersion'], 'reports': reports, 'eligiblePairedDifference': point,
                  'paired95': intervals, 'fixedThresholdCandidate': fixed, 'checks': checks, 'passed': all(checks.values()),
                  'uniqueRows': len(ids), 'overlapOriginalIds': 0, 'overlapOriginalFinanceVectors': 0}
    compare(recomputed, saved)
    return {'mode': 'offline replay of existing evidence; not a new independent test', 'verified': True,
            'qualityGatePassed': recomputed['passed'], 'activated': False, 'eligibleRows': int(eligible.sum()),
            'eligibleEvents': int(y[eligible].sum()), 'candidateEventsFound': a['top5']['eventsFound'],
            'baselineEventsFound': bb['top5']['eventsFound'], 'paired95': intervals,
            'dataHash': recomputed['dataHash'], 'candidateBundleDigest': manifest['bundleDigest']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, default=ROOT / 'ml/experiments' / VERSION)
    parser.add_argument('--candidate', type=Path, default=ROOT / 'ml/artifacts' / VERSION)
    parser.add_argument('--baseline', type=Path, default=ROOT / 'ml/artifacts/baseline')
    parser.add_argument('--dataset', type=Path, default=ROOT / 'datasets/ru-sme-dataset-10000')
    args = parser.parse_args()
    # Stdout only: replay cannot overwrite saved evidence or alter a bundle/pointer.
    print(json.dumps(replay(args.evidence, args.candidate, args.baseline, args.dataset), indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
