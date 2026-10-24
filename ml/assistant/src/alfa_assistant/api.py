import asyncio
import logging
import secrets
import time
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from uuid import uuid4

import anyio
from fastapi import Depends, FastAPI, File, Form, Header, Query, Request, UploadFile
from fastapi.responses import JSONResponse

from .agent import Agent
from .bank import SyntheticBankGateway
from .config import Settings
from .errors import ServiceError
from .llm import OpenAICompatibleLLM
from .observability import setup_logging
from .rag import KnowledgeService, LocalModels, QdrantVectorIndex
from .schemas import ChatResponse, ConfirmCandidate, CreateSession, Metadata, NewMessage
from .sessions import MemorySessionStore
from .storage import SQLiteKnowledgeRepository
from .web import SafePageReader, SearxngSearch, URLPolicy

log = logging.getLogger(__name__)


class BodyLimitMiddleware:
    def __init__(self, app, maximum=11 * 1024 * 1024):
        self.app, self.maximum = app, maximum

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH"}:
            return await self.app(scope, receive, send)
        body = bytearray()
        while True:
            part = await receive()
            if part["type"] == "http.disconnect":
                return
            body.extend(part.get("body", b""))
            if len(body) > self.maximum:
                response = JSONResponse({"error": {"code": "REQUEST_TOO_LARGE"}}, status_code=413)
                return await response(scope, receive, send)
            if not part.get("more_body", False):
                break
        consumed = False

        async def replay():
            nonlocal consumed
            if not consumed:
                consumed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        return await self.app(scope, replay, send)


