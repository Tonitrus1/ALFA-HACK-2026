#!/usr/bin/env python3
"""Generate local credentials once, without printing secrets or overwriting configuration."""
import os
import secrets
from pathlib import Path
root=Path(__file__).resolve().parents[2]
target=root/'.env'
if target.exists():
    raise SystemExit('.env already exists; preserved. Compare required keys with .env.example.')
fd=os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
with os.fdopen(fd,'w') as stream:
    for key in ('BACKEND_DB_PASSWORD','ML_ADMIN_PASSWORD','ML_DB_PASSWORD','ML_SERVICE_TOKEN','ASSISTANT_SERVICE_TOKEN','OCR_API_KEY','DOCUMENT_OCR_TOKEN','SEARXNG_SECRET'):
        stream.write(key+'='+secrets.token_urlsafe(36)+'\n')
    stream.write('\nLLM_API_KEY=\nLLM_BASE_URL=https://api.aitunnel.ru/v1\nASSISTANT_LLM_MODEL=qwen3-30b-a3b\nOCR_LLM_MODEL=deepseek-v4.1-flash-1017\n')
print('Created private .env. No credentials were printed.')
