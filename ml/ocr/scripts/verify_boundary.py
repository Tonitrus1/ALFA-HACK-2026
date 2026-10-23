"""Real 10-file / 50-page test, suitable for an external restart during polling."""

import json
import os
import time
from pathlib import Path

import httpx
import pymupdf

from alfa_ocr.config import Settings

ROOT = Path(__file__).resolve().parents[1]
settings = Settings()
if not (ROOT / "fixtures/generated/inn.pdf").exists():
    from generate_fixtures import generate

    generate()
with httpx.Client(
    base_url=os.environ.get("BOUNDARY_BASE_URL", "http://localhost:8001"),
    headers={"X-API-Key": settings.ocr_api_key.get_secret_value()},
    timeout=180,
) as client:
    source = pymupdf.open(ROOT / "fixtures/generated/inn.pdf")
    pdf = pymupdf.open()
    for _ in range(5):
        pdf.insert_pdf(source)
    files = [
        ("files", (f"synthetic-{i}.pdf", pdf.tobytes(deflate=True, garbage=4), "application/pdf"))
        for i in range(10)
    ]
    response = client.post("/v1/jobs", files=files)
    response.raise_for_status()
    job_id = response.json()["job_id"]
    (ROOT / "reports/local-boundary-job.json").write_text(json.dumps({"job_id": job_id}))
    print(f"Accepted real boundary job {job_id}: 10 files, 50 pages", flush=True)
    deadline = time.monotonic() + 1200
    while time.monotonic() < deadline:
        try:
            job = client.get(f"/v1/jobs/{job_id}").json()
            if job["status"] in ["failed", "succeeded"]:
                break
        except (httpx.HTTPError, ValueError, KeyError):
            pass
        time.sleep(2)
    if job["status"] != "succeeded":
        raise SystemExit(f"Boundary failed: {job.get('error_code')}")
    result = client.get(f"/v1/jobs/{job_id}/result").json()
    ocr = client.get(f"/v1/jobs/{job_id}/ocr").json()
    report = {
        "job_id": job_id,
        "real_ocr": True,
        "real_llm": True,
        "files": len(job["documents"]),
        "pages": len(ocr["pages"]),
        "inn_correct": result["extraction"]["person"]["inn"]["value"] == "000000000001",
        "requires_confirmation": result["requires_confirmation"],
        "provenance": result["provenance"],
    }
    (ROOT / "reports/boundary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    raise SystemExit(
        0 if report["files"] == 10 and report["pages"] == 50 and report["inn_correct"] else 1
    )
