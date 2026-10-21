import json
import re
from dataclasses import dataclass, field

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI

from .errors import ServiceError


def public_content(content):
    text = content or ""
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[-1]
    text = re.sub(r"<think>.*", "", text, flags=re.S)
    return text.strip()


@dataclass
class Completion:
    content: str = ""
    calls: list[dict] = field(default_factory=list)
    input_tokens: int | None = None
    output_tokens: int | None = None


class OpenAICompatibleLLM:
    def __init__(self, settings):
        self.settings = settings
        self.client = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key.get_secret_value() or "not-configured",
            max_retries=0,
            timeout=45,
        )

    async def complete(self, messages, tools, parameters):
        if not self.settings.llm_api_key.get_secret_value():
            raise ServiceError("LLM_KEY_MISSING", 503)
        try:
            result = await self.client.chat.completions.create(
                **parameters,
                messages=messages,
                tools=tools or None,
                response_format={"type": "json_object"},
                extra_body={
                    "reasoning": {"enabled": self.settings.llm_reasoning, "exclude": True},
                    "chat_template_kwargs": {"enable_thinking": self.settings.llm_reasoning},
                },
            )
        except APIStatusError as exc:
            code = {
                401: "LLM_UNAUTHORIZED",
                404: "LLM_MODEL_UNAVAILABLE",
                429: "LLM_RATE_LIMITED",
            }.get(exc.status_code, "LLM_PROVIDER_ERROR")
            raise ServiceError(code, 503) from None
        except (APIConnectionError, APITimeoutError):
            raise ServiceError("LLM_TIMEOUT_OR_CONNECTION", 503) from None
        if not result.choices or result.choices[0].finish_reason == "length":
            raise ServiceError("LLM_INCOMPLETE_RESPONSE", 502)
        msg = result.choices[0].message
        calls = [
            {
                "id": c.id,
                "type": "function",
                "function": {"name": c.function.name, "arguments": c.function.arguments},
            }
            for c in msg.tool_calls or []
        ]
        # Never retain model_extra/reasoning_content/reasoning_details.
        return Completion(
            public_content(msg.content),
            calls,
            result.usage.prompt_tokens if result.usage else None,
            result.usage.completion_tokens if result.usage else None,
        )

    async def close(self):
        await self.client.close()


def wire_json(value):
    return json.dumps(value, ensure_ascii=False, default=str)
