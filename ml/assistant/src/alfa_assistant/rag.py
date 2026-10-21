import hashlib
import io
import json
import logging
import math
import re
import threading
from collections import defaultdict
from datetime import UTC, datetime

import trafilatura
from pypdf import PdfReader
from qdrant_client import QdrantClient, models
from rank_bm25 import BM25Okapi

from .errors import ServiceError

log = logging.getLogger(__name__)
STOPWORDS = set(
    "и а но или в во на по из от до с со к ко у о об для при за без над под не ни это как что какой какая какие какое ли бы же уже ещё его её их он она они мы вы я ты то этого этой есть будет нужно нужен нужны".split()
)


def terms(text):
    return [word for word in re.findall(r"\w+", text.lower()) if word not in STOPWORDS]


class LocalModels:
    def __init__(self, settings):
        from sentence_transformers import SentenceTransformer
        from transformers import AutoTokenizer

        manifest = json.loads((settings.model_dir / "manifest.json").read_text())
        for relative, expected in manifest["sha256"].items():
            path = settings.model_dir / relative
            if not path.resolve().is_relative_to(settings.model_dir.resolve()):
                raise ServiceError("MODEL_CHECKSUM_MISMATCH", 503)
            with path.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != expected:
                    raise ServiceError("MODEL_CHECKSUM_MISMATCH", 503)
        if (
            manifest["embedding_model"] != settings.embedding_model
            or (
                settings.embedding_revision
                and manifest["embedding_revision"] != settings.embedding_revision
            )
            or manifest["tokenizer_model"] != settings.tokenizer_model
            or (manifest["tokenizer_revision"] != settings.tokenizer_revision)
        ):
            raise ServiceError("MODEL_MANIFEST_MISMATCH", 503)
        self.encoder = SentenceTransformer(
            str(settings.model_dir / "embedding"), device="cpu", local_files_only=True
        )
        self.tokenizer = AutoTokenizer.from_pretrained(
            settings.model_dir / "tokenizer", local_files_only=True
        )
        self.chunk_tokenizer = self.encoder.tokenizer

    def encode(self, texts, query=False):
        prefix = "query: " if query else "passage: "
        return self.encoder.encode(
            [prefix + t for t in texts], normalize_embeddings=True, show_progress_bar=False
        ).tolist()

    def count(self, text):
        return len(self.tokenizer.encode(text, add_special_tokens=False))

    def count_messages(self, messages, tools):
        return len(
            self.tokenizer.apply_chat_template(
                messages,
                tools=tools,
                tokenize=True,
                add_generation_prompt=True,
                enable_thinking=False,
            )
        )


class QdrantVectorIndex:
    def __init__(self, url, collection):
        self.client = QdrantClient(url=url, timeout=10)
        self.collection = collection

    def ensure(self):
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                self.collection,
                vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE),
            )

    def reset(self):
        if self.client.collection_exists(self.collection):
            self.client.delete_collection(self.collection)
        self.ensure()

    def upsert(self, chunks, vectors):
        self.ensure()
        for start in range(0, len(chunks), 64):
            self.client.upsert(
                self.collection,
                points=[
                    models.PointStruct(
                        id=c["id"], vector=v, payload={"version_id": c["version_id"]}
                    )
                    for c, v in zip(
                        chunks[start : start + 64], vectors[start : start + 64], strict=True
                    )
                ],
                wait=True,
            )

    def search(self, vector, active_ids):
        if not active_ids:
            return []
        result = self.client.query_points(
            self.collection,
            query=vector,
            limit=10,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(key="version_id", match=models.MatchAny(any=active_ids))
                ]
            ),
        )
        return [(str(p.id), p.score) for p in result.points]


def extract(raw, filename):
    suffix = filename.lower().rsplit(".", 1)[-1]
    if len(raw) > 10 * 1024 * 1024:
        raise ServiceError("FILE_TOO_LARGE", 413)
    if suffix not in {"txt", "md", "html", "htm", "pdf"}:
        raise ServiceError("UNSUPPORTED_FILE_TYPE", 415)
    try:
        if suffix == "pdf":
            if not raw.startswith(b"%PDF-"):
                raise ServiceError("INVALID_PDF", 422)
            reader = PdfReader(io.BytesIO(raw))
            if reader.is_encrypted:
                raise ServiceError("ENCRYPTED_PDF_UNSUPPORTED", 422)
            pages = [(i + 1, p.extract_text() or "") for i, p in enumerate(reader.pages)]
        else:
            text = raw.decode("utf-8-sig")
            if "\x00" in text:
                raise ValueError("binary")
            if suffix in {"html", "htm"}:
                text = trafilatura.extract(text, include_comments=False, include_tables=True) or ""
            pages = [(None, text)]
    except ServiceError:
        raise
    except Exception:
        raise ServiceError("DOCUMENT_PARSE_FAILED", 422) from None
    if not any(t.strip() for _, t in pages):
        raise ServiceError("EMPTY_TEXT_OR_OCR_REQUIRED", 422)
    return pages


