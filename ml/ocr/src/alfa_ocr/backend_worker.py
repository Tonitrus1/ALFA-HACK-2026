"""Durable adapter from backend EXTRACT leases to the standalone OCR job API.

The ledger persists the remote job before polling. A crash in the submit/ledger
window can repeat a provider call; it never publishes into a different lease or
object version. Expired/missing jobs are resubmitted explicitly.
"""
import json
import logging
import os
import sqlite3
import time
from pathlib import Path

import httpx

log = logging.getLogger(__name__)
FIELD_NAMES = {
    "revenue": "revenue", "net_profit": "netProfit", "ebit": "ebit",
    "equity": "equity", "total_assets": "totalAssets", "current_assets": "currentAssets",
    "current_liabilities": "currentLiabilities",
}
# total_debt is not total liabilities: never map a different accounting concept.


def financial_fields(extraction):
    finance = extraction.get("financial", {})
    period, currency = finance.get("period", {}), finance.get("currency", {})
    if currency.get("status") != "extracted" or currency.get("value") != "RUB":
        return []
    fields = []
    for source, target in FIELD_NAMES.items():
        value = finance.get(source, {})
        refs = value.get("sources", [])
        if value.get("status") == "extracted" and value.get("value") is not None and refs:
            fields.append({"name": target, "value": value["value"],
                           "confidence": value["confidence"], "page": refs[0]["page"]})
    if period.get("status") == "extracted" and period.get("sources"):
        fields.append({"name": "period", "value": period["value"],
                       "confidence": period["confidence"], "page": period["sources"][0]["page"]})
    return fields


class Connector:
    def __init__(self):
        self.worker = "compose-ocr-worker"
        self.root = Path(os.environ.get("CONNECTOR_DATA_DIR", "/data"))
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / "jobs.sqlite3")
        self.db.execute("CREATE TABLE IF NOT EXISTS jobs (job_id TEXT PRIMARY KEY, object_version TEXT, remote_id TEXT)")
        self.backend = httpx.Client(base_url=os.environ.get("BACKEND_URL", "http://backend:8080"),
            headers={"X-Service-Token": os.environ["DOCUMENT_OCR_TOKEN"]}, timeout=30)
        self.ocr = httpx.Client(base_url=os.environ.get("OCR_URL", "http://ocr:8001"),
            headers={"X-API-Key": os.environ["OCR_API_KEY"]}, timeout=60)

    def proof(self, lease):
        return {"workerId": self.worker, "generation": lease["generation"], "leaseToken": lease["leaseToken"]}

    def tick(self):
        (self.root / "heartbeat").touch()

    def process_once(self):
        # Leave the lease unclaimed until the real OCR engine and LLM settings are ready.
        self.ocr.get("/health/ready").raise_for_status()
        response = self.backend.post("/internal/v1/document-jobs/claim", json={"workerId": self.worker, "jobType": "EXTRACT"})
        response.raise_for_status()
        if response.status_code == 204:
            return False
        lease = response.json()
        base = "/internal/v1/document-jobs/" + lease["jobId"]
        old = self.db.execute("SELECT remote_id FROM jobs WHERE job_id=? AND object_version=?", (lease["jobId"], lease["objectVersion"])).fetchone()
        remote_id = old[0] if old else None
        if remote_id and self.ocr.get("/v1/jobs/" + remote_id).status_code == 404:
            remote_id = None
        if not remote_id:
            content = self.backend.get(base + "/content", headers={"X-Worker-Id": self.worker,
                "X-Lease-Generation": str(lease["generation"]), "X-Lease-Token": lease["leaseToken"]})
            content.raise_for_status()
            submitted = self.ocr.post("/v1/jobs", files={"files": ("document", content.content, "application/octet-stream")})
            submitted.raise_for_status()
            remote_id = submitted.json()["job_id"]
            self.db.execute("INSERT OR REPLACE INTO jobs VALUES (?,?,?)", (lease["jobId"], lease["objectVersion"], remote_id))
            self.db.commit()
        renew_at = time.monotonic() + 25
        while True:
            self.tick()
            if time.monotonic() >= renew_at:
                self.backend.post(base + "/renew", json=self.proof(lease)).raise_for_status()
                renew_at = time.monotonic() + 25
            status = self.ocr.get("/v1/jobs/" + remote_id)
            status.raise_for_status()
            state = status.json()["status"]
            if state in {"succeeded", "failed"}:
                break
            time.sleep(2)
        fields, engine = [], "ocr-pipeline-failed"
        if state == "succeeded":
            result = self.ocr.get("/v1/jobs/" + remote_id + "/result")
            result.raise_for_status()
            result = result.json()
            fields = financial_fields(result["extraction"])
            engine = result["provenance"]["ocr_engine"] + ":" + result["provenance"]["ocr_version"]
        self.backend.post(base + "/extraction-result", json={**self.proof(lease),
            "objectVersion": lease["objectVersion"], "engineVersion": engine[:256],
            "status": "READY" if state == "succeeded" else "FAILED", "fields": fields}).raise_for_status()
        self.db.execute("DELETE FROM jobs WHERE job_id=?", (lease["jobId"],))
        self.db.commit()
        self.ocr.delete("/v1/jobs/" + remote_id).raise_for_status()
        return True


def main():
    logging.basicConfig(level=logging.INFO)
    connector = Connector()
    while True:
        connector.tick()
        try:
            if connector.process_once():
                continue
        except Exception:
            # No response bodies, URLs containing tokens, document text or credentials in logs.
            log.warning("OCR_CONNECTOR_RETRY")
        time.sleep(5)


if __name__ == "__main__":
    main()
