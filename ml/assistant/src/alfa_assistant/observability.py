import json
import logging
from datetime import UTC, datetime

SAFE_FIELDS = (
    "request_id",
    "session_id",
    "model",
    "prompt_hash",
    "latency_ms",
    "llm_ms",
    "search_ms",
    "fetch_ms",
    "tool_ms",
    "input_tokens",
    "output_tokens",
    "steps",
    "tool_calls",
    "error_code",
    "version_id",
    "version_ids",
    "status",
)


class SafeJSONFormatter(logging.Formatter):
    def format(self, record):
        # Deliberate allowlist: no message args, exception strings, documents or SDK dumps.
        return json.dumps(
            {
                "time": datetime.now(UTC).isoformat(),
                "level": record.levelname,
                "event": record.msg
                if record.name.startswith("alfa_assistant.") and not record.args
                else "external_log",
                **{key: getattr(record, key) for key in SAFE_FIELDS if hasattr(record, key)},
            },
            ensure_ascii=False,
        )


def setup_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(SafeJSONFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    for noisy in ("httpx", "httpcore", "openai", "uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.CRITICAL)
