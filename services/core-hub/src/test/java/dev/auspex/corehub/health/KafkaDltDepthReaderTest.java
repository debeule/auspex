package dev.auspex.corehub.health;

import org.apache.kafka.clients.consumer.Consumer;
import org.apache.kafka.clients.consumer.OffsetAndMetadata;
import org.apache.kafka.common.PartitionInfo;
import org.apache.kafka.common.TopicPartition;
import org.junit.jupiter.api.Test;
import org.springframework.kafka.core.ConsumerFactory;

import java.util.HashMap;
import java.util.Map;
import java.util.stream.IntStream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyCollection;
import static org.mockito.ArgumentMatchers.anySet;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class KafkaDltDepthReaderTest {

    private static final String SIGNAL_DLT = "auspex.signals.extracted.dlt";
    private static final String RAW_DLT = "auspex.raw.ingested.dlt";

    @SuppressWarnings("unchecked")
    private final Consumer<byte[], byte[]> consumer = mock(Consumer.class);
    private final Map<TopicPartition, Long> earliest = new HashMap<>();
    private final Map<TopicPartition, Long> end = new HashMap<>();
    private final Map<TopicPartition, OffsetAndMetadata> committed = new HashMap<>();

    private Map<String, Long> depths() {
        @SuppressWarnings("unchecked")
        ConsumerFactory<byte[], byte[]> factory = mock(ConsumerFactory.class);
        when(factory.createConsumer()).thenReturn(consumer);
        when(consumer.beginningOffsets(anyCollection())).thenReturn(earliest);
        when(consumer.endOffsets(anyCollection())).thenReturn(end);
        when(consumer.committed(anySet())).thenReturn(committed);
        return new KafkaDltDepthReader(factory).depthByTopic();
    }

    private TopicPartition partition(String topic, int partition, long first, long next) {
        TopicPartition tp = new TopicPartition(topic, partition);
        earliest.put(tp, first);
        end.put(tp, next);
        return tp;
    }

    private void partitions(String topic, int count) {
        when(consumer.partitionsFor(topic)).thenReturn(IntStream.range(0, count)
                .mapToObj(p -> new PartitionInfo(topic, p, null, null, null))
                .toList());
    }

    @Test
    void depthCountsRecordsAfterTheReplayGroupsCommittedOffset() {
        partitions(SIGNAL_DLT, 2);
        partitions(RAW_DLT, 1);
        // Partition 0 was replayed up to 7, partition 1 never; the raw topic's records expired.
        committed.put(partition(SIGNAL_DLT, 0, 2, 10), new OffsetAndMetadata(7));
        partition(SIGNAL_DLT, 1, 0, 4);
        partition(RAW_DLT, 0, 5, 5);

        assertThat(depths()).containsExactlyInAnyOrderEntriesOf(Map.of(SIGNAL_DLT, 3L + 4L, RAW_DLT, 0L));
        verify(consumer, never()).poll(org.mockito.ArgumentMatchers.any(java.time.Duration.class));
        verify(consumer, never()).commitSync(org.mockito.ArgumentMatchers.<Map<TopicPartition, OffsetAndMetadata>>any());
    }

    @Test
    void committedOffsetBeforeTheEarliestRetainedRecordCountsFromTheEarliest() {
        partitions(SIGNAL_DLT, 1);
        partitions(RAW_DLT, 1);
        committed.put(partition(SIGNAL_DLT, 0, 8, 10), new OffsetAndMetadata(3));
        partition(RAW_DLT, 0, 0, 0);

        assertThat(depths()).containsEntry(SIGNAL_DLT, 2L);
    }

}
