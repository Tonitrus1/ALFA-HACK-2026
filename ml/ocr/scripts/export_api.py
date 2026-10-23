import json
from pathlib import Path

from alfa_ocr.api import create_app

ROOT = Path(__file__).resolve().parents[1]
(ROOT / "openapi.json").write_text(
    json.dumps(create_app().openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
items = []
for name, method, path in [
    ("Ready", "GET", "/health/ready"),
    ("Schema", "GET", "/v1/schema"),
    ("Submit", "POST", "/v1/jobs"),
    ("Status", "GET", "/v1/jobs/{{job_id}}"),
    ("Job schema", "GET", "/v1/jobs/{{job_id}}/schema"),
    ("OCR", "GET", "/v1/jobs/{{job_id}}/ocr"),
    ("Result", "GET", "/v1/jobs/{{job_id}}/result"),
    ("Delete", "DELETE", "/v1/jobs/{{job_id}}"),
]:
    request = {
        "method": method,
        "header": [{"key": "X-API-Key", "value": "{{ocr_api_key}}"}],
        "url": "{{base_url}}" + path,
    }
    if method == "POST":
        request["body"] = {
            "mode": "formdata",
            "formdata": [
                {"key": "files", "type": "file", "src": "../fixtures/generated/passport.pdf"}
            ],
        }
    item = {"name": name, "request": request}
    if name == "Submit":
        item["event"] = [
            {
                "listen": "test",
                "script": {
                    "type": "text/javascript",
                    "exec": [
                        "if (pm.response.code === 202) pm.collectionVariables.set('job_id', pm.response.json().job_id);"
                    ],
                },
            }
        ]
    items.append(item)
collection = {
    "info": {
        "name": "ALFA standalone OCR",
        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
    },
    "variable": [
        {"key": "base_url", "value": "http://localhost:8001"},
        {"key": "ocr_api_key", "value": ""},
        {"key": "job_id", "value": ""},
    ],
    "item": items,
}
(ROOT / "requests/ocr.postman_collection.json").write_text(
    json.dumps(collection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print("Exported OpenAPI and Postman collection without credentials")
