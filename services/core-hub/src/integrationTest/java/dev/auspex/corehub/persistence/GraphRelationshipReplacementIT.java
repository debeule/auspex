package dev.auspex.corehub.persistence;

import dev.auspex.corehub.AbstractIT;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.neo4j.driver.Session;
import org.springframework.beans.factory.annotation.Autowired;

import java.util.List;
import java.util.Map;
import java.util.UUID;

import static java.util.concurrent.TimeUnit.SECONDS;
import static org.assertj.core.api.Assertions.assertThat;
import static org.awaitility.Awaitility.await;

class GraphRelationshipReplacementIT extends AbstractIT {

    private static final String SIGNAL_TOPIC = "auspex.signals.extracted";

    @Autowired
    Neo4jWriteService neo4jWriteService;

    GraphTestEvents events;

    @BeforeEach
    void setUpEvents() {
        events = new GraphTestEvents(objectMapper);
    }

    @Test
    void rewriteWithADifferentGeneReplacesTheTargetsEdge() {
        UUID id = UUID.randomUUID();
        neo4jWriteService.upsert(events.event(id, "biorxiv", List.of("GENE_A"), List.of(), List.of()));

        neo4jWriteService.upsert(events.event(id, "biorxiv", List.of("GENE_B"), List.of(), List.of()));

        assertThat(targets(id, "TARGETS")).containsExactly("GENE_B");
    }

    @Test
    void rewriteWithoutACompanyRemovesTheMentionsEdge() {
        UUID id = UUID.randomUUID();
        neo4jWriteService.upsert(events.event(id, "biorxiv", List.of(), List.of(),
                List.of("Beam Therapeutics", "Wrongly Mentioned Co")));

        neo4jWriteService.upsert(events.event(id, "biorxiv", List.of(), List.of(), List.of("Beam Therapeutics")));

        assertThat(targets(id, "MENTIONS")).containsExactly("Beam Therapeutics");
    }

    @Test
    void rewriteWithoutAMechanismRemovesTheUsesMechanismEdge() {
        UUID id = UUID.randomUUID();
        neo4jWriteService.upsert(events.event(id, "biorxiv", List.of(), List.of("base editing", "CRISPR"), List.of()));

        neo4jWriteService.upsert(events.event(id, "biorxiv", List.of(), List.of("base editing"), List.of()));

        assertThat(targets(id, "USES_MECHANISM")).containsExactly("base editing");
    }

    @Test
    void sharedEntityNodeAndOtherSignalsEdgesSurviveARewrite() {
        UUID rewritten = UUID.randomUUID();
        UUID other = UUID.randomUUID();
        neo4jWriteService.upsert(events.event(rewritten, "biorxiv", List.of("GENE_A"), List.of(), List.of()));
        neo4jWriteService.upsert(events.event(other, "sec_edgar", List.of("GENE_A"), List.of(), List.of()));

        neo4jWriteService.upsert(events.event(rewritten, "biorxiv", List.of("GENE_B"), List.of(), List.of()));

        assertThat(count("MATCH (g:GeneTarget {name: 'GENE_A'}) RETURN count(g) AS n", Map.of())).isEqualTo(1);
        assertThat(targets(other, "TARGETS")).containsExactly("GENE_A");
        assertThat(targets(rewritten, "TARGETS")).containsExactly("GENE_B");
    }

    @Test
    void repeatedIdenticalWriteLeavesTheGraphUnchanged() {
        UUID id = UUID.randomUUID();
        var event = events.event(id, "biorxiv", List.of("GENE_A", "GENE_B"), List.of("base editing"),
                List.of("Beam Therapeutics"));
        neo4jWriteService.upsert(event);
        String before = graphShape();

        neo4jWriteService.upsert(event);

        assertThat(graphShape()).isEqualTo(before);
        assertThat(count("MATCH ()-[r]->() RETURN count(r) AS n", Map.of())).isEqualTo(4);
    }

    @Test
    void graphAndPostgresHoldTheSameEntitiesAfterARewrite() throws Exception {
        UUID id = UUID.randomUUID();
        publish(SIGNAL_TOPIC, events.json(id, "biorxiv", List.of("GENE_A"), List.of("CRISPR"),
                List.of("Wrongly Mentioned Co")).toString());
        await().atMost(10, SECONDS).until(() -> currentArray(id, "gene_targets").equals(List.of("GENE_A")));

        publish(SIGNAL_TOPIC, events.json(id, "biorxiv", List.of("GENE_B"), List.of("base editing"),
                List.of("Beam Therapeutics")).toString());
        await().atMost(10, SECONDS).until(() -> currentArray(id, "gene_targets").equals(List.of("GENE_B")));

        assertThat(targets(id, "TARGETS")).containsExactlyInAnyOrderElementsOf(currentArray(id, "gene_targets"));
        assertThat(targets(id, "USES_MECHANISM")).containsExactlyInAnyOrderElementsOf(currentArray(id, "mechanisms"));
        assertThat(targets(id, "MENTIONS"))
                .containsExactlyInAnyOrderElementsOf(currentArray(id, "companies_mentioned"));
    }

    private List<String> targets(UUID eventId, String relationship) {
        try (Session session = neo4jDriver.session()) {
            return session.run("""
                    MATCH (s:Signal {event_id: $id})-[r]->(e)
                    WHERE type(r) = $type
                    RETURN e.name AS name ORDER BY name
                    """, Map.of("id", eventId.toString(), "type", relationship))
                    .list(r -> r.get("name").asString());
        }
    }

    private String graphShape() {
        try (Session session = neo4jDriver.session()) {
            return session.run("""
                    MATCH (n) WHERE NOT n:GraphSchema
                    OPTIONAL MATCH (n)-[r]->(m)
                    RETURN labels(n)[0] + ':' + coalesce(n.name, n.event_id) + '-' + coalesce(type(r), '')
                           + '->' + coalesce(m.name, '') AS row
                    ORDER BY row
                    """).list(r -> r.get("row").asString()).toString();
        }
    }

    private List<String> currentArray(UUID eventId, String column) {
        return jdbcTemplate.query(
                "SELECT gene_targets, mechanisms, companies_mentioned FROM signal_current WHERE event_id = ?",
                (rs, n) -> List.of((String[]) rs.getArray(column).getArray()), eventId).stream()
                .flatMap(List::stream)
                .toList();
    }

    private long count(String cypher, Map<String, Object> params) {
        try (Session session = neo4jDriver.session()) {
            return session.run(cypher, params).single().get("n").asLong();
        }
    }
}
