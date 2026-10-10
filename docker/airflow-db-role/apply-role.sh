#!/bin/sh
# Applies AIRFLOW_DB_PASSWORD to the Airflow metadata role on every `up`, creating the role if it
# is missing. postgres-init/01_airflow.sh runs only on an empty volume, so without this a password
# changed in .env would lock Airflow out of an existing database.
set -eu

psql -v ON_ERROR_STOP=1 \
  -v role="$AIRFLOW_DB_USER" -v password="$AIRFLOW_DB_PASSWORD" <<'EOSQL'
SELECT format('CREATE ROLE %I LOGIN', :'role')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'role')
\gexec
ALTER ROLE :"role" WITH LOGIN PASSWORD :'password';
EOSQL

echo "Airflow database role ${AIRFLOW_DB_USER} ready."
