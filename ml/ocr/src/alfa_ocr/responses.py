from typing import Any, Literal

from pydantic import Field

from .models import Page, StrictModel


class ExtractionResult(StrictModel):
    job_id: str
    requires_confirmation: Literal[True]
    extraction: dict[str, Any] = Field(
        description="Validated against the editable JSON Schema returned by GET /v1/schema; see schemas/extraction.schema.json for all typed fields."
    )
    provenance: dict[str, Any] = Field(
        description="Prompt/schema hashes, OCR engine/version, LLM model/calls/usage/validation_repairs and elapsed seconds."
    )


class OCRResult(StrictModel):
    engine: Literal["paddle", "tesseract"]
    engine_version: str
    pages: list[Page]
    seconds: float
