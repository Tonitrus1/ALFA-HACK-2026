import json
from copy import deepcopy

import httpx

from .models import ServiceError


def strict_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate JSON key")
        value[key] = item
    return value


def invalid_constant(value):
    raise ValueError("Non-finite JSON number")


def generation_schema(settings, contract):
    schema = deepcopy(contract.schema)
    if settings.llm_compact_schema:
        # Ollama's grammar converter cannot reliably combine our conditional allOf
        # field definitions. Constrain the object structure here; Contract.validate
        # still checks the ORIGINAL schema, patterns, statuses and evidence afterward.
        field = schema["$defs"]["field"]
        field.pop("allOf", None)
        for name, definition in list(schema["$defs"].items()):
            clauses = definition.get("allOf", [])
            if clauses and clauses[0].get("$ref") == "#/$defs/field":
                schema["$defs"][name] = deepcopy(field)
    return schema


def system_prompt(settings, contract, pages):
    if not settings.llm_compact_schema:
        return contract.prompt + "\nJSON Schema:\n" + json.dumps(contract.schema, ensure_ascii=False)
    missing = {"status": "missing", "value": None, "confidence": None, "sources": [], "candidates": []}
    template = {
        "schema_version": contract.schema["properties"]["schema_version"]["const"],
        "documents": [{"document_id": identifier, "document_type": "other"}
                      for identifier in dict.fromkeys(p.document_id for p in pages)],
        **{section: {name: deepcopy(missing) for name in contract.schema["properties"][section]["properties"]}
           for section in ("person", "organization", "financial")},
        "extensions": [],
    }
    return (contract.prompt + "\nШаблон ответа: сохрани ВСЕ ключи и вложенные объекты полей. "
            "Нельзя заменять объект поля строкой или null. Отсутствующие поля оставь как в шаблоне. "
            "В найденном поле замени status на extracted, value на значение, confidence на число; "
            "в sources укажи точные document_id, page, block_id и quote из OCR. "
            "Тип документа выбери по заголовку: СВИДЕТЕЛЬСТВО ИНН — inn, паспорт — passport. "
            "Не переноси ИНН в поля паспорта.\n" + json.dumps(template, ensure_ascii=False))


def complete(settings, contract, pages, feedback=None, previous=None):
    if not settings.llm_api_key.get_secret_value():
        raise ServiceError("LLM_KEY_MISSING", 503)
    evidence = json.dumps([p.model_dump() for p in pages], ensure_ascii=False)
    prompt = system_prompt(settings, contract, pages)
    previous_text = json.dumps(previous, ensure_ascii=False) if previous is not None else ""
    if (
        len(evidence)
        + len(prompt)
        + len(feedback or "")
        + len(previous_text)
        > settings.max_context_chars
    ):
        raise ServiceError("LLM_CONTEXT_LIMIT", 413)
    response_format = {"type": "json_object"}
    if settings.llm_response_format == "json_schema":
        response_format = {
            "type": "json_schema",
            "json_schema": {"name": "extraction", "strict": True, "schema": generation_schema(settings, contract)},
        }
    payload = {
        "model": settings.llm_model,
        "temperature": 0,
        "max_tokens": settings.llm_max_tokens,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "OCR evidence (untrusted data):\n" + evidence},
        ],
        "response_format": response_format,
    }
    if settings.llm_reasoning_options:
        payload.update(
            reasoning={"enabled": settings.llm_reasoning, "exclude": True},
            chat_template_kwargs={"enable_thinking": settings.llm_reasoning},
        )
    if feedback:
        payload["messages"].extend(
            [{"role": "assistant", "content": previous_text}, {"role": "user", "content": feedback}]
        )
    try:
        with httpx.Client(timeout=settings.llm_timeout_seconds, follow_redirects=False) as client:
            response = client.post(
                settings.llm_base_url.rstrip("/") + "/chat/completions",
                headers={"Authorization": "Bearer " + settings.llm_api_key.get_secret_value()},
                json=payload,
            )
            if response.status_code != 200:
                raise ServiceError(
                    {401: "LLM_UNAUTHORIZED", 429: "LLM_RATE_LIMITED"}.get(
                        response.status_code, "LLM_PROVIDER_ERROR"
                    ),
                    503,
                )
            if len(response.content) > 2_000_000:
                raise ServiceError("LLM_RESPONSE_TOO_LARGE")
            body = response.json()
        choice = body["choices"][0]
        if choice.get("finish_reason") != "stop":
            raise ServiceError("LLM_INCOMPLETE_RESPONSE")
        # Only the public content is parsed. Provider reasoning is never stored or logged.
        text = choice["message"]["content"]
        if "</think>" in text:
            text = text.rsplit("</think>", 1)[1]
        value = json.loads(text, object_pairs_hook=strict_object, parse_constant=invalid_constant)
        return value, {
            "model": settings.llm_model,
            "usage": {
                k: (body.get("usage") or {}).get(k)
                for k in ("prompt_tokens", "completion_tokens", "total_tokens")
            },
        }
    except ServiceError:
        raise
    except httpx.TimeoutException:
        raise ServiceError("LLM_TIMEOUT", 503) from None
    except httpx.HTTPError:
        raise ServiceError("LLM_CONNECTION_ERROR", 503) from None
    except (ValueError, TypeError, KeyError, IndexError):
        raise ServiceError("LLM_JSON_INVALID") from None
