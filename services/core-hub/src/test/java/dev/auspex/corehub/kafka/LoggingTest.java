package dev.auspex.corehub.kafka;

import ch.qos.logback.classic.Level;
import ch.qos.logback.classic.Logger;
import ch.qos.logback.classic.spi.ILoggingEvent;
import ch.qos.logback.core.read.ListAppender;
import dev.auspex.corehub.model.ResearchSignalEvent;
import dev.auspex.corehub.service.GraphUpdateService;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;

class LoggingTest {

    private ListAppender<ILoggingEvent> appender;
    private SignalListener signalListener;

    @BeforeEach
    void setUp() {
        Logger logger = (Logger) LoggerFactory.getLogger(SignalListener.class);
        appender = new ListAppender<>();
        appender.start();
        logger.addAppender(appender);
        logger.setLevel(Level.DEBUG);

        signalListener = new SignalListener(mock(GraphUpdateService.class));
        MDC.clear();
    }

    @AfterEach
    void tearDown() {
        Logger logger = (Logger) LoggerFactory.getLogger(SignalListener.class);
        logger.detachAppender(appender);
        MDC.clear();
    }

    @Test
    void test_signal_listener_mdc_contains_event_id_and_source_type() {
        ResearchSignalEvent event = buildEvent("1.0", UUID.randomUUID(), "biorxiv");
        signalListener.onSignal(event, "auspex.signals.extracted");

        assertThat(appender.list).isNotEmpty();
        ILoggingEvent logEvent = appender.list.get(0);
        assertThat(logEvent.getMDCPropertyMap()).containsKey("auspex.event_id");
        assertThat(logEvent.getMDCPropertyMap()).containsKey("auspex.source_type");
        assertThat(logEvent.getMDCPropertyMap().get("auspex.event_id")).isEqualTo(event.eventId().toString());
        assertThat(logEvent.getMDCPropertyMap().get("auspex.source_type")).isEqualTo("biorxiv");
    }

    @Test
    void test_mdc_cleared_after_listener_returns() {
        ResearchSignalEvent event = buildEvent("1.0", UUID.randomUUID(), "biorxiv");
        signalListener.onSignal(event, "auspex.signals.extracted");
        assertThat(MDC.getCopyOfContextMap()).isNullOrEmpty();
    }

    @Test
    void test_dlt_routing_log_contains_exception_class_and_event_id() {
        UUID eventId = UUID.randomUUID();
        ResearchSignalEvent event = buildEvent("99.0", eventId, "biorxiv");

        try {
            signalListener.onSignal(event, "auspex.signals.extracted");
        } catch (UnknownMajorVersionException ignored) {
        }

        List<ILoggingEvent> errors = appender.list.stream()
                .filter(e -> e.getLevel() == Level.ERROR)
                .toList();
        assertThat(errors).isNotEmpty();
        ILoggingEvent err = errors.get(0);
        assertThat(err.getMDCPropertyMap()).containsKey("auspex.event_id");
        assertThat(err.getFormattedMessage()).contains("UnknownMajorVersionException");
    }

    @Test
    void test_log_output_does_not_contain_raw_content_field() {
        ResearchSignalEvent event = buildEvent("1.0", UUID.randomUUID(), "biorxiv");
        signalListener.onSignal(event, "auspex.signals.extracted");

        for (ILoggingEvent logEvent : appender.list) {
            assertThat(logEvent.getMDCPropertyMap()).doesNotContainKey("raw_content");
            assertThat(logEvent.getFormattedMessage()).doesNotContain("raw_content");
        }
    }

    private static ResearchSignalEvent buildEvent(String schemaVersion, UUID eventId, String sourceType) {
        return new ResearchSignalEvent(
                schemaVersion,
                eventId,
                UUID.randomUUID(),
                "ext-" + eventId,
                null,
                "raw/test.json",
                sourceType,
                "https://example.com",
                Instant.parse("2023-01-10T12:00:00Z"),
                "published_date",
                Instant.parse("2023-01-10T13:00:00Z"),
                "Test title",
                "Test snippet",
                List.of("BRCA1"),
                List.of("inhibition"),
                List.of("BEAM Therapeutics"),
                "Test summary",
                "positive",
                BigDecimal.valueOf(0.85),
                "v1",
                "v1",
                "gpt-4o"
        );
    }
}
