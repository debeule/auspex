#!/bin/sh
# Creates or updates the read-only role postgres-exporter logs in with. Runs on every `up`, so a
# volume initialised before this role existed gets it too, and a changed password is applied.
set -eu

psql -v ON_ERROR_STOP=1 \
  -v role="$POSTGRES_MONITOR_USER" -v password="$POSTGRES_MONITOR_PASSWORD" <<'EOSQL'
SELECT format('CREATE ROLE %I LOGIN', :'role')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'role')
\gexec
ALTER ROLE :"role" WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'password';
GRANT pg_monitor TO :"role";
EOSQL

echo "Monitoring role ${POSTGRES_MONITOR_USER} ready."
