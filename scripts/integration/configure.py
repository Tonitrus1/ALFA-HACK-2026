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
    for key in ('BACKEND_DB_PASSWORD','ML_ADMIN_PASSWORD','ML_DB_PASSWORD','ML_SERVICE_TOKEN'):
        stream.write(key+'='+secrets.token_urlsafe(36)+'\n')
print('Created private .env. No credentials were printed.')
