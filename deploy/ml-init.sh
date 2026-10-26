#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set=runtime_password="$ML_DB_PASSWORD" <<'SQL'
CREATE ROLE ml_runtime LOGIN PASSWORD :'runtime_password';
SQL
for migration in /migrations/V1__*.sql /migrations/V2__*.sql; do
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --file "$migration"
done
