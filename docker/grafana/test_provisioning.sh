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
echo "$response" | grep -q '"title":"Auspex Infrastructure"' || fail "Auspex Infrastructure dashboard not found"
for uid in auspex-pipeline auspex-operations auspex-errors auspex-infrastructure; do
  curl -sf -u "${AUTH}" "${GRAFANA_URL}/api/dashboards/uid/${uid}" | grep -q '"gridPos"' \
    || fail "dashboard ${uid} has no panels"
done
echo "   PASS"

echo "4. Alert rules provisioned..."
response=$(curl -sf -u "${AUTH}" "${GRAFANA_URL}/api/ruler/grafana/api/v1/rules")
echo "$response" | grep -q '"title":"DLT Backlog"' || fail "DLT Backlog alert rule not found"
echo "$response" | grep -q '"title":"Source Silence"' || fail "Source Silence alert rule not found"
echo "$response" | grep -q '"title":"Kafka Lag Critical"' || fail "Kafka Lag Critical alert rule not found"
echo "$response" | grep -q '"title":"Scrape Target Down"' || fail "Scrape Target Down alert rule not found"
echo "$response" | grep -q '"title":"LLM Extraction Errors"' || fail "LLM Extraction Errors alert rule not found"
for title in "Probe Target Down" "Mac Host Exporter Down" "Docker Disk Low" "Mac Disk Low" \
  "VM Memory High" "Container Restarting" "Airflow DAG Run Failed" "Price Refresh Stale" \
  "Ollama Down During Extraction"; do
  echo "$response" | grep -q "\"title\":\"${title}\"" || fail "${title} alert rule not found"
done
echo "   PASS"

echo "5. Prometheus reachable through Grafana..."
response=$(curl -sf -u "${AUTH}" "${GRAFANA_URL}/api/datasources/uid/prometheus/resources/api/v1/query?query=up")
echo "$response" | grep -q '"status":"success"' || fail "Prometheus query via Grafana proxy failed"
echo "   PASS"

echo "6. Contact point and notification policy provisioned..."
response=$(curl -sf -u "${AUTH}" "${GRAFANA_URL}/api/v1/provisioning/contact-points")
echo "$response" | grep -q '"name":"auspex-default"' || fail "contact point auspex-default not found"
response=$(curl -sf -u "${AUTH}" "${GRAFANA_URL}/api/v1/provisioning/policies")
echo "$response" | grep -q '"receiver":"auspex-default"' || fail "default policy does not route to auspex-default"
echo "   PASS"

# Instant queries through Grafana's Prometheus proxy; an empty result means nothing is down.
query() {
  curl -sf -G -u "${AUTH}" "${GRAFANA_URL}/api/datasources/uid/prometheus/resources/api/v1/query" \
    --data-urlencode "query=$1"
}

echo "7. Every Prometheus target up (mac-host may be down)..."
response=$(query 'up{job!="mac-host"} == 0')
echo "$response" | grep -q '"result":\[\]' || fail "scrape targets down: ${response}"
echo "   PASS"

echo "8. Every health probe succeeds (Ollama may be stopped)..."
response=$(query 'probe_success{job!="blackbox-ollama"} == 0')
echo "$response" | grep -q '"result":\[\]' || fail "probes failing: ${response}"
response=$(query 'count(probe_success)')
echo "$response" | grep -q '"value":\[[0-9.]*,"[1-9]' || fail "no probe results yet"
echo "   PASS"

echo "9. Exporters reach their datastores..."
for expr in 'pg_up' 'kafka_brokers' 'elasticsearch_cluster_health_up' 'count(container_memory_working_set_bytes)' 'count(auspex_volume_bytes)'; do
  response=$(query "${expr}")
  echo "$response" | grep -q '"value":\[[0-9.]*,"[1-9]' || fail "${expr} is missing or zero: ${response}"
done
echo "   PASS"

echo "=== All assertions passed ==="
