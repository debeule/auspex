package dev.auspex.corehub.signal;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

@Service
public class SignalIngestionService {

    private static final Logger log = LoggerFactory.getLogger(SignalIngestionService.class);

    private final SignalGraphPort graphPort;
    private final SignalRecordPort recordPort;

    public SignalIngestionService(SignalGraphPort graphPort, SignalRecordPort recordPort) {
        this.graphPort = graphPort;
        this.recordPort = recordPort;
    }

    // Neo4j first — a Neo4j failure prevents the Postgres write and the offset commit.
    public void ingest(ResearchSignalEvent event) {
        log.info("ingesting event_id={}", event.eventId());
        graphPort.upsert(event);
        recordPort.upsert(event);
    }
}
