from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    admin_api_key: SecretStr = SecretStr("")
    llm_api_key: SecretStr = SecretStr("")
    llm_base_url: str = "https://api.aitunnel.ru/v1"
    llm_model: str = "qwen3-30b-a3b"
    llm_temperature: float = Field(0.2, ge=0, le=2)
    llm_max_tokens: int = Field(1000, ge=1, le=1000)
    llm_reasoning: bool = False
    llm_reasoning_options: bool = True
    llm_json_with_tools: bool = True
    llm_timeout_seconds: float = Field(45, gt=0, le=300)
    llm_input_rub_per_million: float | None = None
    llm_output_rub_per_million: float | None = None
    system_prompt_path: Path = Path("prompts/system.txt")
    data_dir: Path = Path("data")
    database_url: str = "sqlite:///data/knowledge.sqlite3"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "assistant_e5_v1"
    searxng_url: str = "http://localhost:8080"
    web_allowed_domains: list[str] = ["alfabank.ru", "cbr.ru", "fincult.info", "nalog.gov.ru"]
    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_revision: str = "fd1525a9fd15316a2d503bf26ab031a61d056e98"
    tokenizer_model: str = "Qwen/Qwen3-30B-A3B"
    tokenizer_revision: str = "ad44e777bcd18fa416d9da3bd8f70d33ebb85d39"
    model_dir: Path = Path("model-cache")
    dense_min_score: float | None = None  # Disabled until measured by calibrate.
    session_ttl_seconds: int = Field(3600, ge=1)
    max_sessions: int = Field(100, ge=1, le=100)
    context_tokens: int = Field(12000, ge=100, le=12000)
    rag_tokens: int = Field(2500, ge=100, le=2500)
    turn_deadline_seconds: float = Field(60, gt=0, le=300)
    thread_workers: int = Field(4, ge=1, le=16)

    @field_validator("llm_input_rub_per_million", "llm_output_rub_per_million")
    @classmethod
    def nonnegative_price(cls, value):
        if value is not None and value < 0:
            raise ValueError("Price must be nonnegative")
        return value
