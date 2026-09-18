from prometheus_client import REGISTRY, CollectorRegistry, Counter, Gauge, Histogram


def make_metrics(registry: CollectorRegistry | None = None) -> dict:
    r = registry if registry is not None else REGISTRY
    return {
        "documents_fetched": Counter(
            "auspex_pipeline_documents_fetched_total",
            "Documents fetched per source run",
            ["source_type"],
            registry=r,
        ),
        "signals_published": Counter(
            "auspex_pipeline_signals_published_total",
            "Signals published to Kafka per source",
            ["source_type"],
            registry=r,
        ),
        "llm_calls": Counter(
            "auspex_llm_extraction_calls_total",
            "LLM extraction call outcomes by source and result",
            ["source_type", "result"],
            registry=r,
        ),
        "run_duration": Histogram(
            "auspex_pipeline_run_duration_seconds",
            "Wall-clock duration of a full pipeline run",
            ["source_type"],
            buckets=[30, 60, 120, 300, 600, 1800, 3600],
            registry=r,
        ),
        "run_last_timestamp": Gauge(
            "auspex_pipeline_run_last_timestamp",
            "Unix timestamp of the last successful pipeline run",
            ["source_type"],
            registry=r,
        ),
    }
