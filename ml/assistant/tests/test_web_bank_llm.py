import asyncio
import json
import logging
import socket
from decimal import Decimal

import httpx
import pytest
from conftest import call, open_session, send
from openai import AsyncOpenAI
from pydantic import ValidationError

from alfa_assistant.bank import annuity
from alfa_assistant.errors import ServiceError
from alfa_assistant.llm import Completion, OpenAICompatibleLLM
from alfa_assistant.observability import SafeJSONFormatter
from alfa_assistant.schemas import AnnuityArgs
from alfa_assistant.web import SafePageReader, SearxngSearch, URLPolicy


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://169.254.169.254/latest/meta-data",
        "https://alfabank.ru.evil.org/",
        "http://user:pass@cbr.ru/",
        "file:///etc/passwd",
        "https://cbr.ru:8443/",
        "http://[::1]/",
        "https://cbr.ru@evil.org/",
    ],
)
def test_ssrf_url_rejected(url):
    with pytest.raises(ServiceError, match="UNSAFE_URL"):
        URLPolicy(["alfabank.ru", "cbr.ru"]).check(url)


async def test_dns_private_and_mixed_answers_rejected(monkeypatch):
    async def lookup(*args, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443))
            for ip in ("8.8.8.8", "127.0.0.1")
        ]

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", lookup)
    with pytest.raises(ServiceError, match="UNSAFE_DNS_ADDRESS"):
        await URLPolicy(["cbr.ru"]).resolve("cbr.ru", 443)


async def test_pinned_ip_tls_host_and_unsafe_redirect(monkeypatch):
    policy = URLPolicy(["cbr.ru"])

    async def resolve(*args):
        return "8.8.8.8"

    policy.resolve = resolve
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )

    async def sync(fn):
        return fn()

    with pytest.raises(ServiceError, match="UNSAFE_URL"):
        await SafePageReader(policy, sync).read("https://cbr.ru/some")
    assert len(seen) == 1
    assert seen[0].url.host == "8.8.8.8"
    assert seen[0].headers["host"] == "cbr.ru"
    assert seen[0].extensions["sni_hostname"] == b"cbr.ru"


@pytest.mark.parametrize(
    "mime,body,error",
    [
        ("application/pdf", b"%PDF-", "WEB_CONTENT_TYPE_UNSUPPORTED"),
        ("text/plain", b"x" * (5 * 1024 * 1024 + 1), "WEB_PAGE_TOO_LARGE"),
    ],
    ids=["pdf-not-supported", "oversized-response"],
)
async def test_web_type_and_size_limit(monkeypatch, mime, body, error):
    policy = URLPolicy(["cbr.ru"])

    async def resolve(*args):
        return "8.8.8.8"

    policy.resolve = resolve
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: real_client(
            transport=httpx.MockTransport(
                lambda req: httpx.Response(200, content=body, headers={"content-type": mime})
            ),
            **kwargs,
        ),
    )

    async def sync(fn):
        return fn()

    with pytest.raises(ServiceError, match=error):
        await SafePageReader(policy, sync).read("https://cbr.ru")


def test_web_candidate_workflow_and_exact_snapshot(client, llm, kb):
    llm.replies.append(Completion(calls=[call("search_web", {"query": "МСП"})]))
    llm.replies.append(Completion(calls=[call("read_web_page", {"result_id": "result-one"})]))

    def propose(messages):
        tool = json.loads([m for m in messages if m["role"] == "tool"][-1]["content"])
        return Completion(
            calls=[call("propose_knowledge_save", {"candidate_id": tool["candidate_id"]})]
        )

    llm.replies.append(propose)

    def cite_page(messages):
        tools = [json.loads(m["content"]) for m in messages if m["role"] == "tool"]
        cid = next(t["candidate_id"] for t in tools if "candidate_id" in t)
        return Completion(
            json.dumps({"answer": "Материал Банка России прочитан.", "citation_ids": [cid]})
        )

    llm.replies.append(cite_page)
    sid, auth = open_session(client)
    response = send(client, sid, auth, "Найди источник и предложи сохранить").json()
    assert len(response["pending_actions"]) == 1
    assert response["citations"][0]["type"] == "WEB"
    action = response["pending_actions"][0]
    assert kb.repo.versions() == []
    admin = {"X-Admin-Key": "test-admin"}
    path = f"/v1/admin/web-candidates/{action['candidate_id']}"
    candidate = client.get(path, headers=admin).json()
    confirm = {"sha256": "0" * 64, "attribution": "Банк России", "allowed_use": "Тестирование"}
    assert client.post(path + "/confirm", json=confirm).status_code == 401
    assert client.post(path + "/confirm", headers=admin, json=confirm).status_code == 409
    confirm["sha256"] = action["sha256"]
    published = client.post(path + "/confirm", headers=admin, json=confirm)
    assert published.status_code == 200
    assert published.json()["sha256"] == candidate["sha256"]
    assert client.post(path + "/confirm", headers=admin, json=confirm).json() == published.json()
    v = kb.repo.versions()[0]
    assert v["text"] == candidate["text"] and v["state"] == "PUBLISHED"
    assert client.delete(f"/v1/sessions/{sid}", headers=auth).status_code == 200
    assert kb.repo.versions()[0]["state"] == "PUBLISHED"


