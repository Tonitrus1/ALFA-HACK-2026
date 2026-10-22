#!/bin/sh
# Runs as ML DB owner during deployment, never as the runtime principal.
set -eu
export PGPASSWORD="$ML_ADMIN_PASSWORD"
psql -h ml-db -U ml_admin -d credit_ml -v ON_ERROR_STOP=1 <<'SQL'
CREATE TABLE IF NOT EXISTS public.ml_deployment_migration(name text PRIMARY KEY,sha256 text NOT NULL);
SQL
for migration in /migrations/V3__*.sql; do
  name=$(basename "$migration")
  checksum=$(sha256sum "$migration" | cut -d ' ' -f 1)
  previous=$(psql -h ml-db -U ml_admin -d credit_ml -At -v ON_ERROR_STOP=1 -v name="$name" <<'SQL'
SELECT sha256 FROM public.ml_deployment_migration WHERE name=:'name';
SQL
)
  if [ -n "$previous" ]; then
    [ "$previous" = "$checksum" ] || { echo "Applied ML migration checksum changed: $name" >&2; exit 1; }
  else
    { echo BEGIN\;; cat "$migration"; printf "\nINSERT INTO public.ml_deployment_migration VALUES ('%s','%s');\nCOMMIT;\n" "$name" "$checksum"; } |
      psql -h ml-db -U ml_admin -d credit_ml -v ON_ERROR_STOP=1
  fi
done
