package dev.auspex.corehub.kafka;

import dev.auspex.corehub.model.ResearchSignalEvent;
import dev.auspex.corehub.model.SchemaVersion;
import dev.auspex.corehub.service.GraphUpdateService;
import jakarta.validation.Valid;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.support.KafkaHeaders;
import org.springframework.messaging.handler.annotation.Header;
import org.springframework.messaging.handler.annotation.Payload;
import org.springframework.stereotype.Component;

/**
 * Consumes auspex.signals.extracted.
 * Unknown major schema_version → throws (deterministic failure → DLT immediately).
 * @Valid triggers bean validation; @KafkaListener does not run it automatically.
 */
@Component
public class SignalListener {

    private static final Logger log = LoggerFactory.getLogger(SignalListener.class);

    private final GraphUpdateService graphUpdateService;

    public SignalListener(GraphUpdateService graphUpdateService) {
        this.graphUpdateService = graphUpdateService;
    }

    @KafkaListener(
            topics = "auspex.signals.extracted",
            containerFactory = "signalListenerContainerFactory"
    )
    public void onSignal(
            @Payload @Valid ResearchSignalEvent event,
            @Header(KafkaHeaders.RECEIVED_TOPIC) String topic
    ) {
        SchemaVersion sv = SchemaVersion.parse(event.schemaVersion());
        if (!SchemaVersion.isKnownMajor(sv)) {
            throw new UnknownMajorVersionException(
                    "Unknown major schema version %d in topic %s — routing to DLT"
                            .formatted(sv.major(), topic));
        }
        log.info("signal event_id={} source_type={} schema_version={}",
                event.eventId(), event.sourceType(), event.schemaVersion());
        graphUpdateService.process(event);
    }
}
