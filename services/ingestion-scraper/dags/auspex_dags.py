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
def _build_connector(source_type: str, entry, rate_limited_client):  # type: ignore[no-untyped-def]
    from auspex_ingest.connectors.biorxiv import BiorxivConnector
    from auspex_ingest.connectors.clinicaltrials import ClinicalTrialConnector
    from auspex_ingest.connectors.mock import MockConnector
    from auspex_ingest.connectors.pubmed import PubmedConnector
    from auspex_ingest.connectors.sec_edgar import SecEdgarConnector

    if source_type == "mock":
        return MockConnector()
    if source_type == "biorxiv":
        return BiorxivConnector(client=rate_limited_client)
    if source_type == "clinicaltrials":
        return ClinicalTrialConnector(client=rate_limited_client)
    if source_type == "pubmed":
        return PubmedConnector(
            client=rate_limited_client,
            search_term=entry.source_config.get("search_term", "gene therapy"),
            api_key=os.environ.get("NCBI_API_KEY") or None,
        )
    if source_type == "edgar":
        return SecEdgarConnector(
            client=rate_limited_client,
            user_agent=os.environ["SEC_USER_AGENT"],
        )
    if source_type == "epo_ops":
        from auspex_ingest.connectors.epo_ops import EpoOpsConnector
        return EpoOpsConnector(
            client=rate_limited_client,
            key=os.environ.get("EPO_OPS_KEY", ""),
            secret=os.environ.get("EPO_OPS_SECRET", ""),
        )
    raise ValueError(f"No connector registered for source_type={source_type!r}")


def _pipeline_factory(entry):  # type: ignore[no-untyped-def]
    import instructor
    import openai
    from confluent_kafka import Producer as ConfluentProducer
    from minio import Minio

    from auspex_ingest.extractor import LLMExtractor
    from auspex_ingest.kafka_producer import KafkaProducerClient
    from auspex_ingest.normalizer import IdentityNormalizer
    from auspex_ingest.prefilter import Prefilter
    from auspex_ingest.rate_limited_client import RateLimitedClient
    from auspex_ingest.storage.minio_client import MinioArchive

    rate_limits: dict[str, float] = {
        "api.biorxiv.org": 3.0,
        "clinicaltrials.gov": 5.0,
        "eutils.ncbi.nlm.nih.gov": 3.0,
        "sec.gov": 4.0,
        "ops.epo.org": 2.0,
    }
    http_client = RateLimitedClient(rate_limits)
    connector = _build_connector(entry.source_type, entry, http_client)

    minio_client = Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=False,
    )
    archive = MinioArchive(client=minio_client, bucket=os.environ["MINIO_BUCKET"])

    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPEN_AI_KEY") or ""
    llm_client = instructor.from_openai(openai.OpenAI(api_key=api_key))
    extractor = LLMExtractor(
        client=llm_client,
        model=os.environ.get("OPEN_AI_EXTRACTION_MODEL", "gpt-4o-mini"),
        schema_version="1.0",
        prompt_version="v1",
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
        min_confidence_to_publish=0.5,
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
