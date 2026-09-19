package dev.auspex.corehub.kafka;

import dev.auspex.corehub.audit.RawAuditService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.support.KafkaHeaders;
import org.springframework.messaging.handler.annotation.Header;
import org.springframework.messaging.handler.annotation.Payload;
import org.springframework.stereotype.Component;

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
        MDC.put("auspex.topic", topic);
        try {
            log.debug("raw message received");
            rawAuditService.record(payload);
        } finally {
            MDC.clear();
        }
    }
}
