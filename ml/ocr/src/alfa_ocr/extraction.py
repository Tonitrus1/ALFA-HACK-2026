"""Bounded LLM contexts, with conservative merging of evidence-backed fields."""

import json

from .llm import complete, system_prompt
from .models import ServiceError


def context_size(settings, contract, pages):
    return (
        len(system_prompt(settings, contract, pages))
        + len(json.dumps([p.model_dump() for p in pages], ensure_ascii=False))
    )


def chunks(settings, contract, pages):
    batch = []
    limit = settings.max_context_chars - (
        min(24000, settings.max_context_chars // 4) if settings.llm_validation_retries else 0
    )
    for page in pages:
        # Extract each document independently so a model cannot silently prefer a
        # later report over an earlier one. Cross-document conflicts are merged here.
        if batch and batch[-1].document_id != page.document_id:
            yield batch
            batch = []
        # A dense page can be split at block boundaries; original source IDs survive.
        for block in page.blocks:
            if batch and batch[-1].document_id == page.document_id and batch[-1].page == page.page:
                candidate = [
                    *batch[:-1],
                    batch[-1].model_copy(update={"blocks": [*batch[-1].blocks, block]}),
                ]
            else:
                candidate = [*batch, page.model_copy(update={"blocks": [block]})]
            if context_size(settings, contract, candidate) > limit:
                if not batch:
                    raise ServiceError("LLM_CONTEXT_LIMIT", 413)
                yield batch
                batch = [page.model_copy(update={"blocks": [block]})]
                if context_size(settings, contract, batch) > limit:
                    raise ServiceError("LLM_CONTEXT_LIMIT", 413)
            else:
                batch = candidate
        if not page.blocks:
            candidate = [*batch, page]
            if context_size(settings, contract, candidate) > limit:
                if batch:
                    yield batch
                batch = [page]
            else:
                batch = candidate
    if batch:
        yield batch


def merge_fields(fields):
    values = {}
    confidence = []
    for field in fields:
        candidates = (
            field["candidates"]
            if field["status"] == "conflict"
            else (
                [{"value": field["value"], "sources": field["sources"]}]
                if field["status"] == "extracted"
                else []
            )
        )
        if field["confidence"] is not None:
            confidence.append(field["confidence"])
        for candidate in candidates:
            sources = values.setdefault(candidate["value"], {})
            for source in candidate["sources"]:
                sources[json.dumps(source, sort_keys=True)] = source
    if not values:
        return {
            "status": "missing",
            "value": None,
            "confidence": None,
            "sources": [],
            "candidates": [],
        }
    if len(values) == 1:
        value, sources = next(iter(values.items()))
        return {
            "status": "extracted",
            "value": value,
            "confidence": min(confidence) if confidence else 0,
            "sources": list(sources.values()),
            "candidates": [],
        }
    return {
        "status": "conflict",
        "value": None,
        "confidence": None,
        "sources": [],
        "candidates": [
            {"value": value, "sources": list(sources.values())} for value, sources in values.items()
        ],
    }


def merge(nodes, key=None):
    first = nodes[0]
    if isinstance(first, dict):
        if {"status", "value", "confidence", "sources", "candidates"}.issubset(first):
            return merge_fields(nodes)
        return {name: merge([n[name] for n in nodes], name) for name in first}
    if key == "documents":
        types = {}
        for node in nodes:
            for document in node:
                types.setdefault(document["document_id"], set()).add(document["document_type"])
        return [
            {
                "document_id": identifier,
                "document_type": next(iter(kinds)) if len(kinds) == 1 else "other",
            }
            for identifier, kinds in types.items()
        ]
    if key == "extensions":
        fields = {}
        for node in nodes:
            for extension in node:
                fields.setdefault(extension["key"], []).append(extension["field"])
        return [{"key": name, "field": merge_fields(values)} for name, values in fields.items()]
    if any(node != first for node in nodes):
        raise ServiceError("LLM_MERGE_STRUCTURE_CONFLICT")
    return first


def extract(settings, contract, pages, active=lambda: True):
    outputs, calls = [], []
    for batch in chunks(settings, contract, pages):
        feedback, previous = None, None
        for attempt in range(settings.llm_validation_retries + 1):
            if not active():
                raise ServiceError("JOB_CANCELLED")
            if len(calls) >= settings.max_llm_calls:
                raise ServiceError("LLM_CALL_LIMIT")
            value, metadata = complete(
                settings, contract, batch, feedback=feedback, previous=previous
            )
            calls.append(metadata)
            try:
                contract.validate(value, batch)
                break
            except ServiceError as error:
                if attempt >= settings.llm_validation_retries:
                    raise
                feedback = (
                    "Исправь предыдущий JSON по исходному OCR и JSON Schema. Верни полный объект, без Markdown. Не выдумывай значения или цитаты. Ошибки (только правила схемы): "
                    + json.dumps(getattr(error, "diagnostics", [error.code]), ensure_ascii=False)
                )
                previous = value
        outputs.append(value)
    value = merge(outputs)
    contract.validate(value, pages)
    usage = {
        key: sum(call["usage"][key] for call in calls)
        if all(call["usage"].get(key) is not None for call in calls)
        else None
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
    }
    return value, {
        "model": settings.llm_model,
        "calls": len(calls),
        "validation_repairs": len(calls) - len(outputs),
        "usage": usage,
        "merge": "conservative lexical equality; differing candidates become conflicts",
    }
