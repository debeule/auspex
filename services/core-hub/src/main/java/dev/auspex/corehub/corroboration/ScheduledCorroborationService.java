package dev.auspex.corehub.corroboration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class ScheduledCorroborationService implements CorroborationService {

    private static final Logger log = LoggerFactory.getLogger(ScheduledCorroborationService.class);
    private static final String CORROBORATED_TOPIC = "auspex.signals.corroborated";

    private final CorroborationScanner scanner;
    private final KafkaTemplate<Object, Object> corroboratedKafkaTemplate;

    public ScheduledCorroborationService(
            CorroborationScanner scanner,
            @Qualifier("corroboratedKafkaTemplate") KafkaTemplate<Object, Object> corroboratedKafkaTemplate
    ) {
        this.scanner = scanner;
        this.corroboratedKafkaTemplate = corroboratedKafkaTemplate;
    }

    @Scheduled(fixedDelayString = "${corroboration.interval-ms:30000}")
    @Override
    public void runCorroboration() {
        List<CorroboratedSignalEvent> events = scanner.scan();
        for (CorroboratedSignalEvent event : events) {
            corroboratedKafkaTemplate.send(CORROBORATED_TOPIC, event.entityKey(), event);
            log.info("corroboration published entity_key={} participants={} sources={}",
                    event.entityKey(), event.participantEventIds().size(), event.distinctSourceCount());
        }
    }
}
