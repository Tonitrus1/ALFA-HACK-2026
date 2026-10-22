"""CPU pairwise ranking on explicit/weak observed labels; never reads oracle truth."""
import argparse
import importlib.metadata
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path

from .catalog import Catalog, digest, file_digest
from .dataset import load_manifest, rows, write_json
from .features import CATEGORICAL, NAMES, VERSION, FeatureBuilder
from .ranker import ModelRanker, build_query
from .schemas import RankingRequest
from .validate_data import validate


def observed_labels(root, splits=None):
    labels = defaultdict(dict)
    for event in rows(root, 'events.parquet'):
        if splits is not None and event['split'] not in splits:
            continue
        group, item, action = event['exposureId'], event['itemId'], event['action']
        if action in ('HELPFUL', 'NOT_INTERESTED'):
            labels[group][item] = 2 if action == 'HELPFUL' else 0
        elif action == 'CLICK' and labels[group].get(item) not in (0, 2):
            labels[group][item] = 1
    return labels


def training_pools(root, builder):
    from catboost import Pool
    manifest = load_manifest(root)
    if manifest['catalogDigest'] != builder.catalog.digest:
        raise ValueError('Feature builder catalog mismatch')
    labels = observed_labels(root, splits={'train', 'validation'})
    partitions = {s: dict(x=[], y=[], group=[]) for s in ('train', 'validation')}
    counts = Counter()
    for row in rows(root, 'requests.parquet'):
        # Test is never used during fitting or hyperparameter selection.
        if row['split'] not in partitions:
            continue
        request = RankingRequest.model_validate_json(row['requestJson'])
        counts[row['split'] + '_all_groups'] += 1
        known = labels[row['exposureId']]
        if not build_query(request.profile) or len(known) < 2 or len(set(known.values())) < 2:
            counts[row['split'] + '_excluded_groups'] += 1
            continue
        ids = [i for i in request.candidateIds if i in known]
        subset = request.model_copy(update={'candidateIds': ids})
        part = partitions[row['split']]
        part['x'].extend(builder.rows(subset))
        part['y'].extend(known[i] for i in ids)
        part['group'].extend([row['exposureId']] * len(ids))
        counts[row['split'] + '_groups'] += 1
        counts[row['split'] + '_rows'] += len(ids)
    pools = {}
    for name, part in partitions.items():
        if not part['y']:
            raise ValueError('No informative groups in ' + name)
        pools[name] = Pool(part['x'], label=part['y'], group_id=part['group'],
                           cat_features=CATEGORICAL, feature_names=NAMES)
    return pools, dict(counts)


def train(data, e5_bundle, output):
    from catboost import CatBoostRanker
    output, data, e5_bundle = Path(output), Path(data), Path(e5_bundle)
    if output.exists():
        raise FileExistsError('Use a new bundle directory')
    validation = validate(data)
    manifest = load_manifest(data)
    semantic = ModelRanker(Catalog(), e5_bundle)
    pools, counts = training_pools(data, FeatureBuilder(semantic))
    best, best_value, runs = None, float('-inf'), []
    for depth in (4, 6):
        for rate in (.03, .1):
            params = dict(loss_function='PairLogit', eval_metric='NDCG:top=6',
                          depth=depth, learning_rate=rate, iterations=500,
                          early_stopping_rounds=50, random_seed=20261022,
                          task_type='CPU', thread_count=4, allow_writing_files=False, verbose=False)
            candidate = CatBoostRanker(**params)
            candidate.fit(pools['train'], eval_set=pools['validation'], use_best_model=True)
            metrics = candidate.get_best_score()['validation']
            score = next(v for k, v in metrics.items() if k.startswith('NDCG'))
            runs.append(dict(params=params, validationNDCG6=score, trees=candidate.tree_count_))
            if score > best_value:
                best, best_value = candidate, score
    output.mkdir(parents=True)
    best.save_model(str(output / 'model.cbm'))
    report = dict(isSynthetic=True, objective='PairLogit', selectionSplit='validation',
                  testUsedForSelection=False, counts=counts, dataValidation=validation,
                  runs=runs, selectedValidationNDCG6=best_value,
                  selectedParams=best.get_params(),
                  featureImportance=dict(zip(NAMES, map(float, best.get_feature_importance(pools['validation'])))),
                  limitations=['Observed labels are selective and position-biased.',
                               'Validation NDCG concerns labeled exposed items, not all eligible cards.',
                               'Independent human review is required before promotion.'])
    write_json(output / 'training-report.json', report)
    # Self-contained bundle, including verified E5 weights; no deployment-time links.
    shutil.copytree(e5_bundle, output / 'e5')
    lineage = dict(rankerType='CatBoostRanker/PairLogit', featureSchemaVersion=VERSION,
        featureNames=NAMES, catboostVersion=importlib.metadata.version('catboost'),
        catalogDigest=semantic.catalog.digest, catalogVersion=semantic.catalog.version,
        e5BundleDigest=semantic.bundle_digest, datasetManifestDigest=file_digest(data / 'manifest.json'),
        datasetFiles={n: manifest['files'][n] for n in ('requests.parquet','issued.parquet','events.parquet')},
        isSynthetic=True, defaultEligible=False,
        files={n: file_digest(output / n) for n in ('model.cbm', 'training-report.json')})
    lineage['bundleDigest'] = digest(lineage)
    write_json(output / 'manifest.json', lineage)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--e5-bundle', type=Path, default=Path('.local/feed-bundle'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = train(args.data, args.e5_bundle, args.output)
    print(json.dumps({k: report[k] for k in ('counts', 'selectedValidationNDCG6')}, indent=2))


if __name__ == '__main__':
    main()
