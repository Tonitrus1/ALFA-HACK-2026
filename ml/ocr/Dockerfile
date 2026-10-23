FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
COPY --from=ghcr.io/astral-sh/uv:0.9.5@sha256:f459f6f73a8c4ef5d69f4e6fbbdb8af751d6fa40ec34b39a1ab469acd6e289b7 /uv /usr/local/bin/uv
ENV PYTHONUNBUFFERED=1 UV_LINK_MODE=copy PATH="/app/.venv/bin:$PATH" \
    HOME=/home/ocr PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True \
    OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libgomp1 libgl1 tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
ENV UV_HTTP_TIMEOUT=600 UV_CONCURRENT_DOWNLOADS=4
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/home/ocr/.cache/uv uv sync --frozen --extra test --no-install-project
# Paddle has its own CPU thread budget; keep BLAS/OpenMP serial.
ENV OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
COPY src/alfa_ocr/engines.py src/alfa_ocr/models.py src/alfa_ocr/__init__.py ./src/alfa_ocr/
COPY scripts/prepare_models.py ./scripts/prepare_models.py
COPY schemas/model-hashes.json ./schemas/model-hashes.json
RUN useradd --uid 10002 --create-home ocr \
    && mkdir -p data reports fixtures/generated \
    && chown ocr:ocr /app /app/data /app/reports /app/fixtures /app/fixtures/generated \
    && chown -R ocr:ocr /home/ocr
USER ocr
ENV PYTHONPATH=/app/src
# Download real CPU weights at build time; runtime can start without model network.
RUN python scripts/prepare_models.py
COPY --chown=ocr:ocr . .
EXPOSE 8001
CMD ["uvicorn", "alfa_ocr.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1", "--no-access-log", "--log-level", "warning"]
