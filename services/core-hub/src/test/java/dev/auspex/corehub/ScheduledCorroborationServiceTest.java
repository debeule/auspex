package dev.auspex.corehub;

import dev.auspex.corehub.corroboration.CorroboratedSignalEvent;
import dev.auspex.corehub.corroboration.CorroborationScanner;
import dev.auspex.corehub.corroboration.ScheduledCorroborationService;
import org.junit.jupiter.api.Test;
import org.springframework.kafka.core.KafkaTemplate;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class ScheduledCorroborationServiceTest {

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

        ScheduledCorroborationService service = new ScheduledCorroborationService(scanner, kafka);
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

        ScheduledCorroborationService service = new ScheduledCorroborationService(scanner, kafka);
        service.runCorroboration();

        verify(kafka, never()).send(any(), any(), any());
    }
}
