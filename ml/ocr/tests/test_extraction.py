from alfa_ocr.config import Settings
from alfa_ocr.contract import Contract
from alfa_ocr.extraction import chunks, merge_fields
from alfa_ocr.models import Block, Page, ServiceError


def field(value, doc="doc"):
    return {
        "status": "extracted",
        "value": value,
        "confidence": 0.8,
        "sources": [{"document_id": doc, "page": 1, "block_id": "b1", "quote": value}],
        "candidates": [],
    }


def test_merge_conflicts_does_not_pick_winner():
    result = merge_fields([field("100"), field("200"), field("100", "doc2")])
    assert result["status"] == "conflict"
    assert result["value"] is None
    assert {candidate["value"] for candidate in result["candidates"]} == {"100", "200"}
    assert len(result["candidates"][0]["sources"]) == 2


def test_missing_does_not_erase_evidence():
    missing = {
        "status": "missing",
        "value": None,
        "confidence": None,
        "sources": [],
        "candidates": [],
    }
    assert merge_fields([missing, field("000001")])["value"] == "000001"


def test_different_documents_are_extracted_independently():
    first = Page(
        document_id="one",
        page=1,
        width=10,
        height=10,
        blocks=[Block(block_id="b1", text="first", confidence=1, bbox=[0, 0, 10, 10])],
    )
    second = first.model_copy(update={"document_id": "two"})
    batches = list(chunks(Settings(), Contract("test", {}), [first, second]))
    assert len(batches) == 2
    assert [{p.document_id for p in batch} for batch in batches] == [{"one"}, {"two"}]


def test_dense_page_chunks_keep_original_block_ids():
    page = Page(
        document_id="doc",
        page=1,
        width=100,
        height=100,
        blocks=[
            Block(block_id=f"b{i}", text="a" * 400, bbox=[0, 0, 10, 10], confidence=0.9)
            for i in range(10)
        ],
    )
    batches = list(chunks(Settings(max_context_chars=1000), Contract("test", {}), [page]))
    assert len(batches) > 1
    assert [b.block_id for batch in batches for p in batch for b in p.blocks] == [
        f"b{i}" for i in range(10)
    ]


def test_validation_repair_is_bounded_and_counted(monkeypatch):
    from alfa_ocr.extraction import extract

    class TestContract:
        prompt = "test"
        schema = {}

        def validate(self, value, pages):
            if value["valid"] is False:
                raise ServiceError("LLM_SCHEMA_INVALID")

    calls = []

    def completion(*args, **kwargs):
        calls.append(kwargs)
        return {"valid": len(calls) == 2}, {
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}
        }

    monkeypatch.setattr("alfa_ocr.extraction.complete", completion)
    page = Page(
        document_id="doc",
        page=1,
        width=10,
        height=10,
        blocks=[Block(block_id="b1", text="unit only", confidence=1, bbox=[0, 0, 10, 10])],
    )
    value, metadata = extract(Settings(), TestContract(), [page])
    assert value == {"valid": True}
    assert len(calls) == 2
    assert calls[1]["previous"] == {"valid": False}
    assert metadata["validation_repairs"] == 1
    assert metadata["usage"]["total_tokens"] == 4
