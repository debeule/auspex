package dev.auspex.corehub.service;

import dev.auspex.corehub.model.ResearchSignalEvent;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Single entry point for persisting a ResearchSignalEvent.
 * Write order: Neo4j → Postgres → acknowledge.
 * Both @Transactional annotations are qualified — two TMs on the classpath.
 */
@Service
public class GraphUpdateService {

    private static final Logger log = LoggerFactory.getLogger(GraphUpdateService.class);

    private final Neo4jWriteService neo4jWriteService;
    private final PostgresWriteService postgresWriteService;

    public GraphUpdateService(
            Neo4jWriteService neo4jWriteService,
            PostgresWriteService postgresWriteService
    ) {
        this.neo4jWriteService = neo4jWriteService;
        this.postgresWriteService = postgresWriteService;
    }

    /**
     * Neo4j first, then Postgres. The offset is acknowledged only after both return.
     * A Neo4j failure here will prevent the Postgres write and the offset commit.
     */
    public void process(ResearchSignalEvent event) {
        log.info("processing event_id={}", event.eventId());
        neo4jWriteService.upsert(event);
        postgresWriteService.upsert(event);
    }
}
