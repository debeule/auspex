import os
import time
from collections import Counter
from uuid import uuid4

import pytest
from confluent_kafka import Producer as ConfluentProducer
from confluent_kafka.admin import AdminClient, NewTopic
from testcontainers.community.kafka import KafkaContainer

os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

_KAFKA_IMAGE = "mirror.gcr.io/confluentinc/cp-kafka:7.6.0"
_TOPIC = "auspex.signals.extracted"
_NUM_PARTITIONS = 6
_MESSAGE_COUNT = 120
_MAX_SKEW_RATIO = 2.0


@pytest.mark.integration
def test_key_distribution_across_partitions() -> None:
    with KafkaContainer(_KAFKA_IMAGE).with_kraft() as kafka:
        bootstrap = kafka.get_bootstrap_server()

        admin = AdminClient({"bootstrap.servers": bootstrap})
        fs = admin.create_topics([
            NewTopic(_TOPIC, num_partitions=_NUM_PARTITIONS, replication_factor=1),
        ])
        for future in fs.values():
            future.result()
        time.sleep(0.5)

        producer = ConfluentProducer({"bootstrap.servers": bootstrap})
        for _ in range(_MESSAGE_COUNT):
            producer.produce(_TOPIC, key=str(uuid4()), value=b"x")
        producer.flush()

        # Read back the partition metadata to count messages per partition
        from confluent_kafka import Consumer, KafkaError

        consumer = Consumer({
            "bootstrap.servers": bootstrap,
            "group.id": "test-partition-dist",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        })
        consumer.subscribe([_TOPIC])

        partition_counts: Counter[int] = Counter()
        received = 0
        deadline = time.monotonic() + 20.0
        while received < _MESSAGE_COUNT and time.monotonic() < deadline:
            msg = consumer.poll(0.5)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                raise RuntimeError(f"Kafka consumer error: {msg.error()}")
            partition_counts[msg.partition()] += 1
            received += 1
        consumer.close()

        assert received == _MESSAGE_COUNT, (
            f"Only received {received}/{_MESSAGE_COUNT} messages"
        )

        expected_per_partition = _MESSAGE_COUNT / _NUM_PARTITIONS
        max_allowed = int(expected_per_partition * _MAX_SKEW_RATIO)

        for p in range(_NUM_PARTITIONS):
            count = partition_counts.get(p, 0)
            assert count <= max_allowed, (
                f"Partition {p} has {count} messages — exceeds {_MAX_SKEW_RATIO}x expected "
                f"({expected_per_partition:.0f}). Full distribution: {dict(partition_counts)}"
            )
