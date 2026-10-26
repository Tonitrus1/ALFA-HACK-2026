import asyncio
import hashlib
import hmac
import json
import shutil
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import Depends, FastAPI, Request, Security
from fastapi.responses import JSONResponse, Response
from fastapi.security import APIKeyHeader
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException

from .config import MAX_BATCH_BYTES, MAX_FILE_BYTES, MAX_FILES, MAX_PAGES, TTL_SECONDS, Settings
from .contract import Contract
from .files import inspect
from .models import Accepted, Document, Job, ServiceError
from .responses import ExtractionResult, OCRResult
from .storage import Store, write_json
from .worker import Worker


class BodyLimit:
    """Enforce the byte budget even for chunked multipart, before parsing files."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        maximum = MAX_BATCH_BYTES + 1024 * 1024
        size = 0

        async def limited_receive():
            nonlocal size
            try:
                message = await asyncio.wait_for(receive(), timeout=30)
            except TimeoutError:
                raise HTTPException(408, "UPLOAD_TIMEOUT") from None
            size += len(message.get("body", b""))
            if size > maximum:
                raise HTTPException(413, "UPLOAD_TOO_LARGE")
            return message

        await self.app(scope, limited_receive, send)


def create_app(settings=None):
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        if not settings.ocr_api_key.get_secret_value():
            raise RuntimeError("OCR_API_KEY_REQUIRED")
        store = Store(settings.data_dir)
        # Fail startup on multiple processes sharing a volume; no silent job replay race.
        import fcntl

        lock = (settings.data_dir / "worker.lock").open("w")
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        store.recover()
        app.state.contract = Contract.read(settings)
        app.state.store = store
        app.state.upload_lock = asyncio.Lock()
        worker = Worker(settings, store)
        app.state.worker = worker
        worker.start()
        yield
        worker.stop.set()
        worker.thread.join(timeout=5)
        worker.cleaner.join(timeout=5)
        lock.close()

    app = FastAPI(
        title="ALFA standalone OCR",
        version="0.1.0",
        lifespan=lifespan,
        description="CPU OCR → local or external OpenAI-compatible LLM → validated JSON. Internal service; all values require user confirmation.",
    )
    app.add_middleware(BodyLimit)
    token = APIKeyHeader(name="X-API-Key", auto_error=False)

    def authorize(value=Security(token)):
        if not value or not hmac.compare_digest(
            value.encode("utf-8"), settings.ocr_api_key.get_secret_value().encode("utf-8")
        ):
            raise ServiceError("UNAUTHORIZED", 401)

    auth = [Depends(authorize)]

    @app.exception_handler(ServiceError)
    async def service_error(request, error):
        return JSONResponse({"error_code": error.code}, status_code=error.status)

    @app.exception_handler(HTTPException)
    async def http_error(request, error):
        return JSONResponse(
            {"error_code": "UPLOAD_TOO_LARGE" if error.status_code == 413 else "REQUEST_INVALID"},
            status_code=error.status_code,
        )

    @app.get("/health/live")
    def live():
        return {"status": "alive"}

    @app.get("/health/ready")
    def ready(request: Request):
        worker = request.app.state.worker
        available = (
            worker.ready
            and worker.thread.is_alive()
            and worker.cleaner.is_alive()
            and bool(settings.llm_api_key.get_secret_value())
        )
        return JSONResponse(
            {
                "ready": available,
                "ocr_ready": worker.ready,
                "llm_configured": bool(settings.llm_api_key.get_secret_value()),
                "error_code": worker.startup_error,
            },
            status_code=200 if available else 503,
        )

    @app.get("/v1/schema", dependencies=auth)
    def schema(request: Request):
        return request.app.state.contract.schema

    @app.post(
        "/v1/jobs",
        response_model=Accepted,
        status_code=202,
        dependencies=auth,
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "multipart/form-data": {
                        "schema": {
                            "type": "object",
                            "required": ["files"],
                            "properties": {
                                "files": {
                                    "type": "array",
                                    "minItems": 1,
                                    "maxItems": 10,
                                    "items": {"type": "string", "format": "binary"},
                                }
                            },
                        }
                    }
                },
            }
        },
    )
    async def submit(request: Request):
        state = request.app.state
        if not state.worker.ready or not state.worker.thread.is_alive():
            raise ServiceError("OCR_NOT_READY", 503)
        async with state.upload_lock:
            if state.store.count_pending() >= settings.max_queued_jobs:
                raise ServiceError("QUEUE_FULL", 429)
            job_id = str(uuid.uuid4())
            directory = state.store.staging / job_id
            directory.mkdir()
            destination = state.store.jobs / job_id
            try:
                async with request.form(max_files=MAX_FILES, max_fields=0) as form:
                    uploads = form.getlist("files")
                    if (
                        not 1 <= len(uploads) <= MAX_FILES
                        or len(form.multi_items()) != len(uploads)
                        or any(not isinstance(f, UploadFile) for f in uploads)
                    ):
                        raise ServiceError("FILES_REQUIRED")
                    documents, total, page_count = [], 0, 0
                    for upload in uploads:
                        document_id = str(uuid.uuid4())
                        path = directory / document_id
                        size, digest = 0, hashlib.sha256()
                        with path.open("wb") as stream:
                            while chunk := await upload.read(1024 * 1024):
                                size += len(chunk)
                                total += len(chunk)
                                if size > MAX_FILE_BYTES or total > MAX_BATCH_BYTES:
                                    raise ServiceError("UPLOAD_TOO_LARGE", 413)
                                digest.update(chunk)
                                stream.write(chunk)
                        media_type, count = await asyncio.to_thread(inspect, path)
                        page_count += count
                        if page_count > MAX_PAGES:
                            raise ServiceError("TOO_MANY_PAGES", 413)
                        documents.append(
                            Document(
                                document_id=document_id,
                                sha256=digest.hexdigest(),
                                media_type=media_type,
                                pages=count,
                            )
                        )
                write_json(directory / "contract.json", asdict(state.contract))
                directory.rename(destination)
                now = time.time()
                job = Job(
                    job_id=job_id,
                    status="queued",
                    created_at=now,
                    expires_at=now + TTL_SECONDS,
                    documents=documents,
                )
                state.store.create(job)
                return Accepted(
                    job_id=job_id, expires_at=job.expires_at, status_url=f"/v1/jobs/{job_id}"
                )
            except BaseException:
                shutil.rmtree(directory, ignore_errors=True)
                shutil.rmtree(destination, ignore_errors=True)
                raise

    def find(request, job_id):
        job = request.app.state.store.get(str(job_id))
        if job is None:
            raise ServiceError("JOB_NOT_FOUND", 404)
        return job

    @app.get("/v1/jobs/{job_id}", response_model=Job, dependencies=auth)
    def status(request: Request, job_id: uuid.UUID):
        return find(request, job_id)

    @app.get("/v1/jobs/{job_id}/schema", dependencies=auth)
    def job_schema(request: Request, job_id: uuid.UUID):
        job = find(request, job_id)
        try:
            snapshot = json.loads(
                (request.app.state.store.jobs / job.job_id / "contract.json").read_text(
                    encoding="utf-8"
                )
            )
            return snapshot["schema"]
        except FileNotFoundError:
            raise ServiceError("JOB_NOT_FOUND", 404) from None

    @app.get("/v1/jobs/{job_id}/result", response_model=ExtractionResult, dependencies=auth)
    def result(request: Request, job_id: uuid.UUID):
        job = find(request, job_id)
        if job.status != "succeeded":
            raise ServiceError("RESULT_NOT_READY", 409)
        try:
            return json.loads(
                (request.app.state.store.jobs / job.job_id / "result.json").read_text(
                    encoding="utf-8"
                )
            )
        except FileNotFoundError:
            raise ServiceError("JOB_NOT_FOUND", 404) from None

    @app.get("/v1/jobs/{job_id}/ocr", response_model=OCRResult, dependencies=auth)
    def ocr(request: Request, job_id: uuid.UUID):
        job = find(request, job_id)
        path = request.app.state.store.jobs / job.job_id / "ocr.json"
        if not path.is_file():
            raise ServiceError("OCR_NOT_READY", 409)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise ServiceError("JOB_NOT_FOUND", 404) from None

    @app.delete("/v1/jobs/{job_id}", status_code=204, dependencies=auth)
    def delete(request: Request, job_id: uuid.UUID):
        job = find(request, job_id)
        request.app.state.store.delete(job.job_id)
        return Response(status_code=204)

    return app
