"""Real HTTP -> OCR -> paid external LLM -> validation. Never substitutes models."""

import argparse
import json
import time
from decimal import Decimal
from pathlib import Path

import httpx
from benchmark_ocr import distance, normalized

from alfa_ocr.config import Settings
from alfa_ocr.contract import Contract
from alfa_ocr.models import Page

ROOT = Path(__file__).resolve().parents[1]


def analyze_existing(base):
    """Read actual OCR independently of the LLM outcome; retain metrics only."""
    settings = Settings()
    path = ROOT / "reports/runtime.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    truth = json.loads((ROOT / "fixtures/generated/truth.json").read_text(encoding="utf-8"))
    with httpx.Client(
        base_url=base, headers={"X-API-Key": settings.ocr_api_key.get_secret_value()}, timeout=30
    ) as client:
        for mode in ["base", "conflict"]:
            names = ["passport", "inn", "snils", "statement", "financial", "other"] + (
                ["conflict"] if mode == "conflict" else []
            )
            job_id = report[mode]["job_id"]
            job = client.get(f"/v1/jobs/{job_id}").json()
            response = client.get(f"/v1/jobs/{job_id}/ocr")
            response.raise_for_status()
            ocr = response.json()
            metrics = {}
            for name, document in zip(names, job["documents"], strict=True):
                text = " ".join(
                    block["text"]
                    for page in ocr["pages"]
                    if page["document_id"] == document["document_id"]
                    for block in page["blocks"]
                )
                actual, expected = normalized(text), normalized(truth[name])
                metrics[name] = {
                    "cer": round(distance(expected, actual) / len(expected), 5),
                    "wer": round(
                        distance(expected.split(), actual.split()) / len(expected.split()), 5
                    ),
                }
            report[mode]["real_pdf_ocr_metrics"] = metrics
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({mode: report[mode]["real_pdf_ocr_metrics"] for mode in ["base", "conflict"]}))


def run(base):
    settings = Settings()
    if not settings.llm_api_key.get_secret_value():
        raise SystemExit("NOT_EXECUTED: LLM_API_KEY missing")
    report = {"synthetic_only": True, "real_ocr": True, "real_llm": True, "checks": {}}
    with httpx.Client(
        base_url=base, headers={"X-API-Key": settings.ocr_api_key.get_secret_value()}, timeout=180
    ) as client:
        report["checks"]["ready"] = client.get("/health/ready").status_code == 200
        for mode in ["base", "conflict"]:
            names = ["passport", "inn", "snils", "statement", "financial", "other"]
            if mode == "conflict":
                names.append("conflict")
            # Entire request is synthetic raster-only PDFs, not the real user files.
            files = [
                (
                    "files",
                    (
                        name + ".pdf",
                        (ROOT / f"fixtures/generated/{name}.pdf").read_bytes(),
                        "application/pdf",
                    ),
                )
                for name in names
            ]
            response = client.post("/v1/jobs", files=files)
            response.raise_for_status()
            job_id = response.json()["job_id"]
            report[mode] = {"job_id": job_id}
            deadline = time.monotonic() + 900
            while time.monotonic() < deadline:
                job = client.get(f"/v1/jobs/{job_id}").json()
                if job["status"] in ["succeeded", "failed"]:
                    break
                time.sleep(2)
            report[mode]["status"] = job["status"]
            report[mode]["error_code"] = job["error_code"]
            if job["status"] != "succeeded":
                continue
            result = client.get(f"/v1/jobs/{job_id}/result").json()
            ocr = client.get(f"/v1/jobs/{job_id}/ocr").json()
            contract = Contract.read(settings)
            contract.validate(result["extraction"], [Page(**p) for p in ocr["pages"]])
            report[mode]["schema_and_sources_valid"] = True
            report[mode]["provenance"] = result["provenance"]
            extraction = result["extraction"]
            expected = {
                "person.full_name": "ИВАНОВ ИВАН ИВАНОВИЧ",
                "person.birth_date": "1990-05-15",
                "person.inn": "000000000001",
                "person.snils": "00000000001",
                "person.passport_series": "0000",
                "person.passport_number": "000001",
                "organization.inn": "0000000002",
                "financial.net_profit": "1500000.00",
                "financial.ebit": "2000000.00",
                "financial.equity": "5000000.00",
                "financial.total_assets": "10000000.00",
                "financial.current_assets": "4000000.00",
                "financial.current_liabilities": "2500000.00",
                "financial.total_debt": "3000000.00",
            }
            if mode == "base":
                expected["financial.revenue"] = "12000000.00"
            checks = {}
            for path, target in expected.items():
                section, key = path.split(".")
                field = extraction[section][key]
                actual = field["value"]
                equal = actual == target
                if section == "financial" and actual is not None:
                    equal = Decimal(actual) == Decimal(target)
                checks[path] = field["status"] == "extracted" and equal
            checks["missing_kpp"] = extraction["organization"]["kpp"]["status"] == "missing"
            checks["missing_ogrn"] = extraction["organization"]["ogrn"]["status"] == "missing"
            checks["financial_period"] = "2025" in (
                extraction["financial"]["period"]["value"] or ""
            )
            checks["financial_currency"] = extraction["financial"]["currency"]["value"] == "RUB"
            checks["extension_demo_code"] = any(
                item["field"]["value"] == "DEMO-2026" for item in extraction["extensions"]
            )
            document_types = {
                item["document_id"]: item["document_type"] for item in extraction["documents"]
            }
            classes = {
                "passport": "passport",
                "inn": "inn",
                "snils": "snils",
                "statement": "bank_statement",
                "financial": "financial",
                "other": "other",
                "conflict": "financial",
            }
            checks["document_classification"] = all(
                document_types.get(document["document_id"]) == classes[name]
                for name, document in zip(names, job["documents"], strict=True)
            )
            if mode == "conflict":
                field = extraction["financial"]["revenue"]
                checks["revenue_conflict"] = field["status"] == "conflict" and {
                    Decimal(c["value"]) for c in field["candidates"]
                } == {Decimal("12000000"), Decimal("13000000")}
            report[mode]["extraction_checks"] = checks
        # Validation failures must not enqueue any jobs.
        report["checks"]["reject_11_files"] = (
            client.post(
                "/v1/jobs",
                files=[
                    (
                        "files",
                        ("a.png", (ROOT / "fixtures/generated/inn.png").read_bytes(), "image/png"),
                    )
                ]
                * 11,
            ).status_code
            == 400
        )
        report["checks"]["reject_51_pages"] = (
            client.post(
                "/v1/jobs",
                files={
                    "files": (
                        "many.pdf",
                        (ROOT / "fixtures/generated/over_limit.pdf").read_bytes(),
                        "application/pdf",
                    )
                },
            ).status_code
            == 413
        )
        report["checks"]["reject_invalid"] = (
            client.post(
                "/v1/jobs", files={"files": ("fake.pdf", b"not a pdf", "application/pdf")}
            ).status_code
            == 422
        )
        report["checks"]["auth_required"] = httpx.get(base + "/v1/schema").status_code == 401
    (ROOT / "reports/runtime.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))
    ok = all(report["checks"].values()) and all(
        report.get(mode, {}).get("status") == "succeeded"
        and all(report[mode].get("extraction_checks", {}).values())
        for mode in ["base", "conflict"]
    )
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8001")
    parser.add_argument("--analyze-existing", action="store_true")
    arguments = parser.parse_args()
    if arguments.analyze_existing:
        analyze_existing(arguments.url)
    else:
        run(arguments.url)
