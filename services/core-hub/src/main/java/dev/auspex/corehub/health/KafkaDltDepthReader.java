package dev.auspex.corehub.health;

import dev.auspex.corehub.kafka.DltReplayService;
import org.apache.kafka.clients.consumer.Consumer;
import org.apache.kafka.clients.consumer.OffsetAndMetadata;
import org.apache.kafka.common.TopicPartition;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.kafka.core.ConsumerFactory;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;

/**
 * Depth is the end offset minus the replay group's committed offset, or minus the earliest
 * retained offset where the group has none, so a replayed record no longer counts. Only offsets
 * are read; the consumer never polls or commits, so the replay's position is untouched.
 */
@Component
public class KafkaDltDepthReader implements DltDepthReader {

    private final ConsumerFactory<byte[], byte[]> consumerFactory;

    public KafkaDltDepthReader(
            @Qualifier("dltReplayConsumerFactory") ConsumerFactory<byte[], byte[]> consumerFactory
    ) {
        this.consumerFactory = consumerFactory;
    }

    @Override
    public Map<String, Long> depthByTopic() {
        Map<String, Long> depths = new HashMap<>();
        try (Consumer<byte[], byte[]> consumer = consumerFactory.createConsumer()) {
            List<TopicPartition> partitions = new ArrayList<>();
            for (String topic : DltReplayService.REPLAYABLE_TOPICS) {
                consumer.partitionsFor(topic)
                        .forEach(info -> partitions.add(new TopicPartition(topic, info.partition())));
                depths.put(topic, 0L);
            }
            Map<TopicPartition, Long> end = consumer.endOffsets(partitions);
            Map<TopicPartition, Long> earliest = consumer.beginningOffsets(partitions);
            Map<TopicPartition, OffsetAndMetadata> committed = consumer.committed(new HashSet<>(partitions));
            for (TopicPartition partition : partitions) {
                long from = earliest.get(partition);
                OffsetAndMetadata replayed = committed.get(partition);
                if (replayed != null) {
                    from = Math.max(from, replayed.offset());
                }
                depths.merge(partition.topic(), Math.max(0, end.get(partition) - from), Long::sum);
            }
        }
        return depths;
    }
}
