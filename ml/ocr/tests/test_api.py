"""Contract tests with an explicitly substituted worker. Not model evidence."""

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from alfa_ocr.api import create_app
from alfa_ocr.config import Settings

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def client(tmp_path, monkeypatch):
    class StubWorker:
        def __init__(self, *args):
            self.ready = True
            self.startup_error = None
            self.thread = self.cleaner = self
            self.stop = self

        def start(self):
            pass

        def set(self):
            pass

        def join(self, **kwargs):
            pass

        def is_alive(self):
            return True

    monkeypatch.setattr("alfa_ocr.api.Worker", StubWorker)
    settings = Settings(
        ocr_api_key="unit-only",
        data_dir=tmp_path,
        prompt_path=ROOT / "prompts/extract.txt",
        schema_path=ROOT / "schemas/extraction.schema.json",
        max_queued_jobs=1,
    )
    with TestClient(create_app(settings)) as client:
        client.headers["X-API-Key"] = "unit-only"
        yield client


def png():
    image = Image.new("RGB", (100, 100), "white")
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def test_auth_and_bad_upload(client):
    assert client.get("/v1/schema", headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.get("/v1/schema", headers={b"X-API-Key": b"\xff"}).status_code == 401
    assert client.post("/v1/jobs", files={"files": ("a.pdf", b"fake")}).status_code == 422
    assert client.post("/v1/jobs", files=[("files", ("a.png", png()))] * 11).status_code == 400
    assert client.post("/v1/jobs", files={"other": ("a.png", png())}).status_code == 422


def test_submit_queue_delete_and_no_result(client):
    response = client.post("/v1/jobs", files={"files": ("../../unsafe-name", png())})
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    status = client.get(f"/v1/jobs/{job_id}").json()
    assert client.get(f"/v1/jobs/{job_id}/schema").json() == client.get("/v1/schema").json()
    assert status["documents"][0]["media_type"] == "image/png"
    assert "unsafe-name" not in str(status)
    assert client.get(f"/v1/jobs/{job_id}/result").status_code == 409
    assert client.post("/v1/jobs", files={"files": ("a.png", png())}).status_code == 429
    assert client.delete(f"/v1/jobs/{job_id}").status_code == 204
    assert client.get(f"/v1/jobs/{job_id}").status_code == 404
