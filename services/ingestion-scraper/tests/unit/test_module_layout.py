import dataclasses
import inspect


def test_kafka_producer_client_is_importable_from_messaging() -> None:
    from auspex_ingest.messaging import KafkaProducerClient
    assert inspect.isclass(KafkaProducerClient)


def test_rate_limited_client_is_importable_from_connectors() -> None:
    from auspex_ingest.connectors import RateLimitedClient
    assert inspect.isclass(RateLimitedClient)


def test_run_result_is_importable_from_pipeline() -> None:
    from auspex_ingest.pipeline import RunResult
    assert dataclasses.is_dataclass(RunResult)


def test_models_module_contains_only_domain_models() -> None:
    import auspex_ingest.models as m
    assert hasattr(m, "RawDocument")
    assert hasattr(m, "ResearchSignalEvent")
    assert not hasattr(m, "RunResult")
