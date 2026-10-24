"""Backend context is a trusted, read-only per-company snapshot, never a client override."""

import pytest

from alfa_assistant.bank import BackendContextGateway
from alfa_assistant.errors import ServiceError
from alfa_assistant.schemas import DocumentsArgs


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