def test_pending_candidates_deleted_on_close_and_restart(client, kb):
    sid, auth = open_session(client)
    c = kb.repo.candidate_create(sid, "title", "https://cbr.ru", "text")
    client.delete(f"/v1/sessions/{sid}", headers=auth)
    with pytest.raises(ServiceError, match="CANDIDATE_NOT_FOUND"):
        kb.repo.candidate(c["id"])
    c = kb.repo.candidate_create("lost-session", "title", "https://cbr.ru", "text")
    kb.repo.cleanup_candidates()
    with pytest.raises(ServiceError, match="CANDIDATE_NOT_FOUND"):
        kb.repo.candidate(c["id"])


def test_explicit_web_citation_survives_full_rag_budget(client, kb, llm, meta):
    for i in range(5):
        v = kb.ingest(f"Источник материалов для бизнеса номер {i}.".encode(), "a.txt", meta)
        kb.publish(v["document_id"], v["version"])
    assert len(kb.search("источник")) == 5
    llm.replies.append(Completion(calls=[call("search_web", {"query": "источник"})]))
    llm.replies.append(Completion(calls=[call("read_web_page", {"result_id": "result-one"})]))

    def cite(messages):
        result = json.loads([m["content"] for m in messages if m["role"] == "tool"][-1])
        return Completion(
            json.dumps(
                {"answer": "Прочитанный веб-источник.", "citation_ids": [result["candidate_id"]]}
            )
        )

    llm.replies.append(cite)
    sid, auth = open_session(client)
    response = send(client, sid, auth, "источник").json()
    assert response["status"] == "ANSWER"
    assert response["citations"][0]["type"] == "WEB"


@pytest.mark.parametrize(
    "amount,rate,months,expected",
    [
        ("12000", "0", 12, "1000.00"),
        ("1000000", "12", 12, "88848.79"),
        ("1", "0", 3, "0.33"),
        ("100", "0", 1, "100.00"),
    ],
)
def test_annuity(amount, rate, months, expected):
    result = annuity(AnnuityArgs(amount=amount, annual_rate=rate, months=months))
    assert result["payment_rub"] == expected
    assert Decimal(result["payment_rub"]) > 0


@pytest.mark.parametrize(
    "args",
    [
        {"amount": 0, "annual_rate": 12, "months": 12},
        {"amount": 1000, "annual_rate": -1, "months": 12},
        {"amount": "NaN", "annual_rate": 12, "months": 12},
        {"amount": 1000, "annual_rate": 12, "months": 1.5},
        {"amount": 1000, "annual_rate": 12, "months": True},
    ],
)
def test_annuity_validation(args):
    with pytest.raises(ValidationError):
        AnnuityArgs(**args)


@pytest.mark.parametrize(
    "status,code",
    [(401, "LLM_UNAUTHORIZED"), (404, "LLM_MODEL_UNAVAILABLE"), (429, "LLM_RATE_LIMITED")],
)
async def test_real_sdk_error_mapping_no_retry(settings, status, code):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"error": {"message": "secret upstream details"}})

    adapter = OpenAICompatibleLLM(settings)
    await adapter.client.close()
    adapter.client = AsyncOpenAI(
        api_key="secret",
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(ServiceError, match=code):
        await adapter.complete([{"role": "user", "content": "test"}], [], {"model": "test"})
    assert len(calls) == 1
    await adapter.close()


async def test_sdk_filters_reasoning_and_disables_it(settings):
    payloads = []

    def handler(request):
        payloads.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "x",
                "object": "chat.completion",
                "created": 1,
                "model": "qwen",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": '<think>private</think>{"answer":"ok"}',
                            "reasoning_content": "private",
                            "reasoning_details": [{"text": "private"}],
                        },
                    }
                ],
                "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
            },
        )

    adapter = OpenAICompatibleLLM(settings)
    await adapter.client.close()
    adapter.client = AsyncOpenAI(
        api_key="secret",
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    result = await adapter.complete([{"role": "user", "content": "test"}], [], {"model": "qwen"})
    assert "private" not in str(result)
    assert payloads[0]["reasoning"]["enabled"] is False
    assert result.input_tokens == 2
    await adapter.close()


def test_logging_allowlist():
    record = logging.LogRecord(
        "alfa_assistant.agent", logging.INFO, "", 1, "turn_complete", (), None
    )
    record.api_key = "SECRET"
    record.document = "PRIVATE DOCUMENT"
    record.reasoning_content = "PRIVATE REASONING"
    record.request_id = "request"
    rendered = SafeJSONFormatter().format(record)
    assert "SECRET" not in rendered and "PRIVATE" not in rendered
    assert json.loads(rendered)["request_id"] == "request"


async def test_search_outage_is_not_reported_as_empty_search(monkeypatch):
    real_client = httpx.AsyncClient
    payload = {
        "results": [],
        "unresponsive_engines": [["duckduckgo", "timeout"], ["bing", "timeout"]],
    }
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: real_client(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, json=payload)), **kwargs
        ),
    )
    search = SearxngSearch("http://searxng:8080", URLPolicy(["cbr.ru"]))
    with pytest.raises(ServiceError, match="WEB_ENGINES_UNAVAILABLE"):
        await search.search("МСП")
    payload["unresponsive_engines"] = []
    assert await search.search("МСП") == []
