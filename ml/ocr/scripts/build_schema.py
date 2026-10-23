"""Generate the editable default contract; pipeline only loads the resulting JSON."""

import json
from pathlib import Path


def obj(properties, **extra):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
        **extra,
    }


def build():
    string = {"type": "string", "minLength": 1}
    source = obj(
        {
            "document_id": string,
            "page": {"type": "integer", "minimum": 1},
            "block_id": string,
            "quote": string,
        }
    )
    candidate = obj(
        {
            "value": string,
            "sources": {"type": "array", "items": {"$ref": "#/$defs/source"}, "minItems": 1},
        }
    )
    field = obj(
        {
            "status": {"enum": ["missing", "extracted", "conflict"]},
            "value": {"type": ["string", "null"]},
            "confidence": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
            "sources": {"type": "array", "items": {"$ref": "#/$defs/source"}},
            "candidates": {"type": "array", "items": {"$ref": "#/$defs/candidate"}},
        }
    )
    field["allOf"] = [
        {
            "if": {"properties": {"status": {"const": "missing"}}},
            "then": {
                "properties": {
                    "value": {"type": "null"},
                    "confidence": {"type": "null"},
                    "sources": {"maxItems": 0},
                    "candidates": {"maxItems": 0},
                }
            },
        },
        {
            "if": {"properties": {"status": {"const": "extracted"}}},
            "then": {
                "properties": {
                    "value": string,
                    "confidence": {"type": "number"},
                    "sources": {"minItems": 1},
                    "candidates": {"maxItems": 0},
                }
            },
        },
        {
            "if": {"properties": {"status": {"const": "conflict"}}},
            "then": {
                "properties": {
                    "value": {"type": "null"},
                    "confidence": {"type": "null"},
                    "sources": {"maxItems": 0},
                    "candidates": {"minItems": 2},
                }
            },
        },
    ]

    def typed(pattern):
        return {
            "allOf": [
                {"$ref": "#/$defs/field"},
                {
                    "properties": {
                        "value": {"type": ["string", "null"], "pattern": pattern},
                        "candidates": {"items": {"properties": {"value": {"pattern": pattern}}}},
                    }
                },
            ]
        }

    def ref(name="field"):
        return {"$ref": f"#/$defs/{name}"}

    schema = obj(
        {
            "schema_version": {"const": "1.0"},
            "documents": {
                "type": "array",
                "minItems": 1,
                "items": obj(
                    {
                        "document_id": string,
                        "document_type": {
                            "enum": [
                                "passport",
                                "inn",
                                "snils",
                                "bank_statement",
                                "financial",
                                "other",
                            ]
                        },
                    }
                ),
            },
            "person": obj(
                {
                    "full_name": ref(),
                    "birth_date": ref("date"),
                    "inn": ref("inn12"),
                    "snils": ref("snils"),
                    "passport_series": ref("series"),
                    "passport_number": ref("number"),
                }
            ),
            "organization": obj(
                {"name": ref(), "inn": ref("inn10"), "kpp": ref("kpp"), "ogrn": ref("ogrn")}
            ),
            "financial": obj(
                {
                    **{
                        key: ref("decimal")
                        for key in [
                            "revenue",
                            "net_profit",
                            "ebit",
                            "equity",
                            "total_assets",
                            "current_assets",
                            "current_liabilities",
                            "total_debt",
                        ]
                    },
                    "period": ref("period"),
                    "currency": ref("currency"),
                }
            ),
            "extensions": {"type": "array", "items": obj({"key": string, "field": ref()})},
        }
    )
    schema.update(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "urn:alfa:ocr:extraction:1.0",
            "title": "Credit document extraction (unconfirmed)",
            "$defs": {
                "source": source,
                "candidate": candidate,
                "field": field,
                "date": typed(r"^\d{4}-\d{2}-\d{2}$"),
                "decimal": typed(r"^-?\d+(\.\d{1,2})?$"),
                "inn12": typed(r"^\d{12}$"),
                "inn10": typed(r"^\d{10}$"),
                "snils": typed(r"^\d{11}$"),
                "series": typed(r"^\d{4}$"),
                "number": typed(r"^\d{6}$"),
                "kpp": typed(r"^\d{9}$"),
                "ogrn": typed(r"^\d{13}$"),
                "currency": typed(r"^[A-Z]{3}$"),
                "period": typed(
                    r"^([0-9]{4}|[0-9]{4}-[0-9]{2}-[0-9]{2}/[0-9]{4}-[0-9]{2}-[0-9]{2})$"
                ),
            },
        }
    )
    schema["$defs"]["date"]["allOf"][1]["properties"]["value"]["format"] = "date"
    schema["$defs"]["date"]["allOf"][1]["properties"]["candidates"]["items"]["properties"]["value"][
        "format"
    ] = "date"
    return schema


if __name__ == "__main__":
    target = Path(__file__).resolve().parents[1] / "schemas/extraction.schema.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
