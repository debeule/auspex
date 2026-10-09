package dev.auspex.corehub.persistence;

import dev.auspex.corehub.AbstractIT;
import dev.auspex.corehub.corroboration.CorroborationService;
import dev.auspex.corehub.signal.ResearchSignalEvent;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.neo4j.driver.Session;
import org.springframework.beans.factory.annotation.Autowired;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class MechanismRelationshipIT extends AbstractIT {

    @Autowired
    Neo4jWriteService neo4jWriteService;

    @Autowired
    CorroborationService corroborationService;

    GraphTestEvents events;

    @BeforeEach
    void setUpEvents() {
        events = new GraphTestEvents(objectMapper);
    }

    @Test
    void mechanismLinkIsWrittenAsUsesMechanism() {
        ResearchSignalEvent event = events.event("biorxiv", List.of("BCL11A"),
                List.of("base editing", "CRISPR"), List.of());

        neo4jWriteService.upsert(event);

        assertThat(count("""
                MATCH (:Signal {event_id: $eventId})-[:USES_MECHANISM]->(m:Mechanism)
                RETURN count(m) AS n
                """, Map.of("eventId", event.eventId().toString()))).isEqualTo(2);
        assertThat(count("MATCH ()-[r:VIA]->() RETURN count(r) AS n", Map.of())).isZero();
    }

    @Test
    void twoSourcesSharingOnlyAMechanismProduceACorroboration() {
        neo4jWriteService.upsert(events.event("biorxiv", List.of("HBB"), List.of("prime editing"), List.of()));
        neo4jWriteService.upsert(events.event("clinicaltrials", List.of("DMD"), List.of("prime editing"), List.of()));

        corroborationService.runCorroboration();

        List<String> keys = jdbcTemplate.queryForList(
                "SELECT entity_key FROM corroboration WHERE superseded_by IS NULL", String.class);
        assertThat(keys).containsExactly("prime editing:Mechanism");
    }

    private long count(String cypher, Map<String, Object> params) {
        try (Session session = neo4jDriver.session()) {
            return session.run(cypher, params).single().get("n").asLong();
        }
    }
}
