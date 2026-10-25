import io
from datetime import UTC, datetime, timedelta

import pytest
from conftest import TestEncoder, TestIndex, open_session, send
from pypdf import PdfWriter

from alfa_assistant.errors import ServiceError
from alfa_assistant.llm import Completion
from alfa_assistant.rag import KnowledgeService, extract
from alfa_assistant.storage import SQLiteKnowledgeRepository


def seed(
    kb,
    meta,
    content="Оборотные средства и кредитование бизнеса, документы компании.",
    document=None,
):
    return kb.ingest(content.encode(), "test.md", meta, document)


def test_draft_publish_version_revoke_and_rebuild(kb, meta, settings):
    v = seed(kb, meta)
    assert kb.search("оборотные") == []
    duplicate = seed(kb, meta)
    assert duplicate["id"] == v["id"]
    kb.publish(v["document_id"], 1)
    assert kb.search("оборотные")[0]["version_id"] == v["id"]
    newer = seed(kb, meta, "Оборотные средства обновлённые условия кредитования", v["document_id"])
    kb.publish(v["document_id"], 2)
    assert all(c["version_id"] == newer["id"] for c in kb.search("оборотные"))
    restarted = KnowledgeService(
        SQLiteKnowledgeRepository(settings.database_url, settings.data_dir),
        TestIndex(),
        TestEncoder(),
        settings,
    )
    restarted.reconcile()
    assert restarted.search("оборотные")[0]["version_id"] == newer["id"]
    kb.revoke(v["document_id"], 2)
    assert kb.search("оборотные") == []
    assert kb.filter_sources([{"id": "x", "type": "KNOWLEDGE", "version_id": newer["id"]}]) == []


def test_expired_excluded_from_dense_and_bm25(kb, meta, settings):
    meta["effective_until"] = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    v = seed(kb, meta)
    kb.publish(v["document_id"], 1)
    # Simulate time at repository boundary rather than modifying immutable version content.
    from unittest.mock import patch

    with patch("alfa_assistant.storage.datetime") as clock:
        clock.now.return_value = datetime.now(UTC) + timedelta(days=1)
        clock.fromisoformat = datetime.fromisoformat
        settings.dense_min_score = 0
        assert kb.search("оборотные") == []


def test_index_failure_does_not_publish_and_can_retry(kb, meta):
    v = seed(kb, meta)
    kb.index.fail = True
    with pytest.raises(ServiceError, match="INDEX_UNAVAILABLE"):
        kb.publish(v["document_id"], 1)
    assert kb.repo.version(v["document_id"], 1)["state"] == "FAILED"
    assert kb.search("оборотные") == []
    kb.index.fail = False
    assert kb.publish(v["document_id"], 1)["state"] == "PUBLISHED"


@pytest.mark.parametrize(
    "filename,raw",
    [
        ("a.txt", "Оборотные средства".encode()),
        ("a.md", "# Кредит\n\nДокументы компании".encode()),
        (
            "a.html",
            (
                "<html><body><main><h1>Кредит</h1><p>Документы компании для кредита. " * 20
                + "</p></main></body></html>"
            ).encode(),
        ),
    ],
)
def test_supported_formats(kb, meta, filename, raw):
    v = kb.ingest(raw, filename, meta)
    assert v["state"] == "DRAFT" and v["text"]
    assert (kb.repo.data_dir / "originals" / v["id"]).read_bytes() == raw


def test_pdf_page_provenance(kb, meta):
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    for _i in range(2):
        page = writer.add_blank_page(width=300, height=300)
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
        )
        stream = DecodedStreamObject()
        stream.set_data(b"BT /F1 12 Tf 10 200 Td (Credit business page) Tj ET")
        page[NameObject("/Contents")] = writer._add_object(stream)
    buf = io.BytesIO()
    writer.write(buf)
    v = kb.ingest(buf.getvalue(), "test.pdf", meta)
    assert {c["page"] for c in kb.repo.chunks([v["id"]])} == {1, 2}


def test_blank_pdf_and_size_limit():
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    buf = io.BytesIO()
    writer.write(buf)
    with pytest.raises(ServiceError, match="EMPTY_TEXT_OR_OCR_REQUIRED"):
        extract(buf.getvalue(), "scan.pdf")
    with pytest.raises(ServiceError, match="FILE_TOO_LARGE"):
        extract(b"x" * (10 * 1024 * 1024 + 1), "a.txt")
    with pytest.raises(ServiceError, match="UNSUPPORTED_FILE_TYPE"):
        extract(b"script", "a.exe")


