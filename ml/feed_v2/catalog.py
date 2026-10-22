"""Versioned editorial source shared by ML and backend. No copied card texts."""
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import Field, StrictInt

from .schemas import Business, Depth, Help, Identifier, Stage, StrictModel, Task, Topic

DEFAULT_CATALOG = Path(__file__).parent / 'catalog' / 'cards.json'


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def file_digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def candidate_digest(ids: list[str]) -> str:
    return digest(sorted(ids))


class Card(StrictModel):
    id: Identifier
    version: StrictInt = Field(ge=1)
    title: str = Field(min_length=1, max_length=70)
    text: str = Field(min_length=1, max_length=4000)
    topic: Topic
    depth: Depth
    tasks: list[Task] = Field(min_length=1)
    help: list[Help] = Field(min_length=1)
    businessCategories: list[Business] = Field(default_factory=list)
    applicationStages: list[Stage] = Field(default_factory=list)
    illustration: str = Field(pattern=r'^illustrations/[a-z_-]+\.svg$')
    status: Literal['DRAFT', 'PUBLISHED']
    format: Literal['ADVICE', 'SCENARIO', 'CHECKLIST']

    @property
    def passage(self) -> str:
        return self.title + '\n' + self.text


class CatalogDocument(StrictModel):
    catalogVersion: StrictInt = Field(ge=1)
    cards: list[Card]


class Catalog:
    def __init__(self, path: Path = DEFAULT_CATALOG):
        self.path = Path(path)
        raw = json.loads(self.path.read_text())
        self.document = CatalogDocument.model_validate(raw)
        self.version = self.document.catalogVersion
        self.digest = digest(raw)
        self.cards = {card.id: card for card in self.document.cards if card.status == 'PUBLISHED'}
        if len({card.id for card in self.document.cards}) != len(self.document.cards):
            raise ValueError('Duplicate catalog IDs')

    def validate_publication(self, previous: dict | None = None):
        review = json.loads((self.path.parent / 'review.json').read_text())
        approved = {row['id']: row for row in review['cards'] if row['approved']}
        if (review['catalogDigest'] != self.digest or set(approved) != set(self.cards)
                or any(approved[i]['version'] != card.version for i, card in self.cards.items())):
            raise ValueError('Published catalog needs a matching complete editorial review')
        if previous and previous['catalogDigest'] != self.digest:
            if self.version <= previous['catalogVersion']:
                raise ValueError('Changed catalog must increment catalogVersion')
            for i, card in self.cards.items():
                old = previous['cards'].get(i)
                if (old and digest(card.model_dump(mode='json')) != old['digest']
                        and card.version <= old['version']):
                    raise ValueError('Changed card must increment version: ' + i)

    def validate_editorial(self) -> dict:
        cards = self.document.cards
        coverage = json.loads((self.path.parent / 'coverage.json').read_text())
        expected = coverage['catalogs'][str(self.version)]
        if len(cards) != expected['publishedCards'] or len(self.cards) != expected['publishedCards']:
            raise ValueError('Published card count differs from coverage configuration')
        counts = Counter((c.topic, c.depth) for c in cards)
        if any(counts[t, d] != expected['cardsPerTopicDepth'] for t in Topic for d in Depth):
            raise ValueError('Topic/depth coverage differs from configuration')
        normalized = [re.sub(r'\W+', '', c.text.lower()) for c in cards]
        if len(set(normalized)) != len(cards):
            raise ValueError('Duplicate card texts')
        for i, a in enumerate(normalized):
            from difflib import SequenceMatcher
            for b in normalized[i + 1:]:
                if SequenceMatcher(None, a, b).ratio() > .85:
                    raise ValueError('Near-duplicate card texts')
        word_counts = {}
        for c in cards:
            words = len(c.text.split())
            if not 50 <= words <= 90:
                raise ValueError(f'{c.id}: expected 50–90 words, got {words}')
            if c.format == 'SCENARIO' and 'вымышлен' not in c.text.lower():
                raise ValueError(f'{c.id}: fictional example must be marked')
            if not (self.path.parent / c.illustration).is_file():
                raise ValueError('Missing illustration: ' + c.illustration)
            word_counts[c.id] = words
        return {'cards': len(cards), 'catalogDigest': self.digest, 'wordCounts': word_counts}
