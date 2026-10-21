"""Generate a portable Postman collection without secrets."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    items = []

    def request(name, method, path, body=None, admin=False, session=False, test=None):
        headers = []
        if admin:
            headers.append({"key": "X-Admin-Key", "value": "{{admin_key}}"})
        if session:
            headers.append({"key": "Authorization", "value": "Bearer {{session_token}}"})
        req = {"method": method, "header": headers, "url": "{{base_url}}" + path}
        if body is not None:
            headers.append({"key": "Content-Type", "value": "application/json"})
            req["body"] = {
                "mode": "raw",
                "raw": json.dumps(body, ensure_ascii=False, indent=2),
                "options": {"raw": {"language": "json"}},
            }
        item = {"name": name, "request": req}
        if test:
            item["event"] = [
                {"listen": "test", "script": {"type": "text/javascript", "exec": test}}
            ]
        items.append(item)

    request(
        "1. Создать сессию",
        "POST",
        "/v1/sessions",
        {},
        test=[
            "pm.test('Created', () => pm.response.to.have.status(201));",
            "const s = pm.response.json();",
            "pm.collectionVariables.set('session_id', s.session_id);",
            "pm.collectionVariables.set('session_token', s.session_token);",
        ],
    )
    request(
        "2. Синтетические продукты",
        "POST",
        "/v1/sessions/{{session_id}}/messages",
        {
            "client_message_id": "{{$guid}}",
            "message": "Какие есть синтетические кредитные продукты?",
        },
        session=True,
    )
    request(
        "3. Связный диалог",
        "POST",
        "/v1/sessions/{{session_id}}/messages",
        {"client_message_id": "{{$guid}}", "message": "А какие документы нужны для demo-app-1?"},
        session=True,
    )
    request(
        "4. Найти, прочитать и предложить сохранить",
        "POST",
        "/v1/sessions/{{session_id}}/messages",
        {
            "client_message_id": "{{$guid}}",
            "message": "Найди на cbr.ru материалы о финансировании МСП, прочитай страницу и предложи сохранить её в знания. Используй поиск в интернете.",
        },
        session=True,
        test=[
            "const actions = pm.response.json().pending_actions || [];",
            "if (actions.length) {",
            "  pm.collectionVariables.set('candidate_id', actions[0].candidate_id);",
            "  pm.collectionVariables.set('snapshot_sha256', actions[0].sha256);",
            "} else { console.log('Продолжите диалог: модель ещё не предложила снимок'); }",
        ],
    )
    request(
        "5. Просмотреть снимок и проверить права хранения",
        "GET",
        "/v1/admin/web-candidates/{{candidate_id}}",
        admin=True,
    )
    request(
        "6. Подтвердить точный снимок",
        "POST",
        "/v1/admin/web-candidates/{{candidate_id}}/confirm",
        {
            "sha256": "{{snapshot_sha256}}",
            "attribution": "Банк России; URL в метаданных",
            "allowed_use": "{{verified_allowed_use}}",
        },
        admin=True,
    )
    request(
        "7. Найти сохранённое в RAG",
        "GET",
        "/v1/knowledge/search?q=финансирование%20МСП",
        admin=True,
    )
    request("8. История", "GET", "/v1/sessions/{{session_id}}/messages", session=True)
    request("9. Закрыть сессию", "DELETE", "/v1/sessions/{{session_id}}", session=True)
    collection = {
        "info": {
            "name": "ALFA Assistant — development",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
            "description": "Внешний платный LLM API. Перед шагом 6 просмотрите снимок и задайте verified_allowed_use. Ключи только локально.",
        },
        "variable": [
            {"key": k, "value": v}
            for k, v in {
                "base_url": "http://localhost:8000",
                "admin_key": "",
                "session_id": "",
                "session_token": "",
                "candidate_id": "",
                "snapshot_sha256": "",
                "verified_allowed_use": "",
            }.items()
        ],
        "item": items,
    }
    (ROOT / "requests/assistant.postman_collection.json").write_text(
        json.dumps(collection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