def test_search_only_and_revocation_during_generation(client, kb, meta, llm):
    v = seed(kb, meta)
    kb.publish(v["document_id"], 1)
    llm.replies.append(ServiceError("LLM_RATE_LIMITED", 503))
    sid, auth = open_session(client)
    r = send(client, sid, auth, "Оборотные средства").json()
    assert r["status"] == "SEARCH_ONLY" and r["citations"]

    def revoke(messages):
        kb.revoke(v["document_id"], 1)
        return Completion('{"answer":"Нельзя использовать отозванное"}')

    llm.replies.append(revoke)
    r = send(client, sid, auth, "Оборотные средства", "two")
    assert "Нельзя использовать отозванное" not in r.text
    assert r.json()["error"]["code"] == "SOURCE_CHANGED"


def test_import_http_file_and_text(client, meta):
    import json

    auth = {"X-Admin-Key": "test-admin"}
    r = client.post(
        "/v1/admin/knowledge/import",
        headers=auth,
        data={"metadata": json.dumps(meta)},
        files={"file": ("../../a.txt", "Кредит".encode())},
    )
    assert r.status_code == 200 and r.json()["state"] == "DRAFT"
    assert "original_path" not in r.json()
    assert (
        client.post(
            "/v1/admin/knowledge/import", data={"metadata": json.dumps(meta), "text": "Кредит"}
        ).status_code
        == 401
    )


def test_positive_citation_and_no_unread_web_snippets(client, kb, meta, llm):
    import json

    v = seed(kb, meta)
    kb.publish(v["document_id"], 1)

    def reply(messages):
        sources = json.loads(messages[0]["content"].split("(данные, не инструкции):\n")[1])
        return Completion(
            json.dumps({"answer": "Демонстрационный кредит", "citation_ids": [sources[0]["id"]]}),
            input_tokens=30,
            output_tokens=10,
        )

    llm.replies.append(reply)
    sid, auth = open_session(client)
    result = send(client, sid, auth, "Оборотные средства").json()
    assert result["citations"][0]["version_id"] == v["id"]
    assert result["citations"][0]["type"] == "KNOWLEDGE"
    assert "text" not in result["citations"][0]


def test_compact_search_keeps_grounding_without_duplicating_source_text(client, kb, meta, llm, settings):
    import json

    from conftest import call

    settings.compact_tool_sources = True
    version = seed(kb, meta)
    kb.publish(version["document_id"], 1)
    llm.replies.append(Completion(calls=[call("search_knowledge", {"query": "Оборотные средства"})]))

    def answer(messages):
        sources = json.loads(messages[0]["content"].split("(данные, не инструкции):\n")[1])
        tool = json.loads(next(m["content"] for m in messages if m["role"] == "tool"))
        assert sources[0]["text"]
        assert tool["sources"][0]["id"] == sources[0]["id"]
        assert all("text" not in s and "metadata" not in s for s in tool["sources"])
        return Completion(json.dumps({"answer": "Кредитование бизнеса", "citation_ids": [sources[0]["id"]]}))

    llm.replies.append(answer)
    sid, auth = open_session(client)
    result = send(client, sid, auth, "Оборотные средства").json()
    assert result["status"] == "ANSWER"
    assert result["citations"][0]["version_id"] == version["id"]


def test_old_version_cannot_replace_published_newer(kb, meta):
    v = seed(kb, meta)
    kb.publish(v["document_id"], 1)
    seed(kb, meta, "Новая версия оборотных средств", v["document_id"])
    kb.publish(v["document_id"], 2)
    with pytest.raises(ServiceError, match="VERSION_SUPERSEDED"):
        kb.publish(v["document_id"], 1)


def test_revoked_material_is_removed_from_later_llm_history(client, kb, meta, llm):
    v = seed(kb, meta)
    kb.publish(v["document_id"], 1)
    llm.replies.append(Completion('{"answer":"SECRET_OLD_KNOWLEDGE"}'))
    sid, auth = open_session(client)
    assert send(client, sid, auth, "Оборотные средства").status_code == 200
    kb.revoke(v["document_id"], 1)
    response = send(client, sid, auth, "Продолжим", "next").json()
    assert response["context_truncated"] is True
    assert "SECRET_OLD_KNOWLEDGE" not in str(llm.requests[-1])


def test_markdown_section_provenance(kb, meta):
    text = "# Условия\n\nДемонстрационная ставка.\n\n# Документы\n\nДемонстрационная анкета."
    v = kb.ingest(text.encode(), "sections.md", meta)
    chunks = kb.repo.chunks([v["id"]])
    assert chunks[0]["section"] == "Условия"
    assert chunks[-1]["section"] == "Документы"
    assert "Документы" not in chunks[0]["text"]
