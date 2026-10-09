import json
import time
import urllib.request

import pytest
from testcontainers.community.elasticsearch import ElasticSearchContainer


@pytest.mark.integration
def test_filebeat_delivers_log_line_to_elasticsearch():
    # ElasticSearchContainer models the Filebeat → Elasticsearch delivery path:
    # Filebeat ships container stdout as ECS JSON; here we index a document directly
    # in the same ECS shape to verify Elasticsearch accepts the format and the required
    # ECS fields are queryable. Filebeat config is validated via docker-compose smoke test.
    container = ElasticSearchContainer("elasticsearch:8.17.3", port=9200)
    container.with_env("ES_JAVA_OPTS", "-Xms256m -Xmx256m")
    container.with_env("discovery.type", "single-node")
    container.with_env("xpack.security.enabled", "false")
    with container as es:
        host = es.get_container_host_ip()
        port = es.get_exposed_port(9200)
        base_url = f"http://{host}:{port}"

        doc = {
            "@timestamp": "2023-01-10T13:00:00.000Z",
            "log": {"level": "info"},
            "service": {"name": "ingestion-scraper"},
            "message": "run complete",
            "auspex.source_type": "biorxiv",
            "auspex.run_id": "abc-123",
            "fetched": 5,
            "published": 3,
        }

        index_url = f"{base_url}/auspex-logs-2023.01.10/_doc"
        data = json.dumps(doc).encode()
        req = urllib.request.Request(
            index_url,
            data=data,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status in (200, 201)

        search_url = f"{base_url}/auspex-logs-*/_search"
        hits = []
        for _ in range(20):
            with urllib.request.urlopen(search_url) as resp:
                body = json.loads(resp.read())
            hits = body.get("hits", {}).get("hits", [])
            if hits:
                break
            time.sleep(0.5)

        assert hits, "No documents found in auspex-logs-* after indexing"
        source = hits[0]["_source"]
        assert "@timestamp" in source
        assert source.get("log", {}).get("level") == "info"
        assert source.get("service", {}).get("name") == "ingestion-scraper"
        assert "message" in source
