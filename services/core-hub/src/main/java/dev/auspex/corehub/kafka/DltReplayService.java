package dev.auspex.corehub.kafka;

import org.apache.kafka.clients.consumer.Consumer;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.clients.consumer.OffsetAndMetadata;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.common.TopicPartition;
import org.apache.kafka.common.header.Header;
import org.apache.kafka.common.header.internals.RecordHeaders;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.kafka.core.ConsumerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.KafkaHeaders;
import org.springframework.stereotype.Service;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

/**
 * Re-publishes dead letters to their source topic with the original key, value and headers, so
 * the normal listener stores them. Its position is kept in its own consumer group and committed
 * after each acknowledged send, so a record is replayed at most once.
 */
@Service
public class DltReplayService {

    /** Dead-letter topics that may be replayed; nothing consumes the corroborated topic yet. */
    public static final Set<String> REPLAYABLE_TOPICS =
            Set.of("auspex.signals.extracted.dlt", "auspex.raw.ingested.dlt");

    private static final Logger log = LoggerFactory.getLogger(DltReplayService.class);
    private static final String DLT_SUFFIX = ".dlt";
    private static final Duration POLL_TIMEOUT = Duration.ofMillis(500);
    private static final Duration REPLAY_TIMEOUT = Duration.ofMinutes(5);
    private static final long SEND_TIMEOUT_SECONDS = 30;

    private final ConsumerFactory<byte[], byte[]> consumerFactory;
    private final KafkaTemplate<byte[], byte[]> replayTemplate;

    public DltReplayService(
            @Qualifier("dltReplayConsumerFactory") ConsumerFactory<byte[], byte[]> consumerFactory,
            @Qualifier("dltReplayKafkaTemplate") KafkaTemplate<byte[], byte[]> replayTemplate
    ) {
        this.consumerFactory = consumerFactory;
        this.replayTemplate = replayTemplate;
    }

    /**
     * Replays every record that was on {@code dltTopic} when the call started and had not been
     * replayed before. Returns how many were replayed.
     */
    public synchronized int replay(String dltTopic) {
        if (!REPLAYABLE_TOPICS.contains(dltTopic)) {
            throw new IllegalArgumentException("not a replayable dead-letter topic: " + dltTopic);
        }
        try (Consumer<byte[], byte[]> consumer = consumerFactory.createConsumer()) {
            List<TopicPartition> partitions = consumer.partitionsFor(dltTopic).stream()
                    .map(info -> new TopicPartition(dltTopic, info.partition()))
                    .toList();
            consumer.assign(partitions);
            Map<TopicPartition, Long> endOffsets = consumer.endOffsets(partitions);
            Instant deadline = Instant.now().plus(REPLAY_TIMEOUT);

            int replayed = 0;
            while (!reachedEnd(consumer, endOffsets)) {
                if (Instant.now().isAfter(deadline)) {
                    throw new IllegalStateException("replay of %s timed out after %d records"
                            .formatted(dltTopic, replayed));
                }
                for (ConsumerRecord<byte[], byte[]> record : consumer.poll(POLL_TIMEOUT)) {
                    TopicPartition partition = new TopicPartition(record.topic(), record.partition());
                    // Records that arrived after the call started wait for the next replay.
                    if (record.offset() >= endOffsets.get(partition)) {
                        continue;
                    }
                    republish(record);
                    consumer.commitSync(Map.of(partition, new OffsetAndMetadata(record.offset() + 1)));
                    replayed++;
                }
            }
            log.info("replayed dead letters topic={} count={}", dltTopic, replayed);
            return replayed;
        }
    }

    private static boolean reachedEnd(Consumer<byte[], byte[]> consumer, Map<TopicPartition, Long> endOffsets) {
        return endOffsets.entrySet().stream()
                .allMatch(end -> consumer.position(end.getKey()) >= end.getValue());
    }

    private void republish(ConsumerRecord<byte[], byte[]> record) {
        RecordHeaders headers = new RecordHeaders();
        for (Header header : record.headers()) {
            if (!isDeadLetterHeader(header.key())) {
                headers.add(header);
            }
        }
        var outgoing = new ProducerRecord<>(sourceTopic(record), null, record.key(), record.value(), headers);
        try {
            replayTemplate.send(outgoing).get(SEND_TIMEOUT_SECONDS, TimeUnit.SECONDS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("replay interrupted", e);
        } catch (ExecutionException | TimeoutException e) {
            throw new IllegalStateException("replay send failed for %s-%d@%d"
                    .formatted(record.topic(), record.partition(), record.offset()), e);
        }
    }

    private static String sourceTopic(ConsumerRecord<byte[], byte[]> record) {
        Header original = record.headers().lastHeader(KafkaHeaders.DLT_ORIGINAL_TOPIC);
        if (original != null) {
            return new String(original.value(), StandardCharsets.UTF_8);
        }
        return record.topic().substring(0, record.topic().length() - DLT_SUFFIX.length());
    }

    /** Headers the dead-letter recoverer and JSON serializers add; the source record had none of them. */
    private static boolean isDeadLetterHeader(String key) {
        return key.startsWith("kafka_dlt-") || (key.startsWith("__") && key.endsWith("TypeId__"));
    }
}
