import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import (
    JSON,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.orm import Session as DBSession

from .errors import ServiceError


def utcnow():
    return datetime.now(UTC).isoformat()


class Base(DeclarativeBase):
    pass


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    created_at: Mapped[str] = mapped_column(String)


class KnowledgeVersion(Base):
    __tablename__ = "knowledge_versions"
    __table_args__ = (UniqueConstraint("document_id", "version"),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("knowledge_documents.id"))
    version: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String)
    text: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String, index=True)
    original_path: Mapped[str] = mapped_column(String)
    attributes: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String)
    published_at: Mapped[str | None] = mapped_column(String, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("knowledge_versions.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str | None] = mapped_column(String, nullable=True)
    ordinal: Mapped[int] = mapped_column(Integer)


class WebCandidate(Base):
    __tablename__ = "web_candidates"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, index=True)
    title: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(String)
    text: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String)
    retrieved_at: Mapped[str] = mapped_column(String)
    state: Mapped[str] = mapped_column(String)
    knowledge_ref: Mapped[dict | None] = mapped_column(JSON, nullable=True)


def version_dict(v):
    return {
        "id": v.id,
        "document_id": v.document_id,
        "version": v.version,
        "state": v.state,
        "text": v.text,
        "sha256": v.sha256,
        "metadata": v.attributes,
        "created_at": v.created_at,
        "published_at": v.published_at,
        "error_code": v.error_code,
    }


class SQLiteKnowledgeRepository:
    def __init__(self, url: str, data_dir: Path):
        self.data_dir = data_dir
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "originals").mkdir(exist_ok=True)
        self.engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})

    def import_version(self, raw, metadata, text, chunks, document_id=None):
        digest = hashlib.sha256(raw).hexdigest()
        with DBSession(self.engine) as db:
            if document_id and not db.get(KnowledgeDocument, document_id):
                raise ServiceError("DOCUMENT_NOT_FOUND", 404)
            previous = (
                list(
                    db.scalars(
                        select(KnowledgeVersion).where(KnowledgeVersion.document_id == document_id)
                    )
                )
                if document_id
                else []
            )
            matches = list(
                db.scalars(select(KnowledgeVersion).where(KnowledgeVersion.sha256 == digest))
            )
            for v in matches:
                if not document_id or v.document_id == document_id:
                    return version_dict(v)
            if not document_id:
                document_id = str(uuid4())
                db.add(KnowledgeDocument(id=document_id, created_at=utcnow()))
                db.flush()
            vid = str(uuid4())
            path = self.data_dir / "originals" / vid
            path.write_bytes(raw)
            v = KnowledgeVersion(
                id=vid,
                document_id=document_id,
                version=max((p.version for p in previous), default=0) + 1,
                state="DRAFT",
                text=text,
                sha256=digest,
                original_path=str(path),
                attributes=metadata,
                created_at=utcnow(),
            )
            db.add(v)
            db.flush()
            for i, c in enumerate(chunks):
                db.add(KnowledgeChunk(id=str(uuid4()), version_id=vid, ordinal=i, **c))
            db.commit()
            return version_dict(v)

    def versions(self):
        with DBSession(self.engine) as db:
            return [version_dict(v) for v in db.scalars(select(KnowledgeVersion))]

    def version(self, document_id, version):
        with DBSession(self.engine) as db:
            v = db.scalar(
                select(KnowledgeVersion).where(
                    KnowledgeVersion.document_id == document_id, KnowledgeVersion.version == version
                )
            )
            if not v:
                raise ServiceError("VERSION_NOT_FOUND", 404)
            return version_dict(v)

    def set_state(self, vid, state, error=None):
        with DBSession(self.engine) as db:
            v = db.get(KnowledgeVersion, vid)
            if state == "PUBLISHED":
                for old in db.scalars(
                    select(KnowledgeVersion).where(
                        KnowledgeVersion.document_id == v.document_id,
                        KnowledgeVersion.state == "PUBLISHED",
                        KnowledgeVersion.id != vid,
                    )
                ):
                    old.state = "REVOKED"
                v.published_at = utcnow()
            v.state, v.error_code = state, error
            db.commit()

    def chunks(self, version_ids):
        if not version_ids:
            return []
        with DBSession(self.engine) as db:
            rows = db.scalars(
                select(KnowledgeChunk)
                .where(KnowledgeChunk.version_id.in_(version_ids))
                .order_by(KnowledgeChunk.ordinal)
            )
            return [
                {
                    "id": c.id,
                    "version_id": c.version_id,
                    "text": c.text,
                    "page": c.page,
                    "section": c.section,
                }
                for c in rows
            ]

    def active_versions(self):
        now = datetime.now(UTC)
        return [
            v
            for v in self.versions()
            if v["state"] == "PUBLISHED"
            and (
                not v["metadata"].get("effective_until")
                or datetime.fromisoformat(v["metadata"]["effective_until"]) > now
            )
        ]

    def active_chunks(self):
        versions = {v["id"]: v for v in self.active_versions()}
        return [
            {
                **c,
                "document_id": versions[c["version_id"]]["document_id"],
                "version": versions[c["version_id"]]["version"],
                "metadata": versions[c["version_id"]]["metadata"],
            }
            for c in self.chunks(list(versions))
        ]

    def candidate_create(self, session_id, title, url, text):
        with DBSession(self.engine) as db:
            c = WebCandidate(
                id=str(uuid4()),
                session_id=session_id,
                title=title,
                url=url,
                text=text,
                sha256=hashlib.sha256(text.encode()).hexdigest(),
                retrieved_at=utcnow(),
                state="PENDING",
            )
            db.add(c)
            db.commit()
            return self._candidate(c)

    @staticmethod
    def _candidate(c):
        return {
            k: getattr(c, k)
            for k in (
                "id",
                "session_id",
                "title",
                "url",
                "text",
                "sha256",
                "retrieved_at",
                "state",
                "knowledge_ref",
            )
        }

    def candidate(self, cid):
        with DBSession(self.engine) as db:
            c = db.get(WebCandidate, cid)
            if not c:
                raise ServiceError("CANDIDATE_NOT_FOUND", 404)
            return self._candidate(c)

    def candidate_state(self, cid, state, ref=None):
        with DBSession(self.engine) as db:
            c = db.get(WebCandidate, cid)
            c.state, c.knowledge_ref = state, ref
            db.commit()

    def cleanup_candidates(self, session_id=None):
        with DBSession(self.engine) as db:
            query = select(WebCandidate).where(WebCandidate.state != "CONFIRMED")
            if session_id:
                query = query.where(WebCandidate.session_id == session_id)
            for c in db.scalars(query):
                db.delete(c)
            db.commit()
