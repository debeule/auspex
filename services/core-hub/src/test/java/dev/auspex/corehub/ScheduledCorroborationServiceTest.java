package dev.auspex.corehub;

import dev.auspex.corehub.corroboration.CorroboratedSignalEvent;
import dev.auspex.corehub.corroboration.CorroborationScanner;
import dev.auspex.corehub.corroboration.ScheduledCorroborationService;
import org.junit.jupiter.api.Test;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.TransactionStatus;
import org.springframework.transaction.support.SimpleTransactionStatus;

import java.time.Instant;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class ScheduledCorroborationServiceTest {

    /** Records whether the scan's database work was committed or rolled back. */
    private static final class RecordingTransactionManager implements PlatformTransactionManager {
        boolean committed;
        boolean rolledBack;

        @Override
        public TransactionStatus getTransaction(TransactionDefinition definition) {
            return new SimpleTransactionStatus();
        }

        @Override
        public void commit(TransactionStatus status) { committed = true; }

        @Override
        public void rollback(TransactionStatus status) { rolledBack = true; }
    }

    private static CorroboratedSignalEvent event(String entityKey) {
        return new CorroboratedSignalEvent(
                entityKey,
                "abc123",
                List.of(UUID.randomUUID()),
                2,
                Instant.now(),
                Instant.now()
        );
    }

    @SuppressWarnings("unchecked")
    @Test
    void test_run_corroboration_publishes_each_event_returned_by_scanner() {
        CorroborationScanner scanner = mock(CorroborationScanner.class);
        KafkaTemplate<Object, Object> kafka = mock(KafkaTemplate.class);
        CorroboratedSignalEvent e1 = event("gene:GeneTarget");
        CorroboratedSignalEvent e2 = event("mech:Mechanism");
        when(scanner.scan()).thenReturn(List.of(e1, e2));
        when(kafka.send(any(), any(), any())).thenReturn(CompletableFuture.completedFuture(null));

        ScheduledCorroborationService service =
                new ScheduledCorroborationService(scanner, kafka, new RecordingTransactionManager(), 1000L);
        service.runCorroboration();

        verify(kafka).send(eq("auspex.signals.corroborated"), eq(e1.entityKey()), eq(e1));
        verify(kafka).send(eq("auspex.signals.corroborated"), eq(e2.entityKey()), eq(e2));
    }

    @SuppressWarnings("unchecked")
    @Test
    void test_run_corroboration_does_not_call_kafka_when_scanner_returns_empty() {
        CorroborationScanner scanner = mock(CorroborationScanner.class);
        KafkaTemplate<Object, Object> kafka = mock(KafkaTemplate.class);
        when(scanner.scan()).thenReturn(List.of());

        ScheduledCorroborationService service =
                new ScheduledCorroborationService(scanner, kafka, new RecordingTransactionManager(), 1000L);
        service.runCorroboration();

        verify(kafka, never()).send(any(), any(), any());
    }

    @SuppressWarnings("unchecked")
    @Test
    void watermarkIsNotWrittenWhenACorroboratedSendFails() {
        CorroborationScanner scanner = mock(CorroborationScanner.class);
        KafkaTemplate<Object, Object> kafka = mock(KafkaTemplate.class);
        when(scanner.scan()).thenReturn(List.of(event("gene:GeneTarget")));
        when(kafka.send(any(), any(), any()))
                .thenReturn(CompletableFuture.failedFuture(new IllegalStateException("broker unavailable")));
        RecordingTransactionManager transactions = new RecordingTransactionManager();

        ScheduledCorroborationService service =
                new ScheduledCorroborationService(scanner, kafka, transactions, 1000L);

        assertThatThrownBy(service::runCorroboration).isInstanceOf(IllegalStateException.class);
        // The scan's inserts and its watermark write share this transaction.
        assertThat(transactions.rolledBack).isTrue();
        assertThat(transactions.committed).isFalse();
    }
}
