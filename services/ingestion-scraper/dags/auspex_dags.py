"""Airflow DAG entry point — thin wrapper around dag_factory.

Loaded by Airflow's DAG discovery. Imports Airflow at module level.
All ingestion logic lives in auspex_ingest.dag_factory, not here.
"""
from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

from airflow import DAG  # type: ignore[import-untyped]
from airflow.operators.python import PythonOperator  # type: ignore[import-untyped]

from auspex_ingest.dag_factory import build_dags, load_sources_config
from auspex_ingest.pipeline import IngestionPipeline

_CONFIG_PATH = Path(os.environ.get("AUSPEX_SOURCES_YAML", "/opt/airflow/config/sources.yaml"))
_REGISTRY: dict[str, type] = {}

try:
    from auspex_ingest.connectors.mock import MockConnector
    _REGISTRY["mock"] = MockConnector
except ImportError:
    pass


def _pipeline_factory(entry):  # type: ignore[no-untyped-def]
    import instructor
    import openai
    from confluent_kafka import Producer as ConfluentProducer
    from minio import Minio

    from auspex_ingest.extractor import LLMExtractor
    from auspex_ingest.kafka_producer import KafkaProducerClient
    from auspex_ingest.normalizer import IdentityNormalizer
    from auspex_ingest.prefilter import Prefilter
    from auspex_ingest.storage.minio_client import MinioArchive

    connector_cls = _REGISTRY[entry.source_type]
    connector = connector_cls()

    minio_client = Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=False,
    )
    archive = MinioArchive(client=minio_client, bucket=os.environ["MINIO_BUCKET"])

    llm_client = instructor.from_openai(openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"]))
    extractor = LLMExtractor(
        client=llm_client,
        model=os.environ.get("OPEN_AI_EXTRACTION_MODEL", "gpt-4o-mini"),
        schema_version="1.0",
        prompt_version="v1",
        gene_vocab=frozenset(entry.prefilter_vocabulary),
    )

    kafka_producer = KafkaProducerClient(
        ConfluentProducer({"bootstrap.servers": os.environ["KAFKA_BOOTSTRAP_SERVERS"]}),
        raw_topic=os.environ.get("KAFKA_RAW_TOPIC", "auspex.raw.ingested"),
        signals_topic=os.environ.get("KAFKA_SIGNALS_TOPIC", "auspex.signals.extracted"),
    )

    return IngestionPipeline(
        connector=connector,
        archive=archive,
        extractor=extractor,
        producer=kafka_producer,
        prefilter=Prefilter.from_vocab(set(entry.prefilter_vocabulary)),
        normalizer=IdentityNormalizer(),
        now=lambda: datetime.now(UTC),
    )


config = load_sources_config(_CONFIG_PATH)
_dag_configs = build_dags(config, _pipeline_factory)

for _dag_cfg in _dag_configs:
    with DAG(
        dag_id=_dag_cfg.dag_id,
        schedule=_dag_cfg.schedule,
        catchup=False,
        max_active_runs=_dag_cfg.max_active_runs,
        start_date=datetime(2024, 1, 1, tzinfo=UTC),
        tags=["auspex"],
    ) as _dag:
        PythonOperator(
            task_id="run_ingestion",
            python_callable=_dag_cfg.task_callable,
        )
    globals()[_dag_cfg.dag_id] = _dag
