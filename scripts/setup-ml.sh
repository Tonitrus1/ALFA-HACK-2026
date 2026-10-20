#!/bin/sh
# Initial preparation requires network; later startup uses only installed local artifacts.
set -eu
cd "$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)"
[ "$(uname -s)" = Darwin ] && [ "$(uname -m)" = arm64 ] || { echo 'Native setup is verified for macOS arm64. For another host supply Python 3.12/PostgreSQL 17 and adapt the launcher.'; exit 1; }
PYTHON_BIN=${PYTHON_BIN:-python3.12}
[ -d .venv ] || "$PYTHON_BIN" -m venv .venv
.venv/bin/pip install -r ml/requirements.lock.txt
mkdir -p .local/tools
if [ ! -x .local/tools/pg/bin/postgres ]; then
 curl -fL --retry 2 https://ftp.postgresql.org/pub/source/v17.5/postgresql-17.5.tar.gz -o .local/tools/postgres.tar.gz
 .venv/bin/python - <<'PY'
import hashlib
from pathlib import Path
p=Path('.local/tools/postgres.tar.gz')
assert hashlib.sha256(p.read_bytes()).hexdigest()=='730bfef34b03825c051ae0fc37542c8be26b55a44e472369221afd397196e303','PostgreSQL archive checksum mismatch'
PY
 tar -xzf .local/tools/postgres.tar.gz -C .local/tools
 (cd .local/tools/postgresql-17.5 && ./configure --prefix="$PWD/../pg" --without-icu --without-readline --without-zlib && make -j4 && make install) > .local/postgres-build.log 2>&1
fi
./scripts/demo migrate
printf '%s\n' 'Prepared. Next: ./scripts/demo train --dataset /absolute/path/to/ru-sme-dataset-10000' 'Then: ./scripts/demo up --offline'
