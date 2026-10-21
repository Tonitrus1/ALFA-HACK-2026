import argparse
import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path

import joblib
import numpy as np
import optuna
import pyarrow.parquet as pq
from catboost import CatBoostClassifier
from optuna.trial import TrialState
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    log_loss,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold

from .features import (
    FEATURES,
    FIELDS,
    canonical,
    code_digest,
    digest,
    matrix,
    statement_from_row,
)


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def load(path):
    columns = list(FIELDS) + ['company_id', 'target_12m', 'split']
    rows = pq.read_table(path, columns=columns).to_pylist()
    statements = [statement_from_row(row) for row in rows]
    target = np.array([row['target_12m'] for row in rows], dtype=np.int8)
    return rows, statements, target


def create_model(params, threads):
    return CatBoostClassifier(
        **params,
        loss_function='Logloss',
        eval_metric='Logloss',
        bootstrap_type='Bayesian',
        nan_mode='Min',
        random_seed=42,
        thread_count=threads,
        allow_writing_files=False,
        verbose=False,
    )


def optimize(x, y, trials, folds, threads, storage):
    splitter = StratifiedKFold(n_splits=folds, shuffle=True, random_state=42)
    splits = list(splitter.split(x, y))

    def objective(trial):
        params = {
            'iterations': trial.suggest_int('iterations', 300, 1200, step=100),
            'depth': trial.suggest_int('depth', 3, 8),
            'learning_rate': trial.suggest_float('learning_rate', 0.015, 0.2, log=True),
            'l2_leaf_reg': trial.suggest_float('l2_leaf_reg', 0.1, 40.0, log=True),
            'random_strength': trial.suggest_float('random_strength', 0.0, 3.0),
            'bagging_temperature': trial.suggest_float('bagging_temperature', 0.0, 2.0),
            'rsm': trial.suggest_float('rsm', 0.65, 1.0),
            'border_count': trial.suggest_categorical('border_count', [32, 64, 128]),
            'auto_class_weights': trial.suggest_categorical(
                'auto_class_weights', ['None', 'Balanced', 'SqrtBalanced']
            ),
        }
        scores = []
        tree_counts = []
        for fold, (train_index, valid_index) in enumerate(splits):
            model = create_model(params, threads)
            model.fit(
                x[train_index],
                y[train_index],
                eval_set=(x[valid_index], y[valid_index]),
                early_stopping_rounds=75,
            )
            prediction = model.predict_proba(x[valid_index])[:, 1]
            scores.append(float(average_precision_score(y[valid_index], prediction)))
            tree_counts.append(int(model.tree_count_))
            trial.set_user_attr('foldAveragePrecision', scores)
            trial.set_user_attr('foldTreeCounts', tree_counts)
            trial.report(float(np.mean(scores)), fold)
            if trial.should_prune():
                raise optuna.TrialPruned()
        trial.set_user_attr('fitIterations', max(1, int(np.median(tree_counts))))
        return float(np.mean(scores))

    study = optuna.create_study(
        study_name='catboost-risk-' + digest({'trials': trials, 'folds': folds})[:12],
        storage=storage,
        direction='maximize',
        sampler=optuna.samplers.TPESampler(seed=42, n_startup_trials=8),
        pruner=optuna.pruners.MedianPruner(n_startup_trials=8, n_warmup_steps=1),
    )
    study.optimize(objective, n_trials=trials, n_jobs=1)
    return study


def select_model(study, x, y, validation_x, validation_y, shortlist, threads):
    completed = sorted(
        (trial for trial in study.trials if trial.state == TrialState.COMPLETE),
        key=lambda trial: (-trial.value, trial.number),
    )[:shortlist]
    candidates = []
    models = []
    for trial in completed:
        params = {**trial.params, 'iterations': trial.user_attrs['fitIterations']}
        model = create_model(params, threads)
        model.fit(x, y)
        prediction = model.predict_proba(validation_x)[:, 1]
        score = float(average_precision_score(validation_y, prediction))
        candidates.append({
            'trialNumber': trial.number,
            'cvAveragePrecision': trial.value,
            'validationAveragePrecision': score,
            'params': params,
        })
        models.append(model)
    index = max(
        range(len(candidates)),
        key=lambda i: (
            candidates[i]['validationAveragePrecision'],
            candidates[i]['cvAveragePrecision'],
            -candidates[i]['trialNumber'],
        ),
    )
    return models[index], candidates[index], candidates


