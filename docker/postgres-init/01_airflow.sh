#!/bin/bash
set -e

# Creates the airflow database and role, isolated from the application database.
# Runs as the Docker-provisioned superuser (POSTGRES_USER) during init.

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-EOSQL
    CREATE ROLE "${AIRFLOW_DB_USER}" WITH LOGIN PASSWORD '${AIRFLOW_DB_PASSWORD}';
    CREATE DATABASE airflow OWNER "${AIRFLOW_DB_USER}";
    REVOKE ALL ON DATABASE airflow FROM PUBLIC;
    GRANT CONNECT ON DATABASE airflow TO "${AIRFLOW_DB_USER}";
EOSQL

echo "Airflow database and role created."
