package dev.auspex.corehub.kafka;

import dev.auspex.corehub.signal.ResearchSignalEvent;
import dev.auspex.corehub.signal.SchemaVersion;
import dev.auspex.corehub.signal.SignalIngestionService;
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import jakarta.validation.Valid;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.support.KafkaHeaders;
import org.springframework.messaging.handler.annotation.Header;
import org.springframework.messaging.handler.annotation.Payload;
import org.springframework.stereotype.Component;

@Component
public class SignalListener {

    /** Listener container id, used to pause and resume it. */
    public static final String CONTAINER_ID = "signal-listener";

    private static final Logger log = LoggerFactory.getLogger(SignalListener.class);

    private final SignalIngestionService signalIngestionService;
    private final MeterRegistry meterRegistry;

    public SignalListener(SignalIngestionService signalIngestionService, MeterRegistry meterRegistry) {
        this.signalIngestionService = signalIngestionService;
        this.meterRegistry = meterRegistry;
    }

    @KafkaListener(
            id = CONTAINER_ID,
            idIsGroup = false,
            topics = "auspex.signals.extracted",
            containerFactory = "signalListenerContainerFactory"
    )
    public void onSignal(
            @Payload @Valid ResearchSignalEvent event,
            @Header(KafkaHeaders.RECEIVED_TOPIC) String topic
    ) {
        MDC.put("auspex.event_id", event.eventId().toString());
        MDC.put("auspex.source_type", event.sourceType());
        try {
            SchemaVersion sv = SchemaVersion.parse(event.schemaVersion());
            if (!SchemaVersion.isKnownMajor(sv)) {
                log.error("routing to DLT: exception_class={} auspex.topic={}",
                        UnknownMajorVersionException.class.getSimpleName(), topic);
                throw new UnknownMajorVersionException(
                        "Unknown major schema version %d in topic %s — routing to DLT"
                                .formatted(sv.major(), topic));
            }
            Counter.builder("auspex.signals.processed.total")
                    .tag("source_type", event.sourceType())
                    .register(meterRegistry)
                    .increment();
            log.info("processing signal schema_version={}", event.schemaVersion());
            signalIngestionService.ingest(event);
        } finally {
            MDC.clear();
        }
    }
}
