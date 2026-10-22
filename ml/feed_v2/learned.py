"""CatBoost ranker with immutable lineage, shared features and no duplicate boosts."""
import importlib.metadata
import json
from pathlib import Path

import numpy as np

from .catalog import digest, file_digest
from .features import CATEGORICAL, NAMES, VERSION, FeatureBuilder
from .ranker import ModelRanker, RulesRanker, build_query, validate_request


class LearnedRanker(RulesRanker):
    def __init__(self, catalog, bundle, threads=4):
        super().__init__(catalog)
        bundle = Path(bundle)
        manifest = json.loads((bundle / 'manifest.json').read_text())
        claimed = manifest.pop('bundleDigest')
        if digest(manifest) != claimed:
            raise ValueError('Learned manifest digest mismatch')
        if (manifest['featureSchemaVersion'] != VERSION or manifest['featureNames'] != NAMES
                or manifest['catalogDigest'] != catalog.digest or manifest['catalogVersion'] != catalog.version
                or manifest['rankerType'] != 'CatBoostRanker/PairLogit'
                or manifest['catboostVersion'] != importlib.metadata.version('catboost')):
            raise ValueError('Learned feature/catalog/library mismatch')
        if set(manifest['files']) != {'model.cbm', 'training-report.json'}:
            raise ValueError('Learned bundle file inventory mismatch')
        for name, expected in manifest['files'].items():
            if file_digest(bundle / name) != expected:
                raise ValueError('Learned bundle checksum mismatch: ' + name)
        self.semantic = ModelRanker(catalog, bundle / 'e5', threads)
        if manifest['e5BundleDigest'] != self.semantic.bundle_digest:
            raise ValueError('Learned/E5 lineage mismatch')
        from catboost import CatBoostRanker
        self.model = CatBoostRanker()
        self.model.load_model(str(bundle / 'model.cbm'))
        if self.model.feature_names_ != NAMES:
            raise ValueError('Model feature names differ from schema')
        self.features = FeatureBuilder(self.semantic)
        self.threads = threads
        self.bundle_digest = claimed
        self.release_id = 'feed-catboost-v1-' + claimed[:12]

    def scores(self, request):
        from catboost import Pool
        values = self.features.rows(request)
        pool = Pool(values, cat_features=CATEGORICAL, feature_names=NAMES)
        scores = np.asarray(self.model.predict(pool, thread_count=self.threads))
        if scores.shape != (len(request.candidateIds),) or not np.isfinite(scores).all():
            raise ValueError('Invalid learned predictions')
        return dict(zip(request.candidateIds, map(float, scores)))

    def rank(self, request):
        validate_request(self.catalog, request)
        if not build_query(request.profile):
            return super().rank(request)
        return self.result(request, self.scores(request), 'MODEL', self.release_id, adjustments=False)
