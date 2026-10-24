"""Train a separate synthetic manipulation proxy; never retrain credit risk."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path

import joblib
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from catboost import CatBoostClassifier
from sklearn.metrics import average_precision_score, confusion_matrix, roc_auc_score

from . import fraud_data, fraud_features
from .demo_policy import precheck
from .features import canonical, digest, matrix as risk_matrix

ROOT = Path(__file__).resolve().parents[2]


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def eligible(pair):
    return precheck(pair['statement'], pair['reference'], 20000000, 12) is None


def select_threshold(y, scores, maximum_fpr=.05):
    """Maximum validation recall under the FPR cap; conservative tie-break."""
    if not len(y) or not (y == 0).any() or not (y == 1).any():
        raise ValueError('Both classes required after prechecks')
    candidates = np.unique(scores)
    ordered = np.argsort(scores, kind='stable')
    sorted_scores, sorted_y = scores[ordered], y[ordered]
    starts = np.searchsorted(sorted_scores, candidates, side='left')
    positives = np.r_[0, np.cumsum(sorted_y)]
    negatives = np.r_[0, np.cumsum(1 - sorted_y)]
    tp = positives[-1] - positives[starts]
    fp = negatives[-1] - negatives[starts]
    # One-sided 95% Wilson upper bound, rather than fitting to the very edge of
    # the empirical budget. Threshold selection still sees validation only.
    n = negatives[-1]
    rate = fp / n
    z = 1.6448536269514722
    upper = (rate + z*z/(2*n) + z*np.sqrt(rate*(1-rate)/n + z*z/(4*n*n))) / (1 + z*z/n)
    valid = np.flatnonzero(upper <= maximum_fpr)
    if not len(valid):
        raise ValueError('No useful threshold under false-positive budget')
    index = max(valid, key=lambda i: (int(tp[i]), -int(fp[i]), float(candidates[i])))
    return float(candidates[index])


def measure(pairs, scores, threshold, risk_model, risk_threshold):
    y = np.array([p['target'] for p in pairs])
    mask = np.array([eligible(p) for p in pairs])
    selected = scores >= threshold
    subset = y[mask]
    predictions = selected[mask]
    tn, fp, fn, tp = confusion_matrix(subset, predictions, labels=[0, 1]).ravel()
    risk_scores = risk_model.predict_proba(risk_matrix([p['statement'] for p in pairs]))[:, 1]
    prior_review = mask & (risk_scores >= risk_threshold)
    new_review = prior_review | (mask & selected)
    newly_caught = mask & selected & ~prior_review & (y == 1)
    return {
        'rows': len(pairs), 'eligibleRows': int(mask.sum()),
        'eligibleBenign': int((subset == 0).sum()), 'eligibleManipulations': int(subset.sum()),
        'averagePrecision': float(average_precision_score(subset, scores[mask])) if len(set(subset)) > 1 else None,
        'rocAuc': float(roc_auc_score(subset, scores[mask])) if len(set(subset)) > 1 else None,
        'confusionMatrix': [[int(tn), int(fp)], [int(fn), int(tp)]],
        'precision': float(tp / max(tp + fp, 1)), 'recall': float(tp / max(tp + fn, 1)),
        'falsePositiveRate': float(fp / max(fp + tn, 1)),
        'rulesOnlyDetectionAfterPrecheck': 0,
        'additionalManipulationsDetected': int(tp),
        'additionalBeyondCreditReview': int(newly_caught.sum()),
        'manualRateBefore': float(prior_review.sum() / max(mask.sum(), 1)),
        'manualRateAfter': float(new_review.sum() / max(mask.sum(), 1)),
        'manualRateIncrease': float((new_review.sum() - prior_review.sum()) / max(mask.sum(), 1)),
    }


def train(dataset, output):
    if output.exists():
        raise FileExistsError('Use a new output directory; do not overwrite a locked experiment')
    output.mkdir(parents=True)
    risk_bundle = ROOT / 'ml/artifacts/baseline'
    risk_model = joblib.load(risk_bundle / 'model.joblib')
    risk_manifest = json.loads((risk_bundle / 'manifest.json').read_text())
    risk_threshold = json.loads((risk_bundle / 'policy.json').read_text())['T_manual']
    train_rows, training = fraud_data.load_split(dataset, 'train')
    valid_rows, validation = fraud_data.load_split(dataset, 'validation')
    if {r['company_id'] for r in train_rows} & {r['company_id'] for r in valid_rows}:
        raise ValueError('Company leakage')
    model = CatBoostClassifier(iterations=350, depth=4, learning_rate=.05,
                               loss_function='Logloss', random_seed=42, thread_count=2,
                               allow_writing_files=False, verbose=False)
    model.fit(fraud_features.matrix(training), [p['target'] for p in training])
    scores = model.predict_proba(fraud_features.matrix(validation))[:, 1]
    mask = np.array([eligible(p) for p in validation])
    threshold = select_threshold(np.array([p['target'] for p in validation])[mask], scores[mask])
    validation_report = measure(validation, scores, threshold, risk_model, risk_threshold)
    joblib.dump(model, output / 'model.joblib')
    schema = {'version': 1, 'features': fraud_features.FEATURES,
              'normalization': '(declared-reference)/max(abs(reference),100 minor units)',
              'forbidden': ['companyId', 'target', 'family', 'target_12m', 'split', 'true_probability_synthetic']}
    write(output / 'feature-schema.json', schema)
    policy = {'version': 'synthetic-dual-policy-4', 'T_fraud': threshold, 'comparison': '>=',
              'maximumValidationFpr': .05, 'selectionSplit': 'validation',
              'thresholdMethod': 'max recall with one-sided 95% Wilson FPR upper bound <=5%',
              'riskBundleDigest': risk_manifest['bundleDigest'], 'T_manual': risk_threshold}
    write(output / 'policy.json', policy)
    # This file is committed to disk before opening any final test rows.
    lock = {'modelHash': file_hash(output / 'model.joblib'), 'policyHash': file_hash(output / 'policy.json'),
            'generatorVersion': fraud_data.VERSION, 'generatorDigest': fraud_data.code_digest(),
            'seed': fraud_data.SEED, 'featureCodeDigest': fraud_features.code_digest(),
            'sourceHashes': {s: file_hash(dataset / 'simulation_splits' / f'{s}.parquet')
                             for s in ('train', 'validation', 'test')},
            'trainCompanies': [r['company_id'] for r in train_rows],
            'validationCompanies': [r['company_id'] for r in valid_rows],
            'heldOutFamily': fraud_data.HELD_OUT_FAMILY, 'testOpened': False}
    write(output / 'selection-lock.json', lock)
    test_rows, testing = fraud_data.load_split(dataset, 'test')
    test_ids = {r['company_id'] for r in test_rows}
    if test_ids & set(lock['trainCompanies'] + lock['validationCompanies']):
        raise ValueError('Test company leakage')
    test_scores = model.predict_proba(fraud_features.matrix(testing))[:, 1]
    test_report = measure(testing, test_scores, threshold, risk_model, risk_threshold)
    unseen = fraud_data.held_out_pairs(test_rows)
    unseen_report = measure(unseen, model.predict_proba(fraud_features.matrix(unseen))[:, 1],
                            threshold, risk_model, risk_threshold)
    gate = (validation_report['falsePositiveRate'] <= .05 and test_report['falsePositiveRate'] <= .05
            and validation_report['additionalBeyondCreditReview'] > 0
            and test_report['additionalBeyondCreditReview'] > 0)
    report = {'interpretation': 'Synthetic generator benchmark only; not real fraud performance',
              'validation': validation_report, 'test': test_report, 'heldOutAttackFamily': unseen_report,
              'testCompanyDigest': digest(sorted(test_ids)), 'routingEnabled': bool(gate),
              'gate': 'validation/test FPR<=5% and additional detections beyond credit review',
              'heldOutGeneralizationSupported': unseen_report['recall'] > 0,
              'classMix': '4 benign and 3 manipulated statements per base company; not a real fraud prevalence',
              'manualRateDenominator': 'statements passing all preliminary policy checks'}
    write(output / 'evaluation.json', report)
    # Persist the derived paired data outside the deployable model bundle.
    data_output = ROOT / 'ml/experiments' / output.name
    data_output.mkdir(parents=True, exist_ok=False)
    for split, pairs in [('train', training), ('validation', validation), ('test', testing), ('held-out', unseen)]:
        records = [{'companyId': p['companyId'], 'target': p['target'], 'family': p['family'],
                    'statementJson': canonical(p['statement']), 'referenceJson': canonical(p['reference'])} for p in pairs]
        pq.write_table(pa.Table.from_pylist(records), data_output / f'{split}.parquet')
    write(data_output / 'manifest.json', {'seed': fraud_data.SEED, 'version': fraud_data.VERSION,
          'generatorDigest': fraud_data.code_digest(),
          'files': {p.name: file_hash(p) for p in data_output.glob('*.parquet')}})
    # Prepared examples come exclusively from train, without scenario IDs in X.
    fixtures = []
    for credit_high in (False, True):
        candidates = [p for p in training if p['target'] == 1 and eligible(p)]
        f = model.predict_proba(fraud_features.matrix(candidates))[:, 1]
        r = risk_model.predict_proba(risk_matrix([p['statement'] for p in candidates]))[:, 1]
        choices = [i for i in range(len(candidates)) if f[i] >= threshold and (r[i] >= risk_threshold) == credit_high]
        if not choices:
            raise ValueError('No genuine train inference for required S05 variant')
        pair = candidates[max(choices, key=lambda i: f[i])]
        fixtures.append({'variant': 'both' if credit_high else 'fraud',
                         'statement': pair['statement'], 'reference': pair['reference'],
                         'sourceCompanyId': pair['companyId']})
    write(output / 'scenario-fixtures.json', {'sourceSplit': 'train', 'cases': fixtures})
    (output / 'model-card.md').write_text(
        '# Synthetic financial manipulation proxy\n\n'
        'Independent CatBoost over 16 signed/absolute financial discrepancies. '
        'Credit model and threshold are unchanged. Synthetic pairs preserve company splits; '
        'benign corrections overlap with attacks. Labels describe generator intent, which is '
        'not identifiable from financial differences alone. No claim of real fraud detection, '
        'PD calibration, time stability or support for individual entrepreneurs.\n\n'
        'Reference must be pinned and supplied by a trusted backend. The model cannot detect '
        'joint compromise of declared and reference statements. No real registry IDs are used.\n')
    names = ['model.joblib', 'policy.json', 'selection-lock.json', 'feature-schema.json',
             'evaluation.json', 'model-card.md', 'scenario-fixtures.json']
    manifest = {'modelVersion': 'catboost-manipulation-v1', 'scoreKind': fraud_features.SCORE_KIND,
                'validationStatus': 'DEMONSTRATION', 'purpose': 'DEMO_RESEARCH',
                'featureSchemaVersion': 1, 'featureCodeDigest': fraud_features.code_digest(),
                'generatorDigest': fraud_data.code_digest(), 'riskBundleDigest': risk_manifest['bundleDigest'],
                'routingEnabled': bool(gate), 'features': fraud_features.FEATURES,
                'libraries': {p: importlib.metadata.version(p) for p in ['catboost', 'numpy', 'joblib']},
                'artifacts': {name: file_hash(output / name) for name in names}}
    manifest['bundleDigest'] = digest(manifest)
    write(output / 'manifest.json', manifest)
    (output / 'SHA256SUMS').write_text(''.join(f'{file_hash(p)}  {p.name}\n' for p in sorted(output.iterdir()) if p.is_file() and p.name != 'SHA256SUMS'))
    print(json.dumps({'bundle': str(output), 'routingEnabled': bool(gate), 'evaluation': report}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', type=Path, default=ROOT / 'datasets/ru-sme-dataset-10000')
    parser.add_argument('--output', type=Path, default=ROOT / 'ml/artifacts/fraud-demo-v1')
    args = parser.parse_args()
    train(args.dataset, args.output)
