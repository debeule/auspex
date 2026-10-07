package dev.auspex.corehub.kafka;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.springframework.kafka.listener.ConsumerRecordRecoverer;

/**
 * Counts every record the error handler sends to a DLT — deserialization failures,
 * validation failures and exhausted retries alike — then hands it to the real recoverer.
 */
public class CountingDeadLetterRecoverer implements ConsumerRecordRecoverer {

    private final ConsumerRecordRecoverer delegate;
    private final MeterRegistry meterRegistry;

    public CountingDeadLetterRecoverer(ConsumerRecordRecoverer delegate, MeterRegistry meterRegistry) {
        this.delegate = delegate;
        this.meterRegistry = meterRegistry;
    }

    @Override
    public void accept(ConsumerRecord<?, ?> record, Exception exception) {
        Counter.builder("auspex.dlt.events.total")
                .tag("topic", record.topic())
                .register(meterRegistry)
                .increment();
        delegate.accept(record, exception);
    }
}
