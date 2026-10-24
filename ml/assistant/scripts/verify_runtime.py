"""Read-only runtime checks plus a disposable session; no paid generation with a configured key."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import anyio
import httpx

from alfa_assistant.config import Settings
from alfa_assistant.web import SafePageReader, URLPolicy


async def main():
    settings = Settings()
    report = {"checked_at": datetime.now(UTC).isoformat(), "paid_requests": 0}
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:8000", timeout=65, trust_env=False
    ) as client:
        report["live"] = (await client.get("/health/live")).status_code
        report["swagger"] = (await client.get("/docs")).status_code
        report["openapi"] = (await client.get("/openapi.json")).status_code
        ready = await client.get("/health/ready")
        report["ready"] = {"http_status": ready.status_code, **ready.json()}
        r = await client.get(
            "/v1/knowledge/search",
            params={"q": "ставка Демо Оборотный"},
            headers={"X-Admin-Key": settings.admin_api_key.get_secret_value()},
        )
        r.raise_for_status()
        report["rag_results"] = len(r.json()["results"])
        r = await client.post("/v1/sessions", json={})
        r.raise_for_status()
        session = r.json()
        auth = {"Authorization": "Bearer " + session["session_token"]}
        path = "/v1/sessions/" + session["session_id"]
        if not ready.json()["dependencies"]["llm_key_configured"]:
            # Service detects the missing key locally, never calls the provider.
            r = await client.post(
                path + "/messages",
                headers=auth,
                json={
                    "client_message_id": "runtime-check",
                    "message": "Какая ставка Демо Оборотного?",
                },
            )
            r.raise_for_status()
            result = r.json()
            report["missing_key_chat"] = {
                "status": result["status"],
                "citations": len(result["citations"]),
                "error_code": result["usage"]["error_code"],
            }
        report["history"] = (await client.get(path + "/messages", headers=auth)).status_code
        report["close"] = (await client.delete(path, headers=auth)).status_code
    try:
        page = await SafePageReader(URLPolicy(["cbr.ru"]), anyio.to_thread.run_sync).read(
            "https://www.cbr.ru/develop/msp/"
        )
        report["real_page_fetch"] = {
            "success": True,
            "url": page["url"],
            "characters": len(page["text"]),
        }
    except Exception as exc:
        report["real_page_fetch"] = {
            "success": False,
            "error_type": type(exc).__name__,
            "code": getattr(exc, "code", None),
        }
    Path("reports/runtime-smoke.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
