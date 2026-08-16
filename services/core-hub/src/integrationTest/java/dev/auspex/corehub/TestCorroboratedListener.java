package dev.auspex.corehub;

import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;

@Component
class TestCorroboratedListener {

    private final List<ConsumerRecord<String, String>> records = new CopyOnWriteArrayList<>();

    @KafkaListener(
            topics = "auspex.signals.corroborated",
            groupId = "test-corroborated-consumer",
            containerFactory = "rawListenerContainerFactory"
    )
    void onCorroborated(ConsumerRecord<String, String> record) {
        records.add(record);
    }

    List<ConsumerRecord<String, String>> records() {
        return List.copyOf(records);
    }

    void clear() {
        records.clear();
    }
}
