package dev.auspex.corehub;

import dev.auspex.corehub.signal.ResearchSignalEvent;
import dev.auspex.corehub.signal.SignalGraphPort;
import dev.auspex.corehub.signal.SignalIngestionService;
import dev.auspex.corehub.signal.SignalRecordPort;
import org.junit.jupiter.api.Test;
import org.mockito.InOrder;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

class SignalIngestionServiceTest {

    private static ResearchSignalEvent testEvent() {
        return new ResearchSignalEvent(
                "1.0",
                UUID.fromString("c1261cdc-1cf0-5bca-922d-7d098c8f0d6f"),
                UUID.fromString("ff46e2f9-35f9-55dc-9d3e-080de1f77cca"),
                "ext-001",
                null,
                "raw/biorxiv/ext-001/key.json",
                "biorxiv",
                "https://example.org",
                Instant.parse("2024-06-15T12:00:00Z"),
                "date",
                Instant.parse("2024-06-15T12:00:00Z"),
                "Title",
                "Snippet",
                List.of("BCL11A"),
                List.of("base editing"),
                List.of("Beam Therapeutics"),
                "Summary",
                "positive",
                new BigDecimal("0.92"),
                "v1",
                "v1",
                "gpt-4o",
                "preclinical_data",
                null,
                List.of(),
                List.of()
        );
    }

    @Test
    void test_ingest_calls_graph_port_before_record_port() {
        SignalGraphPort graphPort = mock(SignalGraphPort.class);
        SignalRecordPort recordPort = mock(SignalRecordPort.class);
        SignalIngestionService service = new SignalIngestionService(graphPort, recordPort);

        service.ingest(testEvent());

        InOrder order = inOrder(graphPort, recordPort);
        order.verify(graphPort).upsert(testEvent());
        order.verify(recordPort).upsert(testEvent());
    }

    @Test
    void test_ingest_calls_both_ports_with_same_event() {
        SignalGraphPort graphPort = mock(SignalGraphPort.class);
        SignalRecordPort recordPort = mock(SignalRecordPort.class);
        SignalIngestionService service = new SignalIngestionService(graphPort, recordPort);

        ResearchSignalEvent event = testEvent();
        service.ingest(event);

        verify(graphPort).upsert(event);
        verify(recordPort).upsert(event);
    }

    @Test
    void test_ingest_propagates_graph_port_exception() {
        SignalGraphPort graphPort = mock(SignalGraphPort.class);
        SignalRecordPort recordPort = mock(SignalRecordPort.class);
        doThrow(new RuntimeException("neo4j down")).when(graphPort).upsert(testEvent());
        SignalIngestionService service = new SignalIngestionService(graphPort, recordPort);

        assertThatThrownBy(() -> service.ingest(testEvent()))
                .isInstanceOf(RuntimeException.class)
                .hasMessage("neo4j down");
        verify(recordPort, never()).upsert(testEvent());
    }
}
