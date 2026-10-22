"""One versioned, allow-listed transformation for training and serving."""
import json
from functools import lru_cache

import numpy as np

from .ranker import build_query
from .schemas import Profile

VERSION = 'feed-features-v1'
CATEGORICAL = ['task', 'help', 'depth', 'businessCategory', 'applicationStage',
               'item_topic', 'item_depth', 'item_format']
NUMERIC = ['semantic_similarity', 'task_match', 'help_match', 'depth_match',
           'business_match', 'stage_match', 'business_universal', 'helpful',
           'not_interested', 'reaction_difference'] + [k + '_missing' for k in CATEGORICAL[:5]]
NAMES = CATEGORICAL + NUMERIC


class FeatureBuilder:
    def __init__(self, semantic):
        self.semantic = semantic
        self.catalog = semantic.catalog
        self._similarities = lru_cache(maxsize=8192)(self._compute_similarities)

    def _compute_similarities(self, profile_json):
        profile = Profile.model_validate_json(profile_json)
        query = build_query(profile)
        if not query:
            return {i: 0. for i in self.catalog.cards}
        vector = self.semantic.encoder.encode([query])[0]
        return {i: float(v @ vector) for i, v in self.semantic.vectors.items()}

    def similarities(self, request):
        return self._similarities(json.dumps(request.profile.model_dump(mode='json'), sort_keys=True))

    def rows(self, request):
        similarities = self.similarities(request)
        profile = request.profile.model_dump(mode='json')
        rows = []
        for i in request.candidateIds:
            card = self.catalog.cards[i]
            counts = request.topicReactions.get(card.topic)
            pos, neg = (counts.helpful, counts.notInterested) if counts else (0, 0)
            numeric = [similarities[i], bool(profile['task'] and profile['task'] in card.tasks),
                       bool(profile['help'] and profile['help'] in card.help),
                       profile['depth'] == card.depth,
                       bool(profile['businessCategory'] and profile['businessCategory'] in card.businessCategories),
                       bool(profile['applicationStage'] and profile['applicationStage'] in card.applicationStages),
                       not card.businessCategories, min(pos, 1000), min(neg, 1000),
                       max(-1000, min(1000, pos - neg))]
            numeric += [profile[k] is None for k in CATEGORICAL[:5]]
            if not np.isfinite(numeric).all():
                raise ValueError('Non-finite feature')
            rows.append([profile[k] or '__MISSING__' for k in CATEGORICAL[:5]]
                        + [card.topic.value, card.depth.value, card.format]
                        + [float(n) for n in numeric])
        return rows
