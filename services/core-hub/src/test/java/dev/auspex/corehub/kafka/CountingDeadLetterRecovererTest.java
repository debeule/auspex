package dev.auspex.corehub.kafka;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.junit.jupiter.api.Test;
import org.springframework.kafka.listener.ConsumerRecordRecoverer;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

class CountingDeadLetterRecovererTest {

    @Test
    void test_every_dead_lettered_record_is_counted_by_source_topic_and_forwarded() {
        SimpleMeterRegistry registry = new SimpleMeterRegistry();
        ConsumerRecordRecoverer delegate = mock(ConsumerRecordRecoverer.class);
        var recoverer = new CountingDeadLetterRecoverer(delegate, registry);
        ConsumerRecord<?, ?> record = new ConsumerRecord<>("auspex.raw.ingested", 0, 42L, "k", "v");
        RuntimeException failure = new IllegalStateException("neo4j unavailable");

        recoverer.accept(record, failure);

        Counter counter = registry.find("auspex.dlt.events.total")
                .tag("topic", "auspex.raw.ingested")
                .counter();
        assertThat(counter).isNotNull();
        assertThat(counter.count()).isEqualTo(1.0);
        verify(delegate).accept(record, failure);
    }
}
