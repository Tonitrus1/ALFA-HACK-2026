import hashlib
import json
from dataclasses import dataclass
from itertools import islice

from jsonschema import Draft202012Validator, FormatChecker

from .models import ServiceError


@dataclass
class Contract:
    prompt: str
    schema: dict

    @classmethod
    def read(cls, settings):
        prompt = settings.prompt_path.read_text(encoding="utf-8")
        schema = json.loads(settings.schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)

        # Forbid remote references: validation must not fetch external content.
        def refs(node):
            if isinstance(node, dict):
                for key in ("$ref", "$dynamicRef", "$recursiveRef"):
                    if key in node and not node[key].startswith("#/"):
                        raise ValueError("REMOTE_SCHEMA_REF_FORBIDDEN")
                for value in node.values():
                    refs(value)
            elif isinstance(node, list):
                for value in node:
                    refs(value)

        refs(schema)
        return cls(prompt, schema)

    def fingerprint(self):
        return {
            "prompt_sha256": hashlib.sha256(self.prompt.encode()).hexdigest(),
            "schema_sha256": hashlib.sha256(
                json.dumps(self.schema, sort_keys=True).encode()
            ).hexdigest(),
        }

    def validate(self, value, pages):
        errors = list(
            islice(
                Draft202012Validator(self.schema, format_checker=FormatChecker()).iter_errors(
                    value
                ),
                10,
            )
        )
        if errors:
            failure = ServiceError("LLM_SCHEMA_INVALID")
            # Schema paths/keywords only, never validation messages containing values.
            failure.diagnostics = [
                str(e.validator) + ":" + "/".join(map(str, e.absolute_schema_path))
                for e in errors[:10]
            ]
            raise failure
        lookup = {(p.document_id, p.page, b.block_id): b.text for p in pages for b in p.blocks}
        expected = {p.document_id for p in pages}
        ids = [d["document_id"] for d in value["documents"]]
        if len(ids) != len(expected) or set(ids) != expected:
            raise ServiceError("LLM_DOCUMENTS_INVALID")

        def visit(node):
            if isinstance(node, dict):
                if {"document_id", "page", "block_id", "quote"}.issubset(node):
                    text = lookup.get((node["document_id"], node["page"], node["block_id"]))
                    if text is None or not node["quote"].strip() or node["quote"] not in text:
                        raise ServiceError("LLM_SOURCE_INVALID")
                if node.get("status") == "conflict":
                    if len({c["value"] for c in node["candidates"]}) < 2:
                        raise ServiceError("LLM_CONFLICT_INVALID")
                for child in node.values():
                    visit(child)
            elif isinstance(node, list):
                for child in node:
                    visit(child)

        visit(value)
