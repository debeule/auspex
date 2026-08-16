package dev.auspex.corehub.kafka;

import dev.auspex.corehub.service.RawAuditService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.support.KafkaHeaders;
import org.springframework.messaging.handler.annotation.Header;
import org.springframework.messaging.handler.annotation.Payload;
import org.springframework.stereotype.Component;

/**
 * Consumes auspex.raw.ingested — writes only to raw_fetch_audit (§3.8).
 */
@Component
public class RawListener {

    private static final Logger log = LoggerFactory.getLogger(RawListener.class);

    private final RawAuditService rawAuditService;

    public RawListener(RawAuditService rawAuditService) {
        this.rawAuditService = rawAuditService;
    }

    @KafkaListener(
            topics = "auspex.raw.ingested",
            containerFactory = "rawListenerContainerFactory"
    )
    public void onRaw(
            @Payload String payload,
            @Header(KafkaHeaders.RECEIVED_TOPIC) String topic
    ) {
        log.debug("raw message received topic={}", topic);
        rawAuditService.record(payload);
    }
}
