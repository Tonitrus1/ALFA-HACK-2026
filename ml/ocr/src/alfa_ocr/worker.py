import json
import threading
import time

from .contract import Contract
from .engines import Engine
from .extraction import extract
from .files import render
from .models import Page, ServiceError
from .storage import write_json


class Worker:
    def __init__(self, settings, store):
        self.settings, self.store = settings, store
        self.engine = Engine(settings.ocr_engine, settings.cpu_threads, settings.ocr_enable_mkldnn)
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True, name="ocr-worker")
        self.cleaner = threading.Thread(target=self.clean, daemon=True, name="ocr-cleaner")
        self.ready = False
        self.startup_error = None

    def start(self):
        self.cleaner.start()
        self.thread.start()

    def clean(self):
        while not self.stop.wait(30):
            self.store.cleanup()

    def run(self):
        try:
            self.engine.load()
            self.ready = True
        except Exception:
            self.startup_error = "OCR_INITIALIZATION_FAILED"
            return
        while not self.stop.is_set():
            job = self.store.claim()
            if job is None:
                self.stop.wait(0.5)
                continue
            self.process(job)

    def process(self, job):
        directory = self.store.jobs / job.job_id
        started = time.monotonic()
        try:
            snapshot = json.loads((directory / "contract.json").read_text(encoding="utf-8"))
            contract = Contract(**snapshot)
            pages = []
            for document in job.documents:
                for index, image in enumerate(
                    render(
                        directory / document.document_id,
                        document.media_type,
                        self.settings.page_dpi,
                    ),
                    1,
                ):
                    if not self.store.get(job.job_id) or self.stop.is_set():
                        return
                    blocks = self.engine.recognize(image)
                    pages.append(
                        Page(
                            document_id=document.document_id,
                            page=index,
                            width=image.width,
                            height=image.height,
                            blocks=blocks,
                        )
                    )
            if not any(p.blocks for p in pages):
                raise ServiceError("OCR_NO_TEXT")
            if not self.store.get(job.job_id):
                return
            write_json(
                directory / "ocr.json",
                {
                    "engine": self.engine.name,
                    "engine_version": self.engine.version(),
                    "pages": [p.model_dump() for p in pages],
                    "seconds": round(time.monotonic() - started, 3),
                },
            )
            job.stage = "llm"
            self.store.save(job)
            extracted, llm_meta = extract(
                self.settings,
                contract,
                pages,
                active=lambda: self.store.get(job.job_id) is not None,
            )
            job.stage = "validation"
            self.store.save(job)
            contract.validate(extracted, pages)
            if not self.store.get(job.job_id):
                return
            write_json(
                directory / "result.json",
                {
                    "job_id": job.job_id,
                    "requires_confirmation": True,
                    "extraction": extracted,
                    "provenance": {
                        **contract.fingerprint(),
                        "ocr_engine": self.engine.name,
                        "ocr_version": self.engine.version(),
                        "llm": llm_meta,
                        "seconds": round(time.monotonic() - started, 3),
                    },
                },
            )
            job.status, job.stage = "succeeded", "done"
        except ServiceError as error:
            job.status, job.error_code = "failed", error.code
        except Exception:
            # Exceptions from libraries may contain documents or credentials.
            job.status, job.error_code = "failed", "PIPELINE_INTERNAL_ERROR"
        self.store.save(job)
