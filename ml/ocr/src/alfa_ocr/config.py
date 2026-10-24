from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    ocr_api_key: SecretStr = SecretStr("")
    ocr_engine: Literal["paddle", "tesseract"] = "tesseract"
    ocr_enable_mkldnn: bool = True
    data_dir: Path = Path("data")
    prompt_path: Path = Path("prompts/extract.txt")
    schema_path: Path = Path("schemas/extraction.schema.json")
    llm_api_key: SecretStr = SecretStr("")
    llm_base_url: str = "https://api.aitunnel.ru/v1"
    llm_model: str = "deepseek-v4.1-flash-1017"
    llm_response_format: Literal["json_object", "json_schema"] = "json_object"
    llm_reasoning: bool = False
    llm_reasoning_options: bool = True
    llm_timeout_seconds: float = Field(120, gt=0, le=300)
    llm_max_tokens: int = Field(16000, ge=1000, le=32000)
    max_context_chars: int = Field(180000, ge=1000, le=500000)
    max_queued_jobs: int = Field(20, ge=1, le=100)
    max_llm_calls: int = Field(32, ge=1, le=100)
    llm_validation_retries: int = Field(1, ge=0, le=2)
    cpu_threads: int = Field(4, ge=1, le=16)
    page_dpi: int = Field(150, ge=100, le=200)


TTL_SECONDS = 86400
MAX_FILES = 10
MAX_PAGES = 50
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_BATCH_BYTES = 100 * 1024 * 1024
MAX_PIXELS = 20_000_000
