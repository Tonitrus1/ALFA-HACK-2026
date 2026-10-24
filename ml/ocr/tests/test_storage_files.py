import time

import pymupdf
import pytest
from PIL import Image

from alfa_ocr.files import inspect
from alfa_ocr.models import Job, ServiceError
from alfa_ocr.storage import Store, write_json


def make_job(job_id="test", **extra):
    return Job(
        job_id=job_id,
        status="queued",
        documents=[],
        created_at=time.time(),
        expires_at=time.time() + 86400,
        **extra,
    )


def test_durable_claim_recovery_and_ttl(tmp_path):
    store = Store(tmp_path)
    job = make_job()
    (store.jobs / job.job_id).mkdir()
    write_json(store.jobs / job.job_id / "result.json", {"test": "synthetic"})
    store.create(job)
    assert store.claim().status == "processing"
    assert store.claim() is None
    restarted = Store(tmp_path)
    restarted.recover()
    assert restarted.get(job.job_id).status == "queued"
    job = restarted.claim()
    assert job.status == "processing"
    with restarted.db() as db:
        db.execute("UPDATE jobs SET expires=? WHERE id=?", (time.time() - 1, job.job_id))
    assert restarted.get(job.job_id) is None
    restarted.cleanup()
    assert not (store.jobs / job.job_id).exists()
    assert restarted.count_pending() == 0


def test_deleted_job_cannot_be_resurrected(tmp_path):
    store = Store(tmp_path)
    job = make_job()
    store.create(job)
    store.delete(job.job_id)
    job.status = "succeeded"
    store.save(job)
    assert store.get(job.job_id) is None


def test_content_sniff_and_multipage_tiff(tmp_path):
    path = tmp_path / "no-extension"
    image = Image.new("RGB", (100, 100), "white")
    image.save(path, format="TIFF", save_all=True, append_images=[image])
    assert inspect(path) == ("image/tiff", 2)


def test_pdf_limit_and_encryption(tmp_path):
    path = tmp_path / "pdf"
    pdf = pymupdf.open()
    for _ in range(51):
        pdf.new_page()
    pdf.save(path)
    with pytest.raises(ServiceError, match="TOO_MANY_PAGES"):
        inspect(path)
    path.unlink()
    pdf = pymupdf.open()
    pdf.new_page()
    pdf.save(path, encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="user")
    with pytest.raises(ServiceError, match="PDF_ENCRYPTED_OR_EMPTY"):
        inspect(path)


def test_invalid_document(tmp_path):
    path = tmp_path / "fake.pdf"
    path.write_bytes(b"not a document")
    with pytest.raises(ServiceError, match="INVALID_DOCUMENT"):
        inspect(path)
