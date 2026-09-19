import json
from typing import Any

from ..models import RawDocument, ResearchSignalEvent


class KafkaProducerClient:
    def __init__(
        self,
        producer: Any,
        raw_topic: str,
        signals_topic: str,
    ) -> None:
        self._producer = producer
        self._raw_topic = raw_topic
        self._signals_topic = signals_topic

    def publish_raw(self, doc: RawDocument, raw_object_key: str, schema_version: str) -> None:
        payload = json.dumps({
            **json.loads(doc.model_dump_json()),
            "raw_object_key": raw_object_key,
        }).encode()
        self._producer.produce(
            self._raw_topic,
            key=doc.external_id,
            value=payload,
            headers={"schema_version": schema_version},
            callback=self._delivery_cb,
        )

    def publish_signal(self, event: ResearchSignalEvent) -> None:
        self._producer.produce(
            self._signals_topic,
            key=str(event.event_id),
            value=event.model_dump_json().encode(),
            headers={"schema_version": event.schema_version},
            callback=self._delivery_cb,
        )

    def flush(self) -> None:
        unflushed = self._producer.flush(timeout=30)
        if unflushed > 0:
            raise RuntimeError(f"Kafka flush timed out: {unflushed} messages undelivered")

    @staticmethod
    def _delivery_cb(err: Any, msg: Any) -> None:
        if err is not None:
            raise RuntimeError(f"Kafka delivery failed: {err}")
