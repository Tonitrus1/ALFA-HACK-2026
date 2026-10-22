"""Stateless scoring, immutable candidate cache and deterministic diversification."""
import importlib.metadata
import json
from collections import Counter
from pathlib import Path

import numpy as np

from .catalog import Catalog, candidate_digest, digest, file_digest
from .schemas import Depth, Profile, RankingRequest, RankingResult, Topic

TASK_TEXT = {
    'PURCHASE': 'Нужны деньги на закупку товаров и пополнение оборотных средств до продажи партии.',
    'CASH_GAP': 'Нужно закрыть кассовый разрыв: оплатить расходы раньше поступления денег от покупателей.',
    'EQUIPMENT': 'Планирую покупку оборудования, доставку и запуск техники в работу.',
    'EXPANSION': 'Планирую расширение бизнеса, новые мощности и расходы на запуск проекта.',
    'EXPLORING': 'Разбираюсь в финансировании бизнеса и хочу понять, с чего начать.',
}
HELP_TEXT = {
    'AMOUNT': 'Нужна помощь: определить потребность, рассчитать сумму и срок финансирования.',
    'OPTIONS': 'Нужна помощь: разобраться в вариантах финансирования и способах получить средства.',
    'COST': 'Нужна помощь: понять стоимость финансирования, комиссии, график и общую сумму платежей.',
    'APPLICATION': 'Нужна помощь: подготовиться к заявке, собрать документы и согласованный расчёт проекта.',
}
DEPTH_TEXT = {
    'BASICS': 'Объяснять с основ, простыми словами.',
    'EXPLAINED': 'Объяснять с краткими пояснениями терминов.',
    'PRACTICAL': 'Интересуют практические нюансы и проверка расчётов.',
}
BUSINESS_TEXT = {'RETAIL': 'Розничная торговля', 'SERVICES': 'Услуги',
                 'MANUFACTURING': 'Производство', 'WHOLESALE': 'Оптовая торговля',
                 'HOSPITALITY': 'Общественное питание и гостеприимство', 'OTHER': 'Другая категория бизнеса'}
STAGE_TEXT = {'DRAFT': 'Готовлю черновик заявки', 'SUBMITTED': 'Заявка отправлена',
              'NEEDS_INFORMATION': 'По заявке запрошена дополнительная информация',
              'REVIEW': 'Заявка рассматривается', 'DECISION': 'По заявке получено решение'}
PRIMARY_TOPICS = {'PURCHASE': Topic.WORKING_CAPITAL, 'CASH_GAP': Topic.CASH_GAP,
                  'EQUIPMENT': Topic.EQUIPMENT, 'EXPANSION': Topic.EQUIPMENT,
                  'EXPLORING': Topic.APPLICATION}


class RankingError(Exception):
    def __init__(self, code: str, message: str, status: int = 409):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


def build_query(profile: Profile) -> str:
    parts = []
    for value, mapping in [(profile.task, TASK_TEXT), (profile.help, HELP_TEXT),
                           (profile.businessCategory, BUSINESS_TEXT),
                           (profile.applicationStage, STAGE_TEXT), (profile.depth, DEPTH_TEXT)]:
        if value is not None:
            parts.append(mapping[value])
    return 'query: ' + ' '.join(parts) if parts else ''


def validate_request(catalog: Catalog, request: RankingRequest):
    if request.catalogVersion != catalog.version or request.catalogDigest != catalog.digest:
        raise RankingError('CATALOG_MISMATCH', 'Catalog version or digest does not match the pinned catalog')
    if candidate_digest(request.candidateIds) != request.candidateSetDigest:
        raise RankingError('CANDIDATE_SET_MISMATCH', 'candidateSetDigest does not match candidateIds')
    if set(request.candidateIds) - catalog.cards.keys():
        raise RankingError('UNKNOWN_CANDIDATE', 'Candidates must belong to the published catalog')
    if request.candidateTexts is not None:
        texts = {c.itemId: c.text for c in request.candidateTexts}
        if (len(texts) != len(request.candidateTexts) or set(texts) != set(request.candidateIds)
                or any(texts[i] != catalog.cards[i].passage for i in request.candidateIds)):
            raise RankingError('CANDIDATE_TEXT_MISMATCH', 'Texts must exactly match title + newline + text in the pinned catalog')


def topic_bonus(request, topic):
    counts = request.topicReactions.get(topic)
    difference = counts.helpful - counts.notInterested if counts else 0
    return .05 * max(-2, min(2, difference))


def diversify(ids: list[str], scores: dict[str, float], catalog: Catalog) -> list[str]:
    remaining = sorted(ids, key=lambda i: (-scores[i], i))
    result = []
    while remaining:
        counts = Counter()
        for _ in range(min(6, len(remaining))):
            # Relax only when no remaining theme is below the cap.
            index = next((j for j, i in enumerate(remaining)
                          if counts[catalog.cards[i].topic] < 2), 0)
            chosen = remaining.pop(index)
            result.append(chosen)
            counts[catalog.cards[chosen].topic] += 1
    return result


