import json

import pytest
from conftest import open_session, send

from alfa_assistant.llm import Completion
from alfa_assistant.schemas import Metadata


@pytest.mark.parametrize("dense_min_score", [None, 0])
def test_synthetic_documents_never_enter_answers(kb, meta, settings, dense_min_score):
    settings.dense_min_score = dense_min_score
    demo = kb.ingest(
        "Статус DOCUMENTS_REQUIRED. СИНТЕТИЧЕСКИЙ ДЕМОНСТРАЦИОННЫЙ МАТЕРИАЛ.".encode(),
        "demo.md",
        Metadata(title="Статус DOCUMENTS_REQUIRED", attribution="Тест", allowed_use="Тест")
        .model_dump(mode="json"),
    )
    kb.publish(demo["document_id"], 1)
    assert kb.repo.active_versions()  # Still available to administrators.
    assert kb.search("DOCUMENTS_REQUIRED") == []
    assert kb.filter_sources([
        {"type": "KNOWLEDGE", "version_id": demo["id"]},
        {"type": "WEB", "url": "https://cbr.ru/develop/msp/"},
    ]) == [{"type": "WEB", "url": "https://cbr.ru/develop/msp/"}]

    public = kb.ingest("Документы для малого бизнеса.".encode(), "public.md", meta)
    kb.publish(public["document_id"], 1)
    results = kb.search("Документы DOCUMENTS_REQUIRED")
    assert results and {s["version_id"] for s in results} == {public["id"]}


def test_old_synthetic_answer_hidden_in_history_replay_source_and_llm(client, app, kb, llm):
    sid, auth = open_session(client)
    result = send(client, sid, auth, "Документы").json()
    demo = kb.ingest(
        b"INTERNAL_DEMO_CONTENT",
        "demo.md",
        Metadata(title="Статус DOCUMENTS_REQUIRED", attribution="Тест", allowed_use="Тест")
        .model_dump(mode="json"),
    )
    kb.publish(demo["document_id"], 1)
    session = app.state.sessions.sessions[sid]
    result.update(answer="INTERNAL_DEMO_CONTENT", citations=[{
        "id": "old-demo", "type": "KNOWLEDGE", "title": demo["metadata"]["title"],
        "document_id": demo["document_id"], "version_id": demo["id"], "version": 1,
        "metadata": demo["metadata"],
    }])
    session.completed["one"]["response"] = result
    session.turns = [[
        {"role": "user", "content": "Документы"},
        {"role": "assistant", "content": "INTERNAL_DEMO_CONTENT"},
    ]]
    session.turn_versions = [{demo["id"]}]

    base = f"/v1/sessions/{sid}"
    assert client.get(f"{base}/sources/{demo['document_id']}/1", headers=auth).status_code == 404
    history = client.get(f"{base}/messages", headers=auth).json()
    assert "INTERNAL_DEMO_CONTENT" not in json.dumps(history)
    replay = send(client, sid, auth, "Документы").json()
    assert replay["status"] == "INSUFFICIENT_EVIDENCE"
    assert replay["citations"] == [] and "INTERNAL_DEMO_CONTENT" not in replay["answer"]

    llm.replies.append(Completion('{"answer":"Уточните продукт."}'))
    assert send(client, sid, auth, "Какие документы?", "two").status_code == 200
    assert "INTERNAL_DEMO_CONTENT" not in json.dumps(llm.requests[-1])
