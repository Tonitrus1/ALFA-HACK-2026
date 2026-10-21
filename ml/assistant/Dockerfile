FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c AS builder
COPY --from=ghcr.io/astral-sh/uv:0.9.5@sha256:f459f6f73a8c4ef5d69f4e6fbbdb8af751d6fa40ec34b39a1ab469acd6e289b7 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1 \
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --extra models --no-install-project --no-dev
COPY . .
RUN uv sync --frozen --extra models --no-dev

FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
ENV PYTHONUNBUFFERED=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
    PATH="/app/.venv/bin:$PATH"
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY . .
RUN useradd --uid 10001 --create-home assistant && \
    mkdir -p data model-cache reports && chown assistant:assistant data model-cache reports
USER assistant
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn alfa_assistant.main:app --host 0.0.0.0 --port 8000 --workers 1 --no-access-log"]
