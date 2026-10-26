"""Real persisted results and TTL cleanup; expiration timestamp is advanced explicitly."""

import argparse
import hashlib
import io
import json
import time
from pathlib import Path

import httpx
from PIL import Image

from alfa_ocr.config import Settings
from alfa_ocr.storage import Store

ROOT = Path(__file__).resolve().parents[1]
settings = Settings()


def run(mode):
    snapshot = ROOT / "reports/local-persistence.json"
    with httpx.Client(
        base_url="http://localhost:8001",
        headers={"X-API-Key": settings.ocr_api_key.get_secret_value()},
        timeout=180,
    ) as client:
        if mode == "snapshot":
            runtime = json.loads((ROOT / "reports/runtime.json").read_text())
            values = {}
            for name in ["base", "conflict"]:
                if runtime[name]["status"] != "succeeded":
                    continue
                job_id = runtime[name]["job_id"]
                response = client.get(f"/v1/jobs/{job_id}/result")
                response.raise_for_status()
                values[job_id] = hashlib.sha256(response.content).hexdigest()
            if not values:
                raise SystemExit("No real succeeded jobs for restart verification")
            snapshot.write_text(json.dumps(values))
            print("Saved result digests for restart verification")
            return
        report = {
            "result_survives_restart": True,
            "ttl_method": "production cleanup thread with expires timestamp advanced in SQLite; not a 24h wall-clock wait",
        }
        for job_id, digest in json.loads(snapshot.read_text()).items():
            response = client.get(f"/v1/jobs/{job_id}/result")
            report["result_survives_restart"] &= (
                response.status_code == 200
                and hashlib.sha256(response.content).hexdigest() == digest
            )
        stream = io.BytesIO()
        Image.new("RGB", (1000, 1400), "white").save(stream, format="PNG")
        response = client.post(
            "/v1/jobs", files={"files": ("blank.png", stream.getvalue(), "image/png")}
        )
        response.raise_for_status()
        job_id = response.json()["job_id"]
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            job = client.get(f"/v1/jobs/{job_id}").json()
            if job["status"] == "failed":
                break
            time.sleep(1)
        report["real_blank_scan_rejected"] = job["error_code"] == "OCR_NO_TEXT"
        store = Store(settings.data_dir)
        with store.db() as db:
            db.execute("UPDATE jobs SET expires=? WHERE id=?", (time.time() - 1, job_id))
        report["expired_job_immediately_inaccessible"] = (
            client.get(f"/v1/jobs/{job_id}").status_code == 404
        )
        deadline = time.monotonic() + 40
        while (store.jobs / job_id).exists() and time.monotonic() < deadline:
            time.sleep(1)
        report["expired_files_physically_removed"] = not (store.jobs / job_id).exists()
    (ROOT / "reports/lifecycle.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    raise SystemExit(0 if all(v for k, v in report.items() if k != "ttl_method") else 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["snapshot", "verify"])
    run(parser.parse_args().mode)
