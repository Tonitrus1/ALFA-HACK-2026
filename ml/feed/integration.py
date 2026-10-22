"""Reference backend boundary; no storage, sessions, cursors or public endpoints."""
from copy import deepcopy

import httpx

from .catalog import Catalog, candidate_digest
from .ranker import RulesRanker, validate_request
from .schemas import RankingRequest, RankingResult


def eligible_ids(catalog: Catalog, *, viewed=(), hidden=(), issued=()) -> list[str]:
    """Backend supplies state scoped by authenticated user AND company.

    issued is the cumulative set already sent in this selection, regardless of VIEW.
    Sending is not a confirmed view and must never update viewed.
    """
    excluded = set(viewed) | set(hidden) | set(issued)
    return sorted(catalog.cards.keys() - excluded)


def replay_page(snapshot: dict, *, hidden=(), reactions=None) -> dict:
    """Keep content/order/exposure; omit hidden and refresh current user reactions."""
    page = deepcopy(snapshot)
    excluded = set(hidden)
    page['cards'] = [card for card in page['cards'] if card['contentId'] not in excluded]
    if reactions is not None:
        for card in page['cards']:
            card['userReaction'] = reactions.get(card['contentId'])
    return page


def make_request(catalog: Catalog, *, request_id, exposure_id, candidate_ids, profile,
                 topic_reactions=None) -> RankingRequest:
    return RankingRequest(requestId=request_id, scope='FEED', exposureId=exposure_id,
                          candidateIds=candidate_ids, candidateSetDigest=candidate_digest(candidate_ids),
                          catalogVersion=catalog.version, catalogDigest=catalog.digest,
                          profile=profile, topicReactions=topic_reactions or {})


def feed_cards(catalog: Catalog, result: RankingResult, *, reactions=None) -> list[dict]:
    """Backend takes six; texts come exclusively from the versioned catalog."""
    reactions = reactions or {}
    return [dict(contentId=i, version=catalog.cards[i].version, title=catalog.cards[i].title,
                 text=catalog.cards[i].text, topic=catalog.cards[i].topic.value,
                 depth=catalog.cards[i].depth.value,
                 illustration=f'/assets/feed/v{catalog.version}/' + catalog.cards[i].illustration,
                 reasonCategory=result.explanations[i].reasonCategory,
                 reason=result.explanations[i].message, userReaction=reactions.get(i))
            for i in result.rankedIds[:6]]


class FeedClient:
    """Port into backend. Catalog/authorization errors must not be hidden by fallback."""
    def __init__(self, catalog: Catalog, base_url: str, token: str, transport=None):
        self.catalog = catalog
        self.rules = RulesRanker(catalog)
        self.http = httpx.Client(base_url=base_url, timeout=1.8, transport=transport,
                                 headers={'X-Service-Token': token})

    def close(self):
        self.http.close()

    def rank(self, request: RankingRequest) -> RankingResult:
        validate_request(self.catalog, request)
        try:
            response = self.http.post('/internal/v2/rankings', json=request.model_dump(mode='json', exclude_none=True),
                                      headers={'Idempotency-Key': request.requestId})
            if response.status_code in (429, 500, 502, 503, 504):
                return self.rules.rank(request)
            response.raise_for_status()
        except httpx.TransportError:
            return self.rules.rank(request)
        # Even a successful remote response is untrusted until its permutation and identity match.
        try:
            result = RankingResult.model_validate(response.json())
            if (len(result.rankedIds) != len(request.candidateIds)
                    or set(result.rankedIds) != set(request.candidateIds)
                    or result.candidateSetDigest != request.candidateSetDigest
                    or result.catalogDigest != request.catalogDigest
                    or result.requestId != request.requestId
                    or result.exposureId != request.exposureId
                    or set(result.explanations) != set(request.candidateIds)):
                raise ValueError('Invalid ranking identity or permutation')
        except ValueError:
            return self.rules.rank(request)
        return result
