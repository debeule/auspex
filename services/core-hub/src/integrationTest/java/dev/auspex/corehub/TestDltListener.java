package dev.auspex.corehub;

import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;

/**
 * Test-only component that consumes DLT topics and records received messages.
 * Used by integration tests to assert DLT routing behaviour.
 */
@Component
class TestDltListener {

    private final List<ConsumerRecord<String, String>> signalDltRecords = new CopyOnWriteArrayList<>();
    private final List<ConsumerRecord<String, String>> rawDltRecords    = new CopyOnWriteArrayList<>();

    @KafkaListener(
            topics = "auspex.signals.extracted.dlt",
            groupId = "test-signal-dlt-consumer",
            containerFactory = "rawListenerContainerFactory"
    )
    void onSignalDlt(ConsumerRecord<String, String> record) {
        signalDltRecords.add(record);
    }

    @KafkaListener(
            topics = "auspex.raw.ingested.dlt",
            groupId = "test-raw-dlt-consumer",
            containerFactory = "rawListenerContainerFactory"
    )
    void onRawDlt(ConsumerRecord<String, String> record) {
        rawDltRecords.add(record);
    }

    List<ConsumerRecord<String, String>> signalDltRecords() {
        return List.copyOf(signalDltRecords);
    }

    List<ConsumerRecord<String, String>> rawDltRecords() {
        return List.copyOf(rawDltRecords);
    }

    void clear() {
        signalDltRecords.clear();
        rawDltRecords.clear();
    }
}