def evaluate(y, prediction, threshold):
    return {
        'rows': len(y),
        'events': int(y.sum()),
        'prevalence': float(y.mean()),
        'rocAuc': float(roc_auc_score(y, prediction)),
        'averagePrecision': float(average_precision_score(y, prediction)),
        'brier': float(brier_score_loss(y, prediction)),
        'logLoss': float(log_loss(y, prediction)),
        'confusionMatrixAtManualThreshold': confusion_matrix(
            y, prediction >= threshold, labels=[0, 1]
        ).tolist(),
        'scoreQuantiles': dict(zip(
            ['min', 'p10', 'p50', 'p80', 'p90', 'p99', 'max'],
            np.quantile(prediction, [0, 0.1, 0.5, 0.8, 0.9, 0.99, 1]).tolist(),
        )),
    }


def create_policy(statements, target, prediction):
    eligible = np.array([
        statement['values']['equityMinor'] >= 0
        and statement['values']['totalLiabilitiesMinor'] * 10
        < statement['values']['totalAssetsMinor'] * 9
        and statement['values']['revenueMinor'] >= 40000000
        for statement in statements
    ])
    threshold = float(np.quantile(prediction[eligible], 0.8, method='higher'))
    selected = eligible & (prediction >= threshold)
    return {
        'version': 'synthetic-demo-policy-3',
        'T_manual': threshold,
        'selectionSplit': 'validation',
        'manualQuantile': 0.8,
        'eligibleRows': int(eligible.sum()),
        'manualRows': int(selected.sum()),
        'manualEvents': int(target[selected].sum()),
        'eligibleEvents': int(target[eligible].sum()),
        'actualCoverage': float(selected.sum() / eligible.sum()),
        'tiedAtThreshold': int((prediction[eligible] == threshold).sum()),
        'comparison': '>=',
        'synthetic': True,
    }


