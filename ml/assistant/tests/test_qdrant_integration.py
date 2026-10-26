import os
from uuid import uuid4

import pytest

from alfa_assistant.rag import QdrantVectorIndex


@pytest.mark.integration
def test_real_qdrant_upsert_filter_rebuild():
    url = os.environ.get("TEST_QDRANT_URL")
    if not url:
        pytest.skip("Set TEST_QDRANT_URL for a real Qdrant integration test")
    index = QdrantVectorIndex(url, "test_" + uuid4().hex)
    try:
        index.ensure()
        a, b = str(uuid4()), str(uuid4())
        index.upsert(
            [{"id": a, "version_id": "published"}, {"id": b, "version_id": "revoked"}],
            [[1.0] + [0.0] * 383, [1.0] + [0.0] * 383],
        )
        assert [cid for cid, _ in index.search([1.0] + [0.0] * 383, ["published"])] == [a]
        assert index.search([1.0] + [0.0] * 383, []) == []
        index.reset()
        assert index.search([1.0] + [0.0] * 383, ["published"]) == []
    finally:
        if index.client.collection_exists(index.collection):
            index.client.delete_collection(index.collection)


@pytest.mark.integration
def test_real_e5_hybrid_versions_and_recovery(settings, meta):
    url = os.environ.get("TEST_QDRANT_URL")
    if not url or not os.environ.get("TEST_E5"):
        pytest.skip("Set TEST_QDRANT_URL and TEST_E5=1; run prepare-models first")
    from alfa_assistant.rag import KnowledgeService, LocalModels
    from alfa_assistant.storage import Base, SQLiteKnowledgeRepository

    settings.dense_min_score = 0.7
    index = QdrantVectorIndex(url, "test_e5_" + uuid4().hex)
    repo = SQLiteKnowledgeRepository(settings.database_url, settings.data_dir)
    Base.metadata.create_all(repo.engine)
    encoder = LocalModels(settings)
    kb = KnowledgeService(repo, index, encoder, settings)
    try:
        kb.reconcile()
        v = kb.ingest(
            "Кредит на пополнение оборотных средств. Ставка синтетическая.".encode(), "a.txt", meta
        )
        assert kb.search("оборотные средства") == []
        kb.publish(v["document_id"], 1)
        found = kb.search("оборотных средств")
        assert found and found[0]["dense_score"] is not None and found[0]["bm25_score"] > 0
        newer = kb.ingest(
            "Кредит на оборотные средства. Новые синтетические условия.".encode(),
            "a.txt",
            meta,
            v["document_id"],
        )
        kb.publish(v["document_id"], 2)
        assert {r["version_id"] for r in kb.search("оборотные средства")} == {newer["id"]}
        recovered = KnowledgeService(repo, index, encoder, settings)
        recovered.reconcile()
        assert recovered.search("оборотные средства")[0]["version_id"] == newer["id"]
        kb.revoke(v["document_id"], 2)
        assert kb.search("оборотные средства") == []
    finally:
        if index.client.collection_exists(index.collection):
            index.client.delete_collection(index.collection)
