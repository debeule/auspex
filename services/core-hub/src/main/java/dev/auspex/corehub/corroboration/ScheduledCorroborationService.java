package dev.auspex.corehub.corroboration;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

import java.util.List;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

/**
 * Runs the corroboration scan and publishes its events in one database transaction: the scan's
 * inserts and its watermark commit only after every send is acknowledged, so a failed send leaves
 * the batch to be found and published again by the next scan. Every failed run, scan or send,
 * increments {@code auspex.corroboration.scan.failures}.
 */
@Service
public class ScheduledCorroborationService implements CorroborationService {

    private static final Logger log = LoggerFactory.getLogger(ScheduledCorroborationService.class);
    private static final String CORROBORATED_TOPIC = "auspex.signals.corroborated";

    private final CorroborationScanner scanner;
    private final KafkaTemplate<Object, Object> corroboratedKafkaTemplate;
    private final TransactionTemplate transactionTemplate;
    private final long sendTimeoutMs;
    private final Counter scanFailures;

    public ScheduledCorroborationService(
            CorroborationScanner scanner,
            @Qualifier("corroboratedKafkaTemplate") KafkaTemplate<Object, Object> corroboratedKafkaTemplate,
            @Qualifier("jpaTransactionManager") PlatformTransactionManager transactionManager,
            @Value("${corroboration.send-timeout-ms:30000}") long sendTimeoutMs,
            MeterRegistry meterRegistry
    ) {
        this.scanner = scanner;
        this.corroboratedKafkaTemplate = corroboratedKafkaTemplate;
        this.transactionTemplate = new TransactionTemplate(transactionManager);
        this.sendTimeoutMs = sendTimeoutMs;
        this.scanFailures = Counter.builder("auspex.corroboration.scan.failures")
                .description("Corroboration runs that threw, in the scan or a send")
                .register(meterRegistry);
    }

    @Scheduled(fixedDelayString = "${corroboration.interval-ms:30000}")
    @Override
    public void runCorroboration() {
        try {
            transactionTemplate.executeWithoutResult(status -> {
                List<CorroboratedSignalEvent> events = scanner.scan();
                for (CorroboratedSignalEvent event : events) {
                    send(event);
                    log.info("corroboration published entity_key={} participants={} sources={}",
                            event.entityKey(), event.participantEventIds().size(), event.distinctSourceCount());
                }
            });
        } catch (RuntimeException e) {
            scanFailures.increment();
            throw e;
        }
    }

    private void send(CorroboratedSignalEvent event) {
        try {
            corroboratedKafkaTemplate.send(CORROBORATED_TOPIC, event.entityKey(), event)
                    .get(sendTimeoutMs, TimeUnit.MILLISECONDS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("corroboration send interrupted", e);
        } catch (ExecutionException | TimeoutException e) {
            log.error("corroboration send failed, rolling back the scan entity_key={}", event.entityKey(), e);
            throw new IllegalStateException("corroboration send failed for " + event.entityKey(), e);
        }
    }
}
