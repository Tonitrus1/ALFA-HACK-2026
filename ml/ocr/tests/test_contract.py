import copy
import json
from pathlib import Path

import pytest

from alfa_ocr.contract import Contract
from alfa_ocr.models import Block, Page, ServiceError

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def contract():
    return Contract("test", json.loads((ROOT / "schemas/extraction.schema.json").read_text()))


@pytest.fixture
def missing():
    return {"status": "missing", "value": None, "confidence": None, "sources": [], "candidates": []}


@pytest.fixture
def value(missing):
    return {
        "schema_version": "1.0",
        "documents": [{"document_id": "doc", "document_type": "other"}],
        **{
            name: {key: copy.deepcopy(missing) for key in keys}
            for name, keys in {
                "person": [
                    "full_name",
                    "birth_date",
                    "inn",
                    "snils",
                    "passport_series",
                    "passport_number",
                ],
                "organization": ["name", "inn", "kpp", "ogrn"],
                "financial": [
                    "revenue",
                    "net_profit",
                    "ebit",
                    "equity",
                    "total_assets",
                    "current_assets",
                    "current_liabilities",
                    "total_debt",
                    "period",
                    "currency",
                ],
            }.items()
        },
        "extensions": [],
    }


@pytest.fixture
def pages():
    return [
        Page(
            document_id="doc",
            page=1,
            width=100,
            height=100,
            blocks=[
                Block(block_id="b1", text="ИНН 000000000001", confidence=0.9, bbox=[0, 0, 50, 10])
            ],
        )
    ]


def test_all_missing_valid(contract, value, pages):
    contract.validate(value, pages)


@pytest.mark.parametrize(
    "mutation,code",
    [
        (lambda v: v.update(schema_version="2"), "LLM_SCHEMA_INVALID"),
        (lambda v: v["person"].pop("inn"), "LLM_SCHEMA_INVALID"),
        (lambda v: v["documents"][0].update(document_id="fake"), "LLM_DOCUMENTS_INVALID"),
        (lambda v: v["documents"].append(v["documents"][0]), "LLM_DOCUMENTS_INVALID"),
    ],
)
def test_invalid_contract(contract, value, pages, mutation, code):
    mutation(value)
    with pytest.raises(ServiceError) as error:
        contract.validate(value, pages)
    assert error.value.code == code


@pytest.mark.parametrize(
    "bad",
    [
        {"document_id": "fake"},
        {"page": 2},
        {"block_id": "missing"},
        {"quote": "invented"},
        {"quote": " "},
    ],
)
def test_source_binding(contract, value, pages, bad):
    source = {"document_id": "doc", "page": 1, "block_id": "b1", "quote": "000000000001", **bad}
    value["person"]["inn"] = {
        "status": "extracted",
        "value": "000000000001",
        "confidence": 0.9,
        "sources": [source],
        "candidates": [],
    }
    with pytest.raises(ServiceError, match="LLM_SOURCE_INVALID"):
        contract.validate(value, pages)


def test_found_without_source_rejected(contract, value, pages):
    value["person"]["inn"].update(status="extracted", value="000000000001", confidence=0.9)
    with pytest.raises(ServiceError, match="LLM_SCHEMA_INVALID"):
        contract.validate(value, pages)


def test_duplicate_conflict_rejected(contract, value, pages):
    candidate = {
        "value": "000000000001",
        "sources": [{"document_id": "doc", "page": 1, "block_id": "b1", "quote": "000000000001"}],
    }
    value["person"]["inn"].update(status="conflict", candidates=[candidate, candidate])
    with pytest.raises(ServiceError, match="LLM_CONFLICT_INVALID"):
        contract.validate(value, pages)


def test_leading_zeros_and_strict_numbers(contract, value, pages):
    field = {
        "status": "extracted",
        "value": "000000000001",
        "confidence": 0.9,
        "sources": [{"document_id": "doc", "page": 1, "block_id": "b1", "quote": "000000000001"}],
        "candidates": [],
    }
    value["person"]["inn"] = field
    contract.validate(value, pages)
    field["value"] = 1
    with pytest.raises(ServiceError, match="LLM_SCHEMA_INVALID"):
        contract.validate(value, pages)