def explanation(card, request, mode):
    p = request.profile
    if p.help and p.help in card.help:
        return {'reasonCategory': 'HELP_MATCH', 'message': {
            'AMOUNT': 'Поможет определить потребность и сумму финансирования.',
            'OPTIONS': 'Поможет разобраться в вариантах финансирования.',
            'COST': 'Вы хотите разобраться в стоимости и платежах.',
            'APPLICATION': 'Вы выбрали помощь в подготовке к заявке.',
        }[p.help]}
    if p.task and p.task in card.tasks:
        return {'reasonCategory': 'TASK_MATCH', 'message': 'Материал связан с выбранной вами задачей.'}
    if topic_bonus(request, card.topic) > 0:
        return {'reasonCategory': 'TOPIC_FEEDBACK', 'message': 'Вы отмечали полезные материалы этой темы.'}
    if p.applicationStage and p.applicationStage in card.applicationStages:
        return {'reasonCategory': 'CONTEXT_MATCH', 'message': 'Материал связан со стадией выбранной заявки.'}
    if p.depth and p.depth == card.depth:
        return {'reasonCategory': 'DEPTH_MATCH', 'message': 'Соответствует выбранной глубине объяснения.'}
    if not build_query(p):
        return {'reasonCategory': 'INTRODUCTION', 'message': 'Вводная подборка о финансировании бизнеса.'}
    return {'reasonCategory': 'SEMANTIC_MATCH' if mode == 'MODEL' else 'TOPIC_DIVERSITY',
            'message': 'Дополняет подборку по вашему запросу.' if mode == 'MODEL'
                       else 'Другая тема для знакомства с финансированием бизнеса.'}


class RulesRanker:
    """Backend may invoke this directly on timeout/503. No model imports or state."""
    def __init__(self, catalog: Catalog):
        self.catalog = catalog

    def base_scores(self, request):
        p = request.profile
        return {i: (.12 * bool(p.task and self.catalog.cards[i].topic == PRIMARY_TOPICS[p.task])
                    + .10 * bool(p.help and p.help in self.catalog.cards[i].help)
                    + .04 * bool(p.applicationStage and p.applicationStage in self.catalog.cards[i].applicationStages)
                    + .04 * bool(p.businessCategory and p.businessCategory in self.catalog.cards[i].businessCategories)
                    + .02 * bool(not p.depth and self.catalog.cards[i].depth == Depth.BASICS))
                for i in request.candidateIds}

    def result(self, request, scores, mode, release_id, *, adjustments=True):
        scores = dict(scores)
        if adjustments:
            for i in request.candidateIds:
                card = self.catalog.cards[i]
                scores[i] += topic_bonus(request, card.topic) + .03 * bool(request.profile.depth == card.depth)
        ranked = diversify(request.candidateIds, scores, self.catalog)
        if len(ranked) != len(request.candidateIds) or set(ranked) != set(request.candidateIds):
            raise RuntimeError('Candidate permutation invariant failed')
        return RankingResult(requestId=request.requestId, scope='FEED', rankedIds=ranked,
                             candidateSetDigest=request.candidateSetDigest, exposureId=request.exposureId,
                             releaseId=release_id, mode=mode,
                             reasonCategory='PROFILE_RELEVANCE' if mode == 'MODEL' else 'DETERMINISTIC_RULES',
                             catalogDigest=self.catalog.digest,
                             explanations={i: explanation(self.catalog.cards[i], request, mode) for i in ranked})

    def rank(self, request: RankingRequest) -> RankingResult:
        validate_request(self.catalog, request)
        return self.result(request, self.base_scores(request), 'RULES', 'feed-rules-v1')


class ModelRanker(RulesRanker):
    def __init__(self, catalog: Catalog, bundle: Path, threads: int = 4):
        super().__init__(catalog)
        bundle = Path(bundle)
        manifest = json.loads((bundle / 'manifest.json').read_text())
        claimed = manifest.pop('bundleDigest')
        if digest(manifest) != claimed:
            raise ValueError('Bundle manifest digest mismatch')
        lock = json.loads(Path(__file__).with_name('model-lock.json').read_text())
        if manifest['modelLock'] != lock or manifest['catalogDigest'] != catalog.digest:
            raise ValueError('Bundle model or catalog mismatch')
        for name, expected in manifest['files'].items():
            relative = Path(name)
            if relative.is_absolute() or '..' in relative.parts or file_digest(bundle / name) != expected:
                raise ValueError('Bundle checksum mismatch: ' + name)
        required = {'embeddings.npy'} | {'model/' + name for name in lock['files']}
        if set(manifest['files']) != required:
            raise ValueError('Bundle file inventory mismatch')
        for name, expected in lock['sha256'].items():
            if manifest['files']['model/' + name] != expected:
                raise ValueError('Model file differs from pinned checksum')
        for lib, version in manifest['libraries'].items():
            if importlib.metadata.version(lib) != version:
                raise ValueError('Dependency mismatch: ' + lib)
        if manifest['cardIds'] != sorted(catalog.cards):
            raise ValueError('Cache candidate inventory mismatch')
        vectors = np.load(bundle / 'embeddings.npy', allow_pickle=False)
        if (vectors.shape != (len(catalog.cards), 384) or not np.isfinite(vectors).all()
                or not np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-5)):
            raise ValueError('Invalid candidate embeddings')
        self.vectors = dict(zip(manifest['cardIds'], vectors))
        from .encoder import E5Encoder
        self.encoder = E5Encoder(bundle / 'model', threads)
        self.release_id = 'feed-e5-v1-' + claimed[:12]
        self.bundle_digest = claimed
        self.encoder.encode(['query: Финансирование бизнеса.'])  # Warm-up before readiness.

    def rank(self, request: RankingRequest) -> RankingResult:
        validate_request(self.catalog, request)
        query = build_query(request.profile)
        if not query:
            return super().rank(request)
        vector = self.encoder.encode([query])[0]
        if not np.isfinite(vector).all():
            raise RuntimeError('Non-finite query embedding')
        scores = {i: float(self.vectors[i] @ vector) for i in request.candidateIds}
        return self.result(request, scores, 'MODEL', self.release_id)
