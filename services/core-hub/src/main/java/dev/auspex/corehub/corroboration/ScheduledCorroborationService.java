package dev.auspex.corehub.corroboration;

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
 * the batch to be found and published again by the next scan.
 */
@Service
public class ScheduledCorroborationService implements CorroborationService {

    private static final Logger log = LoggerFactory.getLogger(ScheduledCorroborationService.class);
    private static final String CORROBORATED_TOPIC = "auspex.signals.corroborated";

    private final CorroborationScanner scanner;
    private final KafkaTemplate<Object, Object> corroboratedKafkaTemplate;
    private final TransactionTemplate transactionTemplate;
    private final long sendTimeoutMs;

    public ScheduledCorroborationService(
            CorroborationScanner scanner,
            @Qualifier("corroboratedKafkaTemplate") KafkaTemplate<Object, Object> corroboratedKafkaTemplate,
            @Qualifier("jpaTransactionManager") PlatformTransactionManager transactionManager,
            @Value("${corroboration.send-timeout-ms:30000}") long sendTimeoutMs
    ) {
        this.scanner = scanner;
        this.corroboratedKafkaTemplate = corroboratedKafkaTemplate;
        this.transactionTemplate = new TransactionTemplate(transactionManager);
        this.sendTimeoutMs = sendTimeoutMs;
    }

    @Scheduled(fixedDelayString = "${corroboration.interval-ms:30000}")
    @Override
    public void runCorroboration() {
        transactionTemplate.executeWithoutResult(status -> {
            List<CorroboratedSignalEvent> events = scanner.scan();
            for (CorroboratedSignalEvent event : events) {
                send(event);
                log.info("corroboration published entity_key={} participants={} sources={}",
                        event.entityKey(), event.participantEventIds().size(), event.distinctSourceCount());
            }
        });
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
