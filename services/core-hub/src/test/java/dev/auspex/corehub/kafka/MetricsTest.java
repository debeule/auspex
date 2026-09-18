package dev.auspex.corehub.kafka;

import dev.auspex.corehub.model.ResearchSignalEvent;
import dev.auspex.corehub.service.GraphUpdateService;
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;

class MetricsTest {

    private SimpleMeterRegistry registry;
    private SignalListener signalListener;

    @BeforeEach
    void setUp() {
        registry = new SimpleMeterRegistry();
        signalListener = new SignalListener(mock(GraphUpdateService.class), registry);
    }

    @Test
    void test_signals_processed_counter_increments_per_source_type() {
        ResearchSignalEvent event = buildEvent("1.0", UUID.randomUUID(), "biorxiv");
        signalListener.onSignal(event, "auspex.signals.extracted");

        Counter counter = registry.find("auspex.signals.processed.total")
                .tag("source_type", "biorxiv")
                .counter();
        assertThat(counter).isNotNull();
        assertThat(counter.count()).isEqualTo(1.0);
    }

    @Test
    void test_dlt_counter_increments_on_routing() {
        ResearchSignalEvent event = buildEvent("99.0", UUID.randomUUID(), "biorxiv");
        try {
            signalListener.onSignal(event, "auspex.signals.extracted");
        } catch (UnknownMajorVersionException ignored) {
        }

        Counter counter = registry.find("auspex.dlt.events.total")
                .tag("topic", "auspex.signals.extracted")
                .counter();
        assertThat(counter).isNotNull();
        assertThat(counter.count()).isEqualTo(1.0);
    }

    private static ResearchSignalEvent buildEvent(String schemaVersion, UUID eventId, String sourceType) {
        return new ResearchSignalEvent(
                schemaVersion, eventId, UUID.randomUUID(),
                "ext-" + eventId, null, "raw/test.json",
                sourceType, "https://example.com",
                Instant.parse("2023-01-10T12:00:00Z"), "published_date",
                Instant.parse("2023-01-10T13:00:00Z"), "Test title",
                "Test snippet", List.of("BRCA1"), List.of("inhibition"),
                List.of("BEAM"), "Summary", "positive",
                BigDecimal.valueOf(0.85), "v1", "v1", "gpt-4o"
        );
    }
}
