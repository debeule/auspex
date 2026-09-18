#!/bin/sh
set -e

GRAFANA_URL="${GRAFANA_URL:-http://localhost:3000}"
GRAFANA_ADMIN_PASSWORD="${GRAFANA_ADMIN_PASSWORD:-admin}"
AUTH="admin:${GRAFANA_ADMIN_PASSWORD}"

fail() {
  echo "FAIL: $1" >&2
  exit 1
}

echo "=== Grafana provisioning smoke tests ==="

echo "1. Health check..."
response=$(curl -sf "${GRAFANA_URL}/api/health")
echo "$response" | grep -q '"database"' || fail "/api/health did not return database:ok"
echo "$response" | grep -q '"ok"' || fail "/api/health database is not ok"
echo "   PASS"

echo "2. Datasources provisioned..."
response=$(curl -sf -u "${AUTH}" "${GRAFANA_URL}/api/datasources")
echo "$response" | grep -q '"name":"Prometheus"' || fail "Prometheus datasource not found"
echo "$response" | grep -q '"name":"Elasticsearch"' || fail "Elasticsearch datasource not found"
echo "   PASS"

echo "3. Dashboards provisioned..."
response=$(curl -sf -u "${AUTH}" "${GRAFANA_URL}/api/search?type=dash-db&query=Auspex")
echo "$response" | grep -q '"title":"Auspex Operations"' || fail "Auspex Operations dashboard not found"
echo "$response" | grep -q '"title":"Auspex Pipeline"' || fail "Auspex Pipeline dashboard not found"
echo "$response" | grep -q '"title":"Auspex Error Drill-Down"' || fail "Auspex Error Drill-Down dashboard not found"
echo "   PASS"

echo "4. Alert rules provisioned..."
response=$(curl -sf -u "${AUTH}" "${GRAFANA_URL}/api/ruler/grafana/api/v1/rules")
echo "$response" | grep -q '"title":"DLT Backlog"' || fail "DLT Backlog alert rule not found"
echo "$response" | grep -q '"title":"Source Silence"' || fail "Source Silence alert rule not found"
echo "$response" | grep -q '"title":"Kafka Lag Critical"' || fail "Kafka Lag Critical alert rule not found"
echo "   PASS"

echo "5. Prometheus reachable through Grafana..."
response=$(curl -sf -u "${AUTH}" "${GRAFANA_URL}/api/datasources/uid/prometheus/resources/api/v1/query?query=up")
echo "$response" | grep -q '"status":"success"' || fail "Prometheus query via Grafana proxy failed"
echo "   PASS"

echo "=== All assertions passed ==="
