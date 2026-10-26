"""Backend context is a trusted, read-only per-company snapshot, never a client override."""

import pytest
from pydantic import ValidationError

from alfa_assistant.bank import BackendContextGateway
from alfa_assistant.errors import ServiceError
from alfa_assistant.schemas import DocumentsArgs


def test_document_overview_preserves_product_names_and_separate_requirements():
    bank = BackendContextGateway(
        {
            "company_id": "company-a",
            "products": [
                {
                    "id": "working-capital",
                    "name": "Оборотный кредит",
                    "documents": [{"title": "Отчётность"}],
                },
                {
                    "id": "equipment",
                    "name": "Кредит на оборудование",
                    "documents": [{"title": "Договор поставки"}],
                },
            ],
            "applications": [],
        }
    )
    overview = bank.documents(DocumentsArgs(), "company-a")
    assert overview["provenance"]["type"] == "BACKEND_SNAPSHOT"
    assert overview["products"] == bank.data["products"]
    assert "documents" not in overview  # Requirements must not become one mandatory list.
    selected = bank.documents(DocumentsArgs(product_id="equipment"), "company-a")
    assert selected["documents"] == [{"title": "Договор поставки"}]


@pytest.mark.parametrize(
    "args",
    [
        {"product_id": "credit", "application_id": "app"},
        {"product_id": " "},
        {"application_id": ""},
    ],
)
def test_document_lookup_rejects_ambiguous_or_blank_selectors(args):
    with pytest.raises(ValidationError):
        DocumentsArgs(**args)


