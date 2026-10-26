from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Identity(StrictModel):
    actor_id: str = Field(min_length=1, max_length=256)
    company_id: str = Field(min_length=1, max_length=256)


class BankContext(StrictModel):
    company_id: str
    products: list[dict] = Field(max_length=1000)
    applications: list[dict] = Field(max_length=10000)


class CreateSession(StrictModel):
    identity: Identity | None = None
    demo_user_id: str | None = None
    system_prompt: str | None = Field(None, min_length=1, max_length=20000)


class NewMessage(StrictModel):
    bank_context: BankContext | None = None
    client_message_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=8000)


class Metadata(StrictModel):
    title: str = Field(min_length=1, max_length=300)
    source_type: Literal["SYNTHETIC", "PUBLIC_NOTE", "WEB"] = "SYNTHETIC"
    source_url: str | None = None
    retrieved_at: datetime | None = None
    effective_until: datetime | None = None
    is_synthetic: bool = True
    product_id: str | None = None
    attribution: str = Field(min_length=1, max_length=1000)
    allowed_use: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def provenance(self):
        if self.source_type != "SYNTHETIC" and (self.is_synthetic or not self.source_url):
            raise ValueError("Public materials need URL and is_synthetic=false")
        if self.source_type == "SYNTHETIC" and not self.is_synthetic:
            raise ValueError("Synthetic source must be marked synthetic")
        if self.effective_until and self.effective_until.tzinfo is None:
            raise ValueError("effective_until requires timezone")
        return self


class ConfirmCandidate(StrictModel):
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    allowed_use: str = Field(min_length=1, max_length=1000)
    attribution: str = Field(min_length=1, max_length=1000)


class Query(StrictModel):
    query: str = Field(min_length=1, max_length=2000)


class ReadPage(StrictModel):
    result_id: str = Field(min_length=1, max_length=100)


class ProposeSave(StrictModel):
    candidate_id: str = Field(min_length=1, max_length=100)


class NoArgs(StrictModel):
    pass


class ApplicationArgs(StrictModel):
    application_id: str = Field(min_length=1, max_length=100)


class DocumentsArgs(StrictModel):
    product_id: str | None = None
    application_id: str | None = None

    @model_validator(mode="after")
    def at_most_one(self):
        if self.product_id is not None and not self.product_id.strip():
            raise ValueError("product_id must not be empty")
        if self.application_id is not None and not self.application_id.strip():
            raise ValueError("application_id must not be empty")
        if self.product_id and self.application_id:
            raise ValueError("Supply at most one of product_id or application_id")
        return self


class AnnuityArgs(StrictModel):
    amount: Decimal = Field(gt=0, le=1_000_000_000, max_digits=14, decimal_places=2)
    annual_rate: Decimal = Field(ge=0, le=100, max_digits=7, decimal_places=4)
    months: int = Field(ge=1, le=600, strict=True)


class ModelAnswer(StrictModel):
    status: Literal["ANSWER", "INSUFFICIENT_EVIDENCE"] = "ANSWER"
    answer: str = Field(min_length=1, max_length=10000)
    citation_ids: list[str] = Field(default_factory=list, max_length=5)


class KnowledgeCitation(StrictModel):
    id: str
    type: Literal["KNOWLEDGE"]
    title: str
    document_id: str
    version_id: str
    version: int
    page: int | None = None
    section: str | None = None
    metadata: Metadata


class WebCitation(StrictModel):
    id: str
    type: Literal["WEB"]
    title: str
    url: str
    retrieved_at: datetime


class PendingAction(StrictModel):
    type: Literal["CONFIRM_KNOWLEDGE_SAVE"]
    candidate_id: str
    url: str
    title: str
    sha256: str
    description: str


class Usage(StrictModel):
    input_tokens: int | None
    output_tokens: int | None
    known_input_tokens: int
    known_output_tokens: int
    complete: bool
    estimated_cost_rub: float | None
    error_code: str | None


class ChatResponse(StrictModel):
    session_id: str
    message_id: str
    status: Literal["ANSWER", "INSUFFICIENT_EVIDENCE", "SEARCH_ONLY"]
    answer: str
    citations: list[Annotated[KnowledgeCitation | WebCitation, Field(discriminator="type")]]
    pending_actions: list[PendingAction]
    usage: Usage
    latency_ms: int
    context_truncated: bool
    request_id: str
