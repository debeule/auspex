from typing import Any
from weakref import WeakKeyDictionary

from prometheus_client import REGISTRY, CollectorRegistry, Counter, Gauge, Histogram

# The API builds a pipeline per request; collectors must be registered once per registry.
_by_registry: WeakKeyDictionary[CollectorRegistry, dict[str, Any]] = WeakKeyDictionary()


def make_metrics(registry: CollectorRegistry | None = None) -> dict[str, Any]:
    r = registry if registry is not None else REGISTRY
    existing = _by_registry.get(r)
    if existing is not None:
        return existing
    metrics = _build(r)
    _by_registry[r] = metrics
    return metrics


def _build(r: CollectorRegistry) -> dict[str, Any]:
    return {
        "documents_fetched": Counter(
            "auspex_pipeline_documents_fetched_total",
            "Documents fetched per source run",
            ["source_type"],
            registry=r,
        ),
        "documents_failed": Counter(
            "auspex_pipeline_documents_failed_total",
            "Documents that raised during archive, extraction or publish",
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
        "llm_duration": Histogram(
            "auspex_llm_extraction_duration_seconds",
            "Wall-clock latency of one LLM extraction call",
            ["source_type"],
            buckets=[0.5, 1, 2, 5, 10, 20, 30, 60, 120, 300],
            registry=r,
        ),
        "run_duration": Histogram(
            "auspex_pipeline_run_duration_seconds",
            "Wall-clock duration of a full pipeline run",
            ["source_type"],
            buckets=[30, 60, 120, 300, 600, 1800, 3600, 7200, 14400],
            registry=r,
        ),
        "run_last_timestamp": Gauge(
            "auspex_pipeline_run_last_timestamp",
            "Unix timestamp of the last successful pipeline run",
            ["source_type"],
            registry=r,
        ),
    }