def test_generic_application_question_can_use_backend_documents_without_an_id(client, llm, settings):
    import json

    from conftest import call

    from alfa_assistant.llm import Completion

    settings.context_tokens = 4096
    settings.rag_tokens = 768
    settings.compact_tool_sources = True
    settings.llm_json_with_tools = False
    created = client.post(
        "/v1/sessions",
        headers={"X-Admin-Key": "test-admin"},
        json={
            "identity": {"actor_id": "real-user", "company_id": "company-a"},
        },
    ).json()
    llm.replies.append(Completion(calls=[call("get_required_documents")]))

    def answer(messages):
        system = messages[0]["content"]
        assert '"id": "working-capital"' in system
        assert "Оборотный кредит" in system
        assert "не проси их" in system
        assert "demo-app" not in system
        documents = json.loads(next(m["content"] for m in messages if m["role"] == "tool"))
        assert documents["provenance"]["type"] == "BACKEND_SNAPSHOT"
        assert documents["products"][0]["documents"] == [{"title": "Отчётность"}]
        assert len(documents["products"]) == 1
        return Completion(
            json.dumps(
                {
                    "status": "ANSWER",
                    "answer": "Для оборотного кредита подготовьте отчётность.",
                    "citation_ids": [],
                }
            )
        )

    llm.replies.append(answer)
    response = client.post(
        f"/v1/sessions/{created['session_id']}/messages",
        headers={
            "X-Admin-Key": "test-admin",
            "Authorization": "Bearer " + created["session_token"],
        },
        json={
            "client_message_id": "application-checklist",
            "message": "Что нужно для подачи заявки?",
            "bank_context": {
                "company_id": "company-a",
                "applications": [],
                "products": [
                    {
                        "id": "working-capital",
                        "name": "Оборотный кредит",
                        "documents": [{"title": "Отчётность"}],
                    }
                ],
            },
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ANSWER"
    assert "отчётность" in response.json()["answer"]


async def test_product_catalogue_context_is_bounded_and_uses_only_the_backend(settings, kb):
    import json

    from alfa_assistant.agent import Agent
    from alfa_assistant.sessions import MemorySessionStore

    async def run_sync(fn):
        return fn()

    session, _ = MemorySessionStore().create("user", "company-a", "prompt", {})
    session.bank_context = {
        "company_id": "company-a",
        "applications": [],
        "products": [
            {"id": f"real-{i}", "name": "Реальный продукт " + str(i)} for i in range(1000)
        ],
    }
    agent = Agent(settings, None, kb, None, None, None, run_sync)
    text = await agent.catalogue_context(session)
    products = json.loads(text.splitlines()[2])
    assert 0 < len(products) < 1000
    assert kb.encoder.count(json.dumps(products, ensure_ascii=False)) <= 256
    assert all(p["id"].startswith("real-") for p in products)


def test_backend_snapshot_has_no_synthetic_applications():
    bank = BackendContextGateway(
        {
            "company_id": "company-a",
            "products": [{"id": "credit", "documents": [{"title": "Отчётность"}]}],
            "applications": [
                {
                    "id": "real-app",
                    "company_id": "company-a",
                    "product_id": "credit",
                    "status": "REVIEW",
                }
            ],
        }
    )
    assert bank.application("real-app", "company-a")["provenance"]["type"] == "BACKEND_SNAPSHOT"
    assert bank.documents(DocumentsArgs(application_id="real-app"), "company-a")["documents"]
    for app, company in [("real-app", "company-b"), ("demo-app-1", "company-a")]:
        with pytest.raises(ServiceError):
            bank.application(app, company)


def test_backend_identity_and_snapshot_require_admin(client):
    identity = {"actor_id": "real-user", "company_id": "company-a"}
    assert client.post("/v1/sessions", json={"identity": identity}).status_code == 403
    response = client.post(
        "/v1/sessions", json={"identity": identity}, headers={"X-Admin-Key": "test-admin"}
    )
    assert response.status_code == 201
    s = response.json()
    headers = {"Authorization": "Bearer " + s["session_token"]}
    url = "/v1/sessions/" + s["session_id"] + "/messages"
    assert (
        client.post(
            url, json={"client_message_id": "m1", "message": "Статус"}, headers=headers
        ).status_code
        == 403
    )
    payload = {
        "client_message_id": "m1",
        "message": "Статус",
        "bank_context": {"company_id": "company-a", "products": [], "applications": []},
    }
    assert client.post(url, json=payload, headers=headers).status_code == 403
    payload["bank_context"]["company_id"] = "company-b"
    assert (
        client.post(url, json=payload, headers={**headers, "X-Admin-Key": "test-admin"}).status_code
        == 403
    )


def test_cited_source_and_history_recheck_publication(client, app, kb, meta):
    source = kb.ingest("Проверяемый текст источника".encode(), "source.txt", meta)
    kb.publish(source["document_id"], source["version"])
    created = client.post("/v1/sessions", json={}).json()
    sid = created["session_id"]
    headers = {"Authorization": "Bearer " + created["session_token"]}
    citation = {
        "type": "KNOWLEDGE",
        "document_id": source["document_id"],
        "version": source["version"],
        "version_id": source["id"],
    }
    app.state.sessions.sessions[sid].completed["test"] = {
        "text": "Вопрос",
        "response": {"answer": "Text relying on revoked source", "citations": [citation]},
    }
    url = f"/v1/sessions/{sid}/sources/{source['document_id']}/{source['version']}"
    assert client.get(url).status_code == 404
    assert client.get(url, headers=headers).json()["text"] == "Проверяемый текст источника"
    kb.revoke(source["document_id"], source["version"])
    assert client.get(url, headers=headers).status_code == 404
    transcript = client.get(f"/v1/sessions/{sid}/messages", headers=headers).json()
    assert "Text relying" not in str(transcript)


def test_seed_creates_missing_documents_and_is_idempotent_without_reviving_revoked(kb):
    from pathlib import Path

    from alfa_assistant.cli import seed_corpus

    corpus = Path(__file__).resolve().parents[1] / "corpus"
    seed_corpus(kb, corpus)
    versions = kb.repo.versions()
    assert len(versions) == 17
    assert all(v["state"] == "PUBLISHED" for v in versions)
    first = versions[0]
    kb.revoke(first["document_id"], first["version"])
    seed_corpus(kb, corpus)
    assert len(kb.repo.versions()) == 17
    assert kb.repo.version(first["document_id"], first["version"])["state"] == "REVOKED"
