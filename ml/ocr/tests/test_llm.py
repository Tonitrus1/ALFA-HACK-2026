"""Provider protocol tests use HTTP doubles; no claims about a real LLM."""

import httpx
import pytest

from alfa_ocr.config import Settings
from alfa_ocr.contract import Contract
from alfa_ocr.llm import complete
from alfa_ocr.models import ServiceError


@pytest.mark.parametrize(
    "status,code",
    [(401, "LLM_UNAUTHORIZED"), (429, "LLM_RATE_LIMITED"), (500, "LLM_PROVIDER_ERROR")],
)
def test_provider_errors_are_sanitized(monkeypatch, status, code):
    original = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(status, text="SECRET DOCUMENT BODY")
            ),
            **kwargs,
        ),
    )
    with pytest.raises(ServiceError, match=code) as error:
        complete(Settings(llm_api_key="unit-key"), Contract("test", {}), [])
    assert "SECRET" not in str(error.value)


@pytest.mark.parametrize(
    "choice,code",
    [
        ({"finish_reason": "length", "message": {"content": "{}"}}, "LLM_INCOMPLETE_RESPONSE"),
        ({"finish_reason": "stop", "message": {"content": "not JSON"}}, "LLM_JSON_INVALID"),
        ({"finish_reason": "stop", "message": {"content": '{"value":NaN}'}}, "LLM_JSON_INVALID"),
        (
            {"finish_reason": "stop", "message": {"content": '{"key":1,"key":2}'}},
            "LLM_JSON_INVALID",
        ),
    ],
)
def test_invalid_output_is_not_success(monkeypatch, choice, code):
    original = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json={"choices": [choice]})
            ),
            **kwargs,
        ),
    )
    with pytest.raises(ServiceError, match=code):
        complete(Settings(llm_api_key="unit-key"), Contract("test", {}), [])


def test_context_limit_is_explicit():
    with pytest.raises(ServiceError, match="LLM_CONTEXT_LIMIT"):
        complete(
            Settings(llm_api_key="unit-key", max_context_chars=1000), Contract("x" * 1001, {}), []
        )


def test_local_qwen_uses_json_without_provider_extensions(monkeypatch):
    import json

    payloads = []
    original = httpx.Client

    def handler(request):
        assert str(request.url) == "http://ollama:11434/v1/chat/completions"
        payloads.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{
            "finish_reason": "stop", "message": {"content": '{"public":true}'},
        }]})

    monkeypatch.setattr(httpx, "Client", lambda **kwargs: original(
        transport=httpx.MockTransport(handler), **kwargs,
    ))
    settings = Settings(llm_api_key="ollama", llm_base_url="http://ollama:11434/v1",
                        llm_model="qwen2.5:3b", llm_reasoning_options=False,
                        llm_response_format="json_object")
    schema = {"type": "object", "properties": {"public": {"type": "boolean"}}}
    value, metadata = complete(settings, Contract("test", schema), [])
    assert value == {"public": True} and metadata["model"] == "qwen2.5:3b"
    assert payloads[0]["response_format"] == {"type": "json_object"}
    assert json.dumps(schema, ensure_ascii=False) in payloads[0]["messages"][0]["content"]
    assert "reasoning" not in payloads[0] and "chat_template_kwargs" not in payloads[0]


def test_compact_template_keeps_full_server_contract_and_context_accounting():
    import json
    from pathlib import Path

    from alfa_ocr.extraction import context_size
    from alfa_ocr.llm import generation_schema, system_prompt
    from alfa_ocr.models import Block, Page

    root = Path(__file__).resolve().parents[1]
    settings = Settings(llm_compact_schema=True, prompt_path=root / "prompts/extract.txt",
                        schema_path=root / "schemas/extraction.schema.json")
    contract = Contract.read(settings)
    original_hash = contract.fingerprint()
    pages = [Page(document_id="doc", page=1, width=10, height=10,
                  blocks=[Block(block_id="b1", text="ИНН 000000000001", confidence=1, bbox=[0, 0, 10, 10])])]
    schema = generation_schema(settings, contract)
    assert "allOf" not in schema["$defs"]["field"]
    assert schema["$defs"]["inn12"]["type"] == "object"
    assert contract.fingerprint() == original_hash
    assert "allOf" in contract.schema["$defs"]["inn12"]
    prompt = system_prompt(settings, contract, pages)
    assert '"document_id": "doc"' in prompt and '"status": "missing"' in prompt
    assert context_size(settings, contract, pages) == len(prompt) + len(json.dumps([p.model_dump() for p in pages], ensure_ascii=False))


def test_reasoning_not_retained(monkeypatch):
    original = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={
                        "choices": [
                            {
                                "finish_reason": "stop",
                                "message": {
                                    "content": '<think>private</think>{"public":true}',
                                    "reasoning": "private",
                                },
                            }
                        ],
                        "usage": {"prompt_tokens": 1},
                    },
                )
            ),
            **kwargs,
        ),
    )
    value, metadata = complete(Settings(llm_api_key="unit-key"), Contract("test", {}), [])
    assert value == {"public": True}
    assert "private" not in str(metadata)
