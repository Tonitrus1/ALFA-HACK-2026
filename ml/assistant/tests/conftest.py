import hashlib
import json
import re
from collections import deque

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from alfa_assistant.api import create_app
from alfa_assistant.config import Settings
from alfa_assistant.llm import Completion
from alfa_assistant.rag import KnowledgeService
from alfa_assistant.schemas import Metadata
from alfa_assistant.storage import Base, SQLiteKnowledgeRepository


class TestTokenizer:
    def encode(self, text, **kwargs):
        return list(text.encode())

    def decode(self, ids):
        return bytes(ids).decode(errors="ignore")


class TestEncoder:
    chunk_tokenizer = TestTokenizer()

    def encode(self, texts, query=False):
        vectors = []
        for text in texts:
            v = [0.0] * 384
            for word in re.findall(r"\w+", text.lower()):
                v[int(hashlib.sha256(word.encode()).hexdigest(), 16) % 384] += 1
            norm = sum(x * x for x in v) ** 0.5 or 1
            vectors.append([x / norm for x in v])
        return vectors

    def count(self, text):
        return max(1, len(text) // 4)

    def count_messages(self, messages, tools):
        return self.count(json.dumps([messages, tools], ensure_ascii=False))


class TestIndex:
    __test__ = False

    def __init__(self):
        self.points = {}
        self.fail = False

    def reset(self):
        self.points.clear()

    def upsert(self, chunks, vectors):
        if self.fail:
            raise ConnectionError()
        for c, v in zip(chunks, vectors, strict=True):
            self.points[c["id"]] = (c, v)

    def search(self, vector, active_ids):
        return sorted(
            [
                (cid, sum(x * y for x, y in zip(vector, v, strict=True)))
                for cid, (c, v) in self.points.items()
                if c["version_id"] in active_ids
            ],
            key=lambda r: r[1],
            reverse=True,
        )[:10]


class TestLLM:
    def __init__(self):
        self.replies = deque()
        self.requests = []

    async def complete(self, messages, tools, parameters):
        self.requests.append(messages)
        reply = (
            self.replies.popleft()
            if self.replies
            else Completion(
                '{"status":"ANSWER","answer":"Привет","citation_ids":[]}',
                input_tokens=10,
                output_tokens=5,
            )
        )
        if isinstance(reply, Exception):
            raise reply
        if callable(reply):
            reply = reply(messages)
            if hasattr(reply, "__await__"):
                reply = await reply
        return reply


class TestSearch:
    async def search(self, query):
        return [
            {
                "result_id": "result-one",
                "url": "https://cbr.ru/develop/msp/",
                "title": "Поддержка МСП",
                "snippet": "snippet only",
                "is_read": False,
            }
        ]


class TestReader:
    async def read(self, url):
        return {
            "url": url,
            "text": "Проверенный снимок поддержки предпринимателей и финансирования.",
        }


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None,
        admin_api_key=SecretStr("test-admin"),
        llm_api_key=SecretStr("test-llm-secret"),
        data_dir=tmp_path,
        database_url="sqlite:///" + str(tmp_path / "knowledge.sqlite3"),
    )


@pytest.fixture
def kb(settings):
    repo = SQLiteKnowledgeRepository(settings.database_url, settings.data_dir)
    Base.metadata.create_all(repo.engine)
    k = KnowledgeService(repo, TestIndex(), TestEncoder(), settings)
    k.reconcile()
    return k


@pytest.fixture
def llm():
    return TestLLM()


@pytest.fixture
def app(settings, kb, llm):
    return create_app(settings, knowledge=kb, llm=llm, web_search=TestSearch(), reader=TestReader())


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def meta():
    return Metadata(
        title="Оборотный",
        attribution="Автор теста",
        allowed_use="Тест",
        source_type="PUBLIC_NOTE",
        source_url="https://cbr.ru/develop/msp/",
        is_synthetic=False,
    ).model_dump(mode="json")


def open_session(client):
    response = client.post("/v1/sessions", json={})
    assert response.status_code == 201, response.text
    s = response.json()
    return s["session_id"], {"Authorization": "Bearer " + s["session_token"]}


def send(client, sid, headers, message="Привет", cid="one"):
    return client.post(
        f"/v1/sessions/{sid}/messages",
        headers=headers,
        json={"message": message, "client_message_id": cid},
    )


def call(name, arguments=None, cid="call1"):
    return {
        "id": cid,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments or {})},
    }
