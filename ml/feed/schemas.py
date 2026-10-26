"""Only explicitly allowed, non-financial profile fields enter the encoder."""
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator


class Topic(str, Enum):
    CASH_GAP = 'CASH_GAP'
    WORKING_CAPITAL = 'WORKING_CAPITAL'
    SEASONALITY = 'SEASONALITY'
    EQUIPMENT = 'EQUIPMENT'
    APPLICATION = 'APPLICATION'
    FINANCING_COST = 'FINANCING_COST'


class Task(str, Enum):
    PURCHASE = 'PURCHASE'
    CASH_GAP = 'CASH_GAP'
    EQUIPMENT = 'EQUIPMENT'
    EXPANSION = 'EXPANSION'
    EXPLORING = 'EXPLORING'


class Help(str, Enum):
    AMOUNT = 'AMOUNT'
    OPTIONS = 'OPTIONS'
    COST = 'COST'
    APPLICATION = 'APPLICATION'


class Depth(str, Enum):
    BASICS = 'BASICS'
    EXPLAINED = 'EXPLAINED'
    PRACTICAL = 'PRACTICAL'


class Business(str, Enum):
    RETAIL = 'RETAIL'
    SERVICES = 'SERVICES'
    MANUFACTURING = 'MANUFACTURING'
    WHOLESALE = 'WHOLESALE'
    HOSPITALITY = 'HOSPITALITY'
    OTHER = 'OTHER'


class Stage(str, Enum):
    DRAFT = 'DRAFT'
    SUBMITTED = 'SUBMITTED'
    NEEDS_INFORMATION = 'NEEDS_INFORMATION'
    REVIEW = 'REVIEW'
    DECISION = 'DECISION'


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Preferences(StrictModel):
    task: Task | None = None
    help: Help | None = None
    depth: Depth | None = None


class Profile(Preferences):
    businessCategory: Business | None = None
    applicationStage: Stage | None = None


class ReactionCounts(StrictModel):
    helpful: StrictInt = Field(default=0, ge=0, le=9007199254740991)
    notInterested: StrictInt = Field(default=0, ge=0, le=9007199254740991)


Identifier = Annotated[str, Field(min_length=1, max_length=128)]
Digest = Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]


class CandidateText(StrictModel):
    itemId: Identifier
    text: str = Field(min_length=1, max_length=4000)


class RankingRequest(StrictModel):
    requestId: Identifier
    scope: Literal['FEED']
    exposureId: Identifier
    candidateIds: list[Identifier] = Field(min_length=1, max_length=100, json_schema_extra={'uniqueItems': True})
    candidateSetDigest: Digest
    catalogVersion: StrictInt = Field(ge=1, le=9007199254740991)
    catalogDigest: Digest
    profile: Profile
    topicReactions: dict[Topic, ReactionCounts] = Field(default_factory=dict)
    candidateTexts: list[CandidateText] | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode='after')
    def unique_candidates(self):
        if len(set(self.candidateIds)) != len(self.candidateIds):
            raise ValueError('candidateIds must be unique')
        return self


class Explanation(StrictModel):
    reasonCategory: Identifier
    message: str = Field(min_length=1, max_length=500)


class RankingResult(StrictModel):
    requestId: Identifier
    scope: Literal['FEED']
    rankedIds: list[Identifier] = Field(min_length=1, max_length=100, json_schema_extra={'uniqueItems': True})
    candidateSetDigest: Digest
    exposureId: Identifier
    releaseId: Identifier
    mode: Literal['MODEL', 'RULES']
    reasonCategory: Identifier
    catalogDigest: Digest
    explanations: dict[str, Explanation]

    @model_validator(mode='after')
    def complete_ranking(self):
        if len(set(self.rankedIds)) != len(self.rankedIds):
            raise ValueError('rankedIds must be unique')
        if set(self.explanations) != set(self.rankedIds):
            raise ValueError('explanations must contain exactly rankedIds')
        return self


class MLError(StrictModel):
    code: Identifier
    message: str = Field(min_length=1, max_length=500)
    correlationId: Identifier
    fallbackAction: Literal['MANUAL_REVIEW', 'RULES', 'MANUAL_INPUT',
                            'SEARCH_ONLY', 'RETRY_LATER', 'NONE'] = 'NONE'
