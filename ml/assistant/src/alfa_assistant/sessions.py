import hashlib
import secrets
import time
from dataclasses import dataclass, field
from uuid import uuid4

from .errors import ServiceError


@dataclass
class Session:
    id: str
    token_hash: str
    user_id: str
    company_id: str
    prompt: str
    prompt_hash: str
    parameters: dict
    created_at: float
    last_activity: float
    busy: bool = False
    turns: list[list[dict]] = field(default_factory=list)
    turn_versions: list[set[str]] = field(default_factory=list)
    completed: dict = field(default_factory=dict)
    results: dict = field(default_factory=dict)
    usage: dict = field(default_factory=lambda: {"input_tokens": 0, "output_tokens": 0})


class MemorySessionStore:
    """All methods run on the single event loop; no await between check and mutation."""

    def __init__(self, ttl=3600, maximum=100, clock=time.time):
        self.ttl, self.maximum, self.clock = ttl, maximum, clock
        self.sessions: dict[str, Session] = {}

    def expired_ids(self):
        now = self.clock()
        return [
            s.id for s in self.sessions.values() if not s.busy and now - s.last_activity >= self.ttl
        ]

    def create(self, user_id, company_id, prompt, parameters):
        if len(self.sessions) >= self.maximum:
            raise ServiceError("SESSION_CAPACITY", 503)
        token = secrets.token_urlsafe(32)
        now = self.clock()
        session = Session(
            str(uuid4()),
            hashlib.sha256(token.encode()).hexdigest(),
            user_id,
            company_id,
            prompt,
            hashlib.sha256(prompt.encode()).hexdigest(),
            parameters,
            now,
            now,
        )
        self.sessions[session.id] = session
        return session, token

    def get(self, session_id, token):
        s = self.sessions.get(session_id)
        if not s or not secrets.compare_digest(
            s.token_hash, hashlib.sha256(token.encode()).hexdigest()
        ):
            raise ServiceError("SESSION_NOT_FOUND", 404)
        if not s.busy and self.clock() - s.last_activity >= self.ttl:
            raise ServiceError("SESSION_EXPIRED", 404)
        s.last_activity = self.clock()
        return s

    def close(self, session_id, token):
        s = self.get(session_id, token)
        if s.busy:
            raise ServiceError("SESSION_BUSY", 409)
        del self.sessions[session_id]