def create_app(settings=None, *, knowledge=None, llm=None, web_search=None, reader=None):
    cfg = settings or Settings()
    sessions = MemorySessionStore(cfg.session_ttl_seconds, cfg.max_sessions)
    limiter = anyio.CapacityLimiter(cfg.thread_workers)

    async def run_sync(fn):
        return await anyio.to_thread.run_sync(fn, limiter=limiter, abandon_on_cancel=True)

    bank = SyntheticBankGateway(Path("fixtures/bank.json"))

    @asynccontextmanager
    async def lifespan(app):
        nonlocal knowledge, llm, web_search, reader
        setup_logging()
        if not cfg.admin_api_key.get_secret_value():
            raise RuntimeError("ADMIN_API_KEY is required")
        if knowledge is None:
            repo = SQLiteKnowledgeRepository(cfg.database_url, cfg.data_dir)
            try:
                encoder = await run_sync(lambda: LocalModels(cfg))
                knowledge = KnowledgeService(
                    repo, QdrantVectorIndex(cfg.qdrant_url, cfg.qdrant_collection), encoder, cfg
                )
            except Exception:
                app.state.startup_error = "MODELS_NOT_PREPARED"
        if knowledge is not None:
            try:
                await run_sync(knowledge.reconcile)
                await run_sync(knowledge.repo.cleanup_candidates)
            except Exception:
                app.state.startup_error = "KNOWLEDGE_RECONCILIATION_FAILED"
        llm = llm or OpenAICompatibleLLM(cfg)
        policy = URLPolicy(cfg.web_allowed_domains)
        web_search = web_search or SearxngSearch(cfg.searxng_url, policy)
        reader = reader or SafePageReader(policy, run_sync)
        app.state.agent = Agent(cfg, llm, knowledge, bank, web_search, reader, run_sync)
        app.state.knowledge = knowledge

        async def expire():
            while True:
                await asyncio.sleep(30)
                await cleanup()

        task = asyncio.create_task(expire())
        yield
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        if hasattr(llm, "close"):
            await llm.close()
        if knowledge:
            knowledge.repo.engine.dispose()

    app = FastAPI(
        title="ALFA Assistant (development)",
        version="0.1.0",
        lifespan=lifespan,
        description="External paid LLM development mode. Synthetic bank, no credit decisions.",
    )
    app.add_middleware(BodyLimitMiddleware)
    app.state.sessions = sessions
    app.state.startup_error = None

    async def cleanup():
        expired = sessions.expired_ids()
        for sid in expired:
            del sessions.sessions[sid]
        for sid in expired:
            if knowledge:

                def remove(sid=sid):
                    with knowledge.lock:
                        knowledge.repo.cleanup_candidates(sid)

                await run_sync(remove)

    @app.middleware("http")
    async def request_id(request, call_next):
        request.state.request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.exception_handler(ServiceError)
    async def service_error(request, exc):
        return JSONResponse(
            {"error": {"code": exc.code}, "request_id": request.state.request_id},
            status_code=exc.status,
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        log.error(
            "request_error",
            extra={"request_id": request.state.request_id, "error_code": "INTERNAL_ERROR"},
        )
        return JSONResponse(
            {"error": {"code": "INTERNAL_ERROR"}, "request_id": request.state.request_id},
            status_code=500,
        )

    def is_admin(key):
        expected = cfg.admin_api_key.get_secret_value()
        return bool(expected and key and secrets.compare_digest(key.encode(), expected.encode()))

    def admin(x_admin_key: str | None = Header(None)):
        if not is_admin(x_admin_key):
            raise ServiceError("ADMIN_UNAUTHORIZED", 401)

    def session_auth(sid: str, authorization: str | None):
        token = (
            authorization.removeprefix("Bearer ")
            if authorization and authorization.startswith("Bearer ")
            else ""
        )
        return sessions.get(sid, token), token

    def kb():
        if knowledge is None or not knowledge.ready:
            raise ServiceError("KNOWLEDGE_NOT_READY", 503)
        return knowledge

    @app.get("/health/live")
    async def live():
        return {"status": "live"}

    @app.get("/health/ready")
    async def ready():
        dependencies = {
            "knowledge": bool(knowledge and knowledge.ready),
            "llm_key_configured": bool(cfg.llm_api_key.get_secret_value()),
            "searxng": False,
            "qdrant": False,
        }
        import httpx

        async with httpx.AsyncClient(timeout=2, trust_env=False) as client:

            async def check(url):
                try:
                    return (await client.get(url)).is_success
                except httpx.HTTPError:
                    return False

            dependencies["searxng"], dependencies["qdrant"] = await asyncio.gather(
                check(cfg.searxng_url + "/healthz"), check(cfg.qdrant_url + "/readyz")
            )
        ok = all(dependencies.values())
        return JSONResponse(
            {
                "status": "ready" if ok else "not_ready",
                "dependencies": dependencies,
                "startup_error": app.state.startup_error,
            },
            status_code=200 if ok else 503,
        )

    @app.post("/v1/sessions", status_code=201)
    async def new_session(body: CreateSession, x_admin_key: str | None = Header(None)):
        await cleanup()
        if (
            body.demo_user_id is not None
            or body.system_prompt is not None
            or body.identity is not None
        ) and not is_admin(x_admin_key):
            raise ServiceError("ADMIN_REQUIRED_FOR_OVERRIDES", 403)
        user = (
            {"id": body.identity.actor_id, "company_id": body.identity.company_id}
            if body.identity
            else bank.user(body.demo_user_id or "demo-user-1")
        )
        prompt = body.system_prompt or await run_sync(
            lambda: cfg.system_prompt_path.read_text(encoding="utf-8")
        )
        s, token = sessions.create(
            user["id"],
            user["company_id"],
            prompt,
            {
                "model": cfg.llm_model,
                "temperature": cfg.llm_temperature,
                "max_tokens": cfg.llm_max_tokens,
            },
        )
        s.trusted_identity = body.identity is not None
        return {
            "session_id": s.id,
            "session_token": token,
            "prompt_hash": s.prompt_hash,
            "created_at": s.created_at,
            "expires_in_seconds": cfg.session_ttl_seconds,
            "demo_user_id": s.user_id,
            "company_id": s.company_id,
            "model": cfg.llm_model,
        }

    @app.get("/v1/sessions/{sid}/messages")
    async def history(sid: str, authorization: str | None = Header(None)):
        s, _ = session_auth(sid, authorization)
        # Return a transcript without internal tools; revoked knowledge cannot reappear on reload.
        active = await run_sync(lambda: {v["id"] for v in kb().repo.active_versions()})
        messages = []
        for cid, item in s.completed.items():
            response = item.get("response")
            if response and any(
                c.get("type") == "KNOWLEDGE" and c.get("version_id") not in active
                for c in response.get("citations", [])
            ):
                response = {
                    **response,
                    "answer": "Ответ скрыт: источник больше недоступен.",
                    "citations": [],
                    "pending_actions": [],
                    "status": "INSUFFICIENT_EVIDENCE",
                }
            messages.append(
                {
                    "client_message_id": cid,
                    "message": item["text"],
                    "response": response,
                    "error": item.get("error"),
                }
            )
        return {"session_id": sid, "messages": messages, "usage": s.usage}

    @app.get("/v1/sessions/{sid}/sources/{document_id}/{version}")
    async def cited_source(
        sid: str, document_id: str, version: int, authorization: str | None = Header(None)
    ):
        session, _ = session_auth(sid, authorization)
        cited = any(
            citation.get("document_id") == document_id and citation.get("version") == version
            for item in session.completed.values()
            for citation in (item.get("response") or {}).get("citations", [])
        )
        if not cited:
            raise ServiceError("SOURCE_NOT_FOUND", 404)
        source = await run_sync(lambda: kb().repo.version(document_id, version))
        if source["state"] != "PUBLISHED":
            raise ServiceError("SOURCE_REVOKED", 404)
        return {
            "title": source["metadata"]["title"],
            "text": source["text"],
            "metadata": source["metadata"],
        }

    @app.post("/v1/sessions/{sid}/messages", response_model=ChatResponse)
    async def chat(
        sid: str,
        body: NewMessage,
        request: Request,
        authorization: str | None = Header(None),
        x_admin_key: str | None = Header(None),
    ):
        s, _ = session_auth(sid, authorization)
        if s.trusted_identity and body.bank_context is None:
            raise ServiceError("BACKEND_CONTEXT_REQUIRED", 403)
        if body.bank_context is not None:
            if not is_admin(x_admin_key):
                raise ServiceError("ADMIN_REQUIRED_FOR_CONTEXT", 403)
            if body.bank_context.company_id != s.company_id:
                raise ServiceError("CONTEXT_COMPANY_MISMATCH", 403)
        previous = s.completed.get(body.client_message_id)
        if previous:
            if previous["text"] != body.message:
                raise ServiceError("IDEMPOTENCY_CONFLICT", 409)
            if "error" in previous:
                raise ServiceError(*previous["error"])
            return previous["response"]
        if s.busy:
            raise ServiceError("SESSION_BUSY", 409)
        kb()
        s.bank_context = body.bank_context.model_dump() if body.bank_context else None
        s.busy = True
        try:
            result = await app.state.agent.run(s, body.message, request.state.request_id)
            s.completed[body.client_message_id] = {"text": body.message, "response": result}
            return result
        except ServiceError as exc:
            s.completed[body.client_message_id] = {
                "text": body.message,
                "error": (exc.code, exc.status),
            }
            raise
        finally:
            s.busy = False
            s.last_activity = time.time()

    @app.delete("/v1/sessions/{sid}")
    async def close_session(sid: str, authorization: str | None = Header(None)):
        _, token = session_auth(sid, authorization)
        sessions.close(sid, token)
        if knowledge:

            def remove():
                with knowledge.lock:
                    knowledge.repo.cleanup_candidates(sid)

            await run_sync(remove)
        return {"closed": True}

    @app.get("/v1/knowledge/search", dependencies=[Depends(admin)])
    async def search(q: str = Query(min_length=1, max_length=2000)):
        return {
            "results": await run_sync(lambda: kb().search(q)),
            "dense_enabled": cfg.dense_min_score is not None,
        }

    @app.post("/v1/admin/knowledge/import", dependencies=[Depends(admin)])
    async def import_knowledge(
        metadata: str = Form(...),
        file: UploadFile | None = File(None),
        text: str | None = Form(None),
        document_id: str | None = Form(None),
    ):
        try:
            meta = Metadata.model_validate_json(metadata)
        except ValueError:
            raise ServiceError("INVALID_METADATA", 422) from None
        if (file is None) == (text is None):
            raise ServiceError("SUPPLY_FILE_OR_TEXT", 422)
        if file:
            raw = await file.read(10 * 1024 * 1024 + 1)
            filename = file.filename or "unknown"
        else:
            raw, filename = text.encode("utf-8"), "text.txt"
        return await run_sync(
            lambda: kb().ingest(raw, filename, meta.model_dump(mode="json"), document_id)
        )

    @app.get("/v1/admin/knowledge", dependencies=[Depends(admin)])
    async def list_knowledge():
        return {"documents": await run_sync(lambda: kb().repo.versions())}

    @app.get("/v1/admin/knowledge/{document_id}/versions/{version}", dependencies=[Depends(admin)])
    async def get_version(document_id: str, version: int):
        return await run_sync(lambda: kb().repo.version(document_id, version))

    @app.post(
        "/v1/admin/knowledge/{document_id}/versions/{version}/publish",
        dependencies=[Depends(admin)],
    )
    async def publish(document_id: str, version: int):
        return await run_sync(lambda: kb().publish(document_id, version))

    @app.post(
        "/v1/admin/knowledge/{document_id}/versions/{version}/revoke", dependencies=[Depends(admin)]
    )
    async def revoke(document_id: str, version: int):
        return await run_sync(lambda: kb().revoke(document_id, version))

    @app.get("/v1/admin/web-candidates/{cid}", dependencies=[Depends(admin)])
    async def candidate(cid: str):
        return await run_sync(lambda: kb().repo.candidate(cid))

    @app.post("/v1/admin/web-candidates/{cid}/confirm", dependencies=[Depends(admin)])
    async def confirm(cid: str, body: ConfirmCandidate):
        def operation():
            service = kb()
            with service.lock:
                c = service.repo.candidate(cid)
                if not secrets.compare_digest(c["sha256"], body.sha256):
                    raise ServiceError("CANDIDATE_HASH_CONFLICT", 409)
                if c["state"] == "CONFIRMED":
                    return c["knowledge_ref"]
                if c["state"] != "PENDING":
                    raise ServiceError("CANDIDATE_REJECTED", 409)
                metadata = Metadata(
                    title=c["title"],
                    source_type="WEB",
                    source_url=c["url"],
                    retrieved_at=c["retrieved_at"],
                    is_synthetic=False,
                    attribution=body.attribution,
                    allowed_use=body.allowed_use,
                )
                v = service.ingest(
                    c["text"].encode(), "snapshot.txt", metadata.model_dump(mode="json")
                )
                v = service.publish(v["document_id"], v["version"])
                ref = {
                    "document_id": v["document_id"],
                    "version": v["version"],
                    "sha256": v["sha256"],
                }
                service.repo.candidate_state(cid, "CONFIRMED", ref)
                return ref

        return await run_sync(operation)

    @app.delete("/v1/admin/web-candidates/{cid}", dependencies=[Depends(admin)])
    async def reject(cid: str):
        def operation():
            service = kb()
            with service.lock:
                c = service.repo.candidate(cid)
                if c["state"] == "CONFIRMED":
                    raise ServiceError("CANDIDATE_ALREADY_CONFIRMED", 409)
                service.repo.candidate_state(cid, "REJECTED")
            return {"rejected": True}

        return await run_sync(operation)

    return app
