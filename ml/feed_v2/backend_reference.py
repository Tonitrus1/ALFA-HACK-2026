"""Executable acceptance reference ONLY. Backend must provide durable transactions.

Never instantiate this in the stateless ML server. Each instance is scoped to one
authenticated (user, company). Server acceptance order defines the latest reaction;
client occurredAt is retained for analytics, not used to overwrite newer state.
"""
from copy import deepcopy

from .catalog import Catalog, digest


class FeedbackProjection:
    def __init__(self, catalog: Catalog):
        self.catalog = catalog
        self.exposures: dict[str, set[str]] = {}
        self.events: dict[str, str] = {}
        self.latest: dict[str, str] = {}
        self.viewed: set[str] = set()

    def issue(self, exposure_id: str, ids: list[str]):
        if not set(ids) <= self.catalog.cards.keys():
            raise ValueError('Unknown issued card')
        if exposure_id in self.exposures and self.exposures[exposure_id] != set(ids):
            raise ValueError('Exposure identity conflict')
        self.exposures[exposure_id] = set(ids)

    def apply(self, event: dict, *, visible_fraction=0., visible_ms=0) -> bool:
        if event['itemId'] not in self.exposures.get(event['exposureId'], set()):
            raise ValueError('Card not issued in this user/company context')
        fingerprint = digest(event)
        previous = self.events.get(event['clientEventId'])
        if previous:
            if previous != fingerprint:
                raise ValueError('Event identity conflict')
            return False
        action = event['action']
        if action == 'VIEW':
            if visible_fraction < .5 or visible_ms < 1000:
                raise ValueError('VIEW visibility criterion not met')
            self.viewed.add(event['itemId'])
        elif action in ('HELPFUL', 'NOT_INTERESTED'):
            self.latest[event['itemId']] = action
        elif action != 'CLICK':
            raise ValueError('Unknown feedback action')
        self.events[event['clientEventId']] = fingerprint
        return True

    @property
    def hidden(self):
        return {i for i, action in self.latest.items() if action == 'NOT_INTERESTED'}

    @property
    def helpful(self):
        return {i for i, action in self.latest.items() if action == 'HELPFUL'}

    @property
    def topic_reactions(self):
        counts = {}
        for i, action in self.latest.items():
            topic = self.catalog.cards[i].topic.value
            item = counts.setdefault(topic, {'helpful': 0, 'notInterested': 0})
            item['helpful' if action == 'HELPFUL' else 'notInterested'] += 1
        return deepcopy(counts)
