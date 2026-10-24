import argparse
import asyncio
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from .config import Settings


def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def prepare(settings):
    from huggingface_hub import snapshot_download

    settings.model_dir.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        settings.embedding_model,
        revision=settings.embedding_revision,
        local_dir=settings.model_dir / "embedding",
        allow_patterns=["*.json", "*.txt", "*.safetensors", "*.model", "1_Pooling/*"],
    )
    snapshot_download(
        settings.tokenizer_model,
        revision=settings.tokenizer_revision,
        local_dir=settings.model_dir / "tokenizer",
        allow_patterns=["tokenizer*", "vocab.json", "merges.txt", "config.json"],
    )
    checksums = {}
    for folder in ("embedding", "tokenizer"):
        for path in (settings.model_dir / folder).rglob("*"):
            if path.is_file() and ".cache" not in path.parts:
                with path.open("rb") as stream:
                    checksums[str(path.relative_to(settings.model_dir)).replace("\\", "/")] = (
                        hashlib.file_digest(stream, "sha256").hexdigest()
                    )
    dump(
        settings.model_dir / "manifest.json",
        {
            "embedding_model": settings.embedding_model,
            "embedding_revision": settings.embedding_revision,
            "tokenizer_model": settings.tokenizer_model,
            "tokenizer_revision": settings.tokenizer_revision,
            "prepared_at": datetime.now(UTC).isoformat(),
            "sha256": checksums,
        },
    )
    print("Models prepared; runtime is local-only. Manifest:", settings.model_dir / "manifest.json")


def service(settings):
    from .rag import KnowledgeService, LocalModels, QdrantVectorIndex
    from .storage import SQLiteKnowledgeRepository

    return KnowledgeService(
        SQLiteKnowledgeRepository(settings.database_url, settings.data_dir),
        QdrantVectorIndex(settings.qdrant_url, settings.qdrant_collection),
        LocalModels(settings),
        settings,
    )


async def smoke(settings):
    from .agent import TOOLS
    from .llm import OpenAICompatibleLLM

    if not settings.llm_api_key.get_secret_value():
        print("SKIPPED: LLM_API_KEY missing")
        return
    client = OpenAICompatibleLLM(settings)
    parameters = {"model": settings.llm_model, "temperature": 0, "max_tokens": 128}
    try:
        first = await client.complete(
            [{"role": "user", "content": 'Верни JSON {"answer":"Привет"}'}], [], parameters
        )
        second = await client.complete(
            [{"role": "user", "content": "Покажи кредитные продукты"}],
            TOOLS,
            parameters
            | {"tool_choice": {"type": "function", "function": {"name": "list_credit_products"}}},
        )
        ok = bool(first.content) and any(
            c["function"]["name"] == "list_credit_products" for c in second.calls
        )
        report = {
            "passed": ok,
            "model": settings.llm_model,
            "requests": 2,
            "checked_at": datetime.now(UTC).isoformat(),
            "input_tokens": [first.input_tokens, second.input_tokens],
            "output_tokens": [first.output_tokens, second.output_tokens],
        }
        dump(Path("reports/llm-smoke.json"), report)
        print(json.dumps(report))
        if not ok:
            raise SystemExit(1)
    finally:
        await client.close()


def calibrate(settings):
    """Choose threshold on labeled development queries only; preserve every observed score."""
    kb = service(settings)
    rows = json.loads(Path("evaluation/rag-questions.json").read_text(encoding="utf-8"))
    chunks = kb.repo.active_chunks()
    if not chunks:
        raise SystemExit("Seed the corpus first")
    vectors = kb.encoder.encode([c["text"] for c in chunks])
    observations = []
    for row in rows:
        if row.get("follow_up"):
            continue
        query = kb.encoder.encode([row["question"]], query=True)[0]
        scored = sorted(
            [
                (sum(x * y for x, y in zip(query, vector, strict=True)), c)
                for c, vector in zip(chunks, vectors, strict=True)
            ],
            key=lambda s: s[0],
            reverse=True,
        )
        top = scored[0]
        observations.append(
            {
                "question": row["question"],
                "expected": row["expected"],
                "score": top[0],
                "title": top[1]["metadata"]["title"],
                "relevant": row["expected"] in top[1]["metadata"]["title"]
                if row["expected"]
                else False,
            }
        )
    # Penalize admitting no-answer queries twice as strongly as rejecting relevant ones.
    candidates = sorted({r["score"] for r in observations} | {1.0})
    threshold = min(
        candidates,
        key=lambda t: (
            sum(
                (2 if not r["expected"] else 1)
                for r in observations
                if (r["score"] >= t) != r["relevant"]
            ),
            -t,
        ),
    )
    dump(
        Path("reports/dense-calibration.json"),
        {
            "experimental": True,
            "threshold": threshold,
            "embedding_revision": settings.embedding_revision,
            "observations": observations,
            "note": "Development set; no held-out quality claim",
        },
    )
    print("Set DENSE_MIN_SCORE=" + str(threshold))


def seed_corpus(kb, corpus=Path("corpus")):
    """Repository deduplicates raw hashes; only it allocates document identities."""
    manifest = json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))
    for doc in manifest["documents"]:
        path = corpus / doc["path"]
        version = kb.ingest(path.read_bytes(), path.name, doc["metadata"])
        if version["state"] != "REVOKED":
            kb.publish(version["document_id"], version["version"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=["prepare-models", "reindex", "seed", "smoke-llm", "export-openapi", "calibrate"],
    )
    args = parser.parse_args()
    settings = Settings()
    if args.command == "prepare-models":
        prepare(settings)
    elif args.command == "smoke-llm":
        asyncio.run(smoke(settings))
    elif args.command == "export-openapi":
        from .api import create_app

        dump(Path("openapi.json"), create_app(settings).openapi())
    elif args.command == "calibrate":
        calibrate(settings)
    else:
        kb = service(settings)
        if args.command == "seed":
            seed_corpus(kb)
            print("Corpus published")
        kb.reconcile()
        print("Index rebuilt from SQLite")