def create_fixtures(rows, statements, prediction, threshold, bundle_digest, policy_version):
    valid = [
        i for i, statement in enumerate(statements)
        if statement['values']['equityMinor'] >= 0
        and statement['values']['totalLiabilitiesMinor'] * 10
        < statement['values']['totalAssetsMinor'] * 9
        and statement['values']['revenueMinor'] // 4 > 50000000
    ]
    low = min(valid, key=lambda i: prediction[i])
    high = max(valid, key=lambda i: prediction[i])
    assert prediction[low] < threshold * 0.7
    assert prediction[high] > threshold * 1.3
    base = statements[low]
    adverse = statements[high]
    refused = json.loads(canonical(base))
    values = refused['values']
    values['totalLiabilitiesMinor'] = values['totalAssetsMinor'] * 95 // 100
    values['equityMinor'] = values['totalAssetsMinor'] - values['totalLiabilitiesMinor']
    values['currentLiabilitiesMinor'] = min(
        values['currentLiabilitiesMinor'], values['totalLiabilitiesMinor']
    )
    companies = []
    configurations = [
        ('S01', 'Одобрение', base, 20000000),
        ('S02', 'Отказ по правилу', refused, 20000000),
        ('S03', 'Уточнение выручки', base, 20000000),
        ('S04', 'Другие условия', base, 500000001),
        ('S05', 'Ручная проверка', adverse, 20000000),
        ('S06', 'Сбой ML', base, 20000000),
    ]
    for number, name, statement, amount in configurations:
        initial = json.loads(canonical(statement))
        if number == 'S03':
            initial['values']['revenueMinor'] *= 2
        companies.append({
            'companyId': 'DEMO:' + number,
            'name': f'Демо {number} · {name}',
            'businessAgeMonths': 36,
            'synthetic': True,
            'sourceRecordId': 'SIM:SOURCE:' + number,
            'sourceVersion': 1,
            'availableAt': '2026-04-01T00:00:00Z',
            'reference': statement,
            'initial': initial,
            'amountMinor': amount,
            'termMonths': 12,
        })
    return {
        'synthetic': True,
        'bundleDigest': bundle_digest,
        'policyVersion': policy_version,
        'selectionSource': 'train',
        'sourceTrainIds': {'low': rows[low]['company_id'], 'high': rows[high]['company_id']},
        'companies': companies,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('ml/artifacts/baseline'))
    parser.add_argument('--trials', type=int, default=30)
    parser.add_argument('--folds', type=int, default=3)
    parser.add_argument('--shortlist', type=int, default=5)
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--storage')
    args = parser.parse_args()
    if args.trials < 1 or args.folds < 2 or args.shortlist < 1 or args.threads < 1:
        parser.error('trials/shortlist/threads >= 1; folds >= 2')
    root = args.dataset.resolve()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    published = {
        line.split(maxsplit=1)[1].lstrip('*'): line.split()[0]
        for line in (root / 'MANIFEST.sha256').read_text().splitlines()
        if line.strip()
    }
    paths = {
        split: root / 'simulation_splits' / f'{split}.parquet'
        for split in ['train', 'validation', 'test']
    }
    hashes = {split: file_hash(path) for split, path in paths.items()}
    for split, path in paths.items():
        assert hashes[split] == published[str(path.relative_to(root))]
    train_rows, train_statements, train_y = load(paths['train'])
    validation_rows, validation_statements, validation_y = load(paths['validation'])
    assert (len(train_rows), int(train_y.sum())) == (7016, 352)
    assert (len(validation_rows), int(validation_y.sum())) == (1494, 80)
    assert not {row['company_id'] for row in train_rows} & {
        row['company_id'] for row in validation_rows
    }
    x = matrix(train_statements)
    validation_x = matrix(validation_statements)
    study = optimize(x, train_y, args.trials, args.folds, args.threads, args.storage)
    model, selected, candidates = select_model(
        study, x, train_y, validation_x, validation_y, args.shortlist, args.threads
    )
    policy = create_policy(
        validation_statements, validation_y, model.predict_proba(validation_x)[:, 1]
    )
    threshold = policy['T_manual']
    study_report = {
        'studyName': study.study_name,
        'direction': study.direction.name,
        'sampler': {'name': 'TPESampler', 'seed': 42},
        'pruner': {'name': 'MedianPruner', 'startupTrials': 8, 'warmupSteps': 1},
        'objective': 'train_stratified_cv_average_precision',
        'folds': args.folds,
        'trialsRequested': args.trials,
        'bestCvTrial': study.best_trial.number,
        'selectedTrial': selected['trialNumber'],
        'trials': [{
            'number': trial.number,
            'state': trial.state.name,
            'value': trial.value,
            'params': trial.params,
            'userAttrs': trial.user_attrs,
        } for trial in study.trials],
    }
    joblib.dump(model, out / 'model.joblib')
    write(out / 'policy.json', policy)
    write(out / 'optuna-study.json', study_report)
    lock = {
        'modelHash': file_hash(out / 'model.joblib'),
        'policyHash': file_hash(out / 'policy.json'),
        'studyHash': file_hash(out / 'optuna-study.json'),
        'selectedTrial': selected['trialNumber'],
        'params': selected['params'],
        'featureCodeDigest': code_digest(),
    }
    write(out / 'selection-lock.json', lock)
    test_rows, test_statements, test_y = load(paths['test'])
    assert (len(test_rows), int(test_y.sum())) == (1490, 80)
    ids = [
        {row['company_id'] for row in rows}
        for rows in [train_rows, validation_rows, test_rows]
    ]
    assert not ids[0] & ids[2] and not ids[1] & ids[2]
    for split, rows in zip(paths, [train_rows, validation_rows, test_rows]):
        assert all(row['split'] == split for row in rows)
    report = {
        'modelType': 'CatBoostClassifier',
        'optimization': {
            'library': 'optuna',
            'trials': len(study.trials),
            'folds': args.folds,
            'objective': study_report['objective'],
            'selectedTrial': selected['trialNumber'],
            'params': selected['params'],
        },
        'selectionLock': lock,
        'candidates': candidates,
        'splits': {
            split: evaluate(target, model.predict_proba(matrix(statements))[:, 1], threshold)
            for split, statements, target in [
                ('train', train_statements, train_y),
                ('validation', validation_statements, validation_y),
                ('test', test_statements, test_y),
            ]
        },
        'datasetHashes': hashes,
    }
    write(out / 'evaluation.json', report)
    schema = Path('docs/architecture/contracts/feature-snapshot.schema.json')
    write(out / 'feature-schema.json', json.loads(schema.read_text()))
    card = {
        'modelType': 'CatBoostClassifier',
        'modelVersion': 'catboost-optuna-v1',
        'params': selected['params'],
        'features': FEATURES,
        'missingValueMode': 'Min',
        'optimization': report['optimization'],
        'calibration': None,
        'dataOrigin': 'SYNTHETIC_FINANCE_V1',
        'scoreKind': 'BANKRUPTCY_PROXY',
        'purpose': 'DEMO_RESEARCH',
    }
    (out / 'model-card.md').write_text('```json\n' + json.dumps(card, indent=2) + '\n```\n')
    artifact_names = [
        'model.joblib', 'policy.json', 'selection-lock.json', 'evaluation.json',
        'optuna-study.json', 'feature-schema.json', 'model-card.md',
    ]
    manifest = {
        'modelVersion': 'catboost-optuna-v1',
        'modelType': 'CatBoostClassifier',
        'featureSchemaVersion': 2,
        'featureCodeDigest': code_digest(),
        'featureSchemaDigest': file_hash(out / 'feature-schema.json'),
        'features': FEATURES,
        'rawWhitelist': list(FIELDS),
        'scoreKind': 'BANKRUPTCY_PROXY',
        'validationStatus': 'DEMONSTRATION',
        'purpose': 'DEMO_RESEARCH',
        'financialsSynthetic': True,
        'labelsSynthetic': True,
        'datasetHashes': hashes,
        'datasetHash': file_hash(root / 'training_simulation.parquet'),
        'splitMembershipDigest': digest({
            split: sorted(ids[i]) for i, split in enumerate(paths)
        }),
        'python': platform.python_version(),
        'libraries': {
            package: importlib.metadata.version(package)
            for package in ['numpy', 'scikit-learn', 'scipy', 'joblib', 'pyarrow', 'catboost', 'optuna']
        },
        'artifacts': {name: file_hash(out / name) for name in artifact_names},
    }
    manifest['bundleDigest'] = digest(manifest)
    write(out / 'manifest.json', manifest)
    checksums = [
        f'{file_hash(out / name)}  {name}'
        for name in artifact_names + ['manifest.json']
    ]
    (out / 'SHA256SUMS').write_text('\n'.join(checksums) + '\n')
    fixtures = create_fixtures(
        train_rows, train_statements, model.predict_proba(x)[:, 1],
        threshold, manifest['bundleDigest'], policy['version'],
    )
    generated = out.parent.parent / 'generated'
    generated.mkdir(exist_ok=True)
    write(generated / 'companies.json', fixtures['companies'])
    Path('ml/fixtures').mkdir(exist_ok=True)
    write(Path('ml/fixtures/scenarios.json'), fixtures)
    reports = Path('reports')
    reports.mkdir(exist_ok=True)
    for name in artifact_names + ['manifest.json']:
        if name != 'model.joblib':
            (reports / name).write_bytes((out / name).read_bytes())
    print(json.dumps({
        'modelVersion': manifest['modelVersion'],
        'bundleDigest': manifest['bundleDigest'],
        'selectedTrial': selected['trialNumber'],
        'params': selected['params'],
        'threshold': threshold,
        'test': report['splits']['test'],
    }, indent=2))


if __name__ == '__main__':
    main()
