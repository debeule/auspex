package dev.auspex.corehub.persistence;

import dev.auspex.corehub.AbstractIT;
import dev.auspex.corehub.config.Neo4jSchemaInitializer;
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
    Neo4jSchemaInitializer schemaInitializer;

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

    @Test
    void startupRewritesExistingViaRelationshipsToUsesMechanism() {
        seedViaLink("sig-via-1", "base editing");
        seedViaLink("sig-via-2", "exon skipping");

        schemaInitializer.initSchema();

        assertThat(count("MATCH ()-[r:VIA]->() RETURN count(r) AS n", Map.of())).isZero();
        assertThat(count("""
                MATCH (s:Signal)-[:USES_MECHANISM]->(m:Mechanism)
                WHERE [s.event_id, m.name] IN [['sig-via-1', 'base editing'], ['sig-via-2', 'exon skipping']]
                RETURN count(*) AS n
                """, Map.of())).isEqualTo(2);
    }

    @Test
    void relationshipRewriteIsIdempotentAcrossRestarts() {
        seedViaLink("sig-via-1", "base editing");
        try (Session session = neo4jDriver.session()) {
            session.run("""
                    MATCH (s:Signal {event_id: 'sig-via-1'}), (m:Mechanism {name: 'base editing'})
                    CREATE (s)-[:USES_MECHANISM]->(m)
                    """);
        }

        schemaInitializer.initSchema();
        schemaInitializer.initSchema();

        assertThat(count("MATCH ()-[r:VIA]->() RETURN count(r) AS n", Map.of())).isZero();
        assertThat(count("""
                MATCH (:Signal {event_id: 'sig-via-1'})-[r:USES_MECHANISM]->(:Mechanism {name: 'base editing'})
                RETURN count(r) AS n
                """, Map.of())).isEqualTo(1);
    }

    private void seedViaLink(String eventId, String mechanism) {
        try (Session session = neo4jDriver.session()) {
            session.run("""
                    MERGE (s:Signal {event_id: $eventId})
                    MERGE (m:Mechanism {name: $mechanism})
                    CREATE (s)-[:VIA]->(m)
                    """, Map.of("eventId", eventId, "mechanism", mechanism));
        }
    }

    private long count(String cypher, Map<String, Object> params) {
        try (Session session = neo4jDriver.session()) {
            return session.run(cypher, params).single().get("n").asLong();
        }
    }
}
