"""Bounded nested development on train only; preprocessing lives in the estimator."""
import numpy as np
from catboost import CatBoostClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .bundle import predict_probability
from .evaluation import evaluate, operating_key


CONFIGS = {
    'logistic': [{'family': 'logistic', 'C': c, 'balanced': False} for c in (.01, .1, 1., 10.)],
    'balanced': [{'family': 'logistic', 'C': .1, 'balanced': True}],
    'catboost': [{'family': 'catboost', 'iterations': 400, 'depth': d, 'l2_leaf_reg': 10.} for d in (3, 4)],
}


def estimator(config, threads):
    if config['family'] == 'logistic':
        return Pipeline([('impute', SimpleImputer(strategy='median', keep_empty_features=True)),
                         ('scale', StandardScaler()),
                         ('classifier', LogisticRegression(C=config['C'], class_weight='balanced' if config['balanced'] else None,
                                                           max_iter=3000, random_state=42))])
    return CatBoostClassifier(iterations=config['iterations'], depth=config['depth'], l2_leaf_reg=config['l2_leaf_reg'],
                              learning_rate=.03, loss_function='Logloss', eval_metric='Logloss', auto_class_weights='None',
                              random_seed=42, thread_count=threads, allow_writing_files=False, verbose=False)


def select(configs, x, y, eligible, folds, seed, threads):
    splits = list(StratifiedKFold(folds, shuffle=True, random_state=seed).split(x, y))
    candidates = []
    for config in configs:
        keys = []
        for tr, va in splits:
            model = estimator(config, threads)
            model.fit(x[tr], y[tr])
            keys.append(operating_key(y[va], predict_probability(model, x[va]), eligible[va]))
        candidates.append({'config': config, 'innerOperatingKeys': keys, 'meanKey': np.mean(keys, axis=0).tolist()})
    best = max(range(len(candidates)), key=lambda i: tuple(candidates[i]['meanKey']))
    return candidates[best]['config'], candidates


def develop(x, y, eligible, ids, folds=5, repeats=3, seed=20261021, threads=2, progress=None):
    predictions = {n: np.full((repeats, len(y)), np.nan) for n in ['constant', *CONFIGS]}
    records, membership = [], []
    for repeat in range(repeats):
        for fold, (tr, va) in enumerate(StratifiedKFold(folds, shuffle=True, random_state=seed+repeat).split(x, y)):
            membership.extend({'companyId': ids[i], 'repeat': repeat, 'fold': fold} for i in va)
            for name in predictions:
                details = []
                if name == 'constant':
                    p = np.full(len(va), y[tr].mean())
                else:
                    config, details = select(CONFIGS[name], x[tr], y[tr], eligible[tr], 3, 42000+repeat*folds+fold, threads)
                    model = estimator(config, threads)
                    model.fit(x[tr], y[tr])
                    p = predict_probability(model, x[va])
                predictions[name][repeat, va] = p
                records.append({'family': name, 'repeat': repeat, 'fold': fold,
                                'all': evaluate(y[va], p), 'eligible': evaluate(y[va][eligible[va]], p[eligible[va]]),
                                'innerCandidates': details})
            if progress:
                progress(repeat, fold)
    summaries = {n: {'all': [evaluate(y, p) for p in pp], 'eligible': [evaluate(y[eligible], p[eligible]) for p in pp]}
                 for n, pp in predictions.items()}
    # Balanced is diagnostic only: selection requires ordinary calibrated-population losses.
    winner = max(['logistic', 'catboost'], key=lambda n: tuple(np.mean([operating_key(y, p, eligible) for p in predictions[n]], axis=0)))
    return winner, summaries, records, membership, predictions
