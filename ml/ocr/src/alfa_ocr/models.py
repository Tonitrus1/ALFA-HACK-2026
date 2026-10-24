from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Block(StrictModel):
    block_id: str
    text: str
    confidence: float = Field(ge=0, le=1)
    # Coordinates in rendered image pixels, origin top-left.
    bbox: list[float] = Field(min_length=4, max_length=4)


class Page(StrictModel):
    document_id: str
    page: int = Field(ge=1)
    width: int
    height: int
    blocks: list[Block]


class Document(StrictModel):
    document_id: str
    sha256: str
    media_type: str
    pages: int


class Job(StrictModel):
    job_id: str
    status: Literal["queued", "processing", "succeeded", "failed"]
    created_at: float
    expires_at: float
    documents: list[Document]
    error_code: str | None = None
    stage: Literal["queued", "ocr", "llm", "validation", "done"] = "queued"


class Accepted(StrictModel):
    job_id: str
    status: Literal["queued"] = "queued"
    expires_at: float
    status_url: str


class ServiceError(Exception):
    def __init__(self, code: str, status: int = 422):
        self.code = code
        self.status = status
