#!/bin/sh
set -eu
python - <<'PYWAIT'
import os,time,urllib.request
for service in ('QDRANT_URL','SEARXNG_URL'):
    suffix='/readyz' if service=='QDRANT_URL' else '/healthz'
    for attempt in range(60):
        try:
            urllib.request.urlopen(os.environ[service]+suffix,timeout=3)
            break
        except OSError:
            if attempt==59:raise
            time.sleep(2)
PYWAIT
alembic upgrade head
# One process owns this data volume. Seed only once; explicit reindex remains available.
if [ ! -f /app/data/.seeded-v1 ]; then
    python -c 'from alfa_assistant.cli import main; main()' seed
    touch /app/data/.seeded-v1
fi
exec uvicorn alfa_assistant.main:app --host 0.0.0.0 --port 8000 --workers 1 --no-access-log