def chunk_pages(pages, tokenizer):
    chunks = []
    for page, text in pages:
        section = None
        buffer = []
        for paragraph in re.split(r"\n\s*\n", text):
            if paragraph.lstrip().startswith("#"):
                if buffer:
                    chunks.append(
                        {"text": tokenizer.decode(buffer), "page": page, "section": section}
                    )
                    buffer = []
                section = paragraph.splitlines()[0].lstrip("# ")[:200]
            ids = tokenizer.encode(paragraph.strip(), add_special_tokens=False)
            if not ids:
                continue
            if len(buffer) + len(ids) > 350 and buffer:
                chunks.append({"text": tokenizer.decode(buffer), "page": page, "section": section})
                buffer = buffer[-50:]
            buffer.extend(ids)
            while len(buffer) > 350:
                chunks.append(
                    {"text": tokenizer.decode(buffer[:350]), "page": page, "section": section}
                )
                buffer = buffer[300:]
        if buffer:
            chunks.append({"text": tokenizer.decode(buffer), "page": page, "section": section})
    return chunks


class KnowledgeService:
    def __init__(self, repository, index, encoder, settings):
        self.repo, self.index, self.encoder, self.settings = repository, index, encoder, settings
        self.lock = threading.RLock()
        self.ready = False

    def reconcile(self):
        with self.lock:
            self.ready = False
            self.index.reset()
            chunks = self.repo.active_chunks()
            if chunks:
                self.index.upsert(chunks, self.encoder.encode([c["text"] for c in chunks]))
            self.ready = True

    def ingest(self, raw, filename, metadata, document_id=None):
        pages = extract(raw, filename)
        chunks = chunk_pages(pages, self.encoder.chunk_tokenizer)
        with self.lock:
            return self.repo.import_version(
                raw, metadata, "\n\n".join(t for _, t in pages), chunks, document_id
            )

    def publish(self, document_id, version):
        with self.lock:
            v = self.repo.version(document_id, version)
            if v["state"] == "PUBLISHED":
                return v
            if any(
                other["document_id"] == document_id
                and other["version"] > version
                and other["published_at"]
                for other in self.repo.versions()
            ):
                raise ServiceError("VERSION_SUPERSEDED", 409)
            expires = v["metadata"].get("effective_until")
            if expires and datetime.fromisoformat(expires) <= datetime.now(UTC):
                raise ServiceError("VERSION_EXPIRED", 409)
            chunks = self.repo.chunks([v["id"]])
            try:
                self.index.upsert(chunks, self.encoder.encode([c["text"] for c in chunks]))
            except Exception:
                self.repo.set_state(v["id"], "FAILED", "INDEX_UNAVAILABLE")
                raise ServiceError("INDEX_UNAVAILABLE", 503) from None
            self.repo.set_state(v["id"], "PUBLISHED")
            log.info("knowledge_publish", extra={"version_id": v["id"]})
            return self.repo.version(document_id, version)

    def revoke(self, document_id, version):
        with self.lock:
            v = self.repo.version(document_id, version)
            self.repo.set_state(v["id"], "REVOKED")
            log.info("knowledge_revoke", extra={"version_id": v["id"]})
            return self.repo.version(document_id, version)

    def filter_sources(self, sources):
        with self.lock:
            active = {v["id"] for v in self.repo.active_versions()}
            return [s for s in sources if s["type"] != "KNOWLEDGE" or s["version_id"] in active]

    def search(self, query):
        with self.lock:
            chunks = self.repo.active_chunks()
            if not chunks:
                return []
            by_id = {c["id"]: c for c in chunks}
            dense = []
            if self.settings.dense_min_score is not None:
                dense = [
                    (cid, score)
                    for cid, score in self.index.search(
                        self.encoder.encode([query], query=True)[0],
                        list({c["version_id"] for c in chunks}),
                    )
                    if cid in by_id and score >= self.settings.dense_min_score
                ]
            tokenized = [terms(c["text"]) for c in chunks]
            scores = [0.0] * len(chunks)
            if any(tokenized) and terms(query):
                bm25 = BM25Okapi(tokenized)
                # Positive RSJ IDF (Lucene variant) also supports a one-document corpus.
                for term in bm25.idf:
                    frequency = sum(term in doc for doc in bm25.doc_freqs)
                    bm25.idf[term] = math.log1p((len(chunks) - frequency + 0.5) / (frequency + 0.5))
                scores = bm25.get_scores(terms(query))
            lexical = [
                (chunks[i]["id"], float(scores[i]))
                for i in sorted(range(len(chunks)), key=lambda i: scores[i], reverse=True)
                if scores[i] > 0
            ][:10]
            fused = defaultdict(float)
            for branch in (dense, lexical):
                for rank, (cid, _) in enumerate(branch, 1):
                    fused[cid] += 1 / (60 + rank)
            result, budget = [], 0
            for cid in sorted(fused, key=fused.get, reverse=True):
                c = by_id[cid]
                cost = self.encoder.count(c["text"])
                if budget + cost > self.settings.rag_tokens:
                    continue
                result.append(
                    {
                        "id": cid,
                        "type": "KNOWLEDGE",
                        "title": c["metadata"]["title"],
                        "document_id": c["document_id"],
                        "version_id": c["version_id"],
                        "version": c["version"],
                        "text": c["text"],
                        "page": c["page"],
                        "section": c["section"],
                        "metadata": c["metadata"],
                        "rrf_score": fused[cid],
                        "dense_score": dict(dense).get(cid),
                        "bm25_score": dict(lexical).get(cid),
                    }
                )
                budget += cost
                if len(result) == 5:
                    break
            return result
