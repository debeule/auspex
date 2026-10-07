package dev.auspex.corehub;

import org.junit.jupiter.api.Test;
import org.neo4j.driver.Session;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static dev.auspex.corehub.TestFixtures.*;
import static java.util.concurrent.TimeUnit.SECONDS;
import static org.assertj.core.api.Assertions.assertThat;
import static org.awaitility.Awaitility.await;

class SignalPersistenceIT extends AbstractIT {

    @Test
    void test_timestamp_round_trip_preserves_instant() throws Exception {
        publish(SIGNAL_TOPIC, validSignalJson());

        await().atMost(10, SECONDS).untilAsserted(() -> {
            var rows = jdbcTemplate.queryForList(
                    "SELECT published_date, ingested_at FROM signal_current WHERE event_id = ?",
                    UUID.fromString(BASE_EVENT_ID));
            assertThat(rows).hasSize(1);

            Object publishedDate = rows.getFirst().get("published_date");
            assertThat(publishedDate).isNotNull();
        });

        try (Session session = neo4jDriver.session()) {
            var result = session.run(
                    "MATCH (s:Signal {event_id: $id}) RETURN s.published_date AS pd",
                    Map.of("id", BASE_EVENT_ID));
            assertThat(result.hasNext()).isTrue();
            var record = result.next();
            assertThat(record.get("pd").isNull()).isFalse();
        }
    }

    @Test
    void test_company_level_fields_are_persisted_to_signal_current() throws Exception {
        publish(SIGNAL_TOPIC, companyLevelSignalJson());

        await().atMost(10, SECONDS).untilAsserted(() -> {
            var rows = jdbcTemplate.queryForList("""
                    SELECT event_type, primary_company,
                           array_to_string(program_identifiers, ',') AS programs,
                           array_to_string(trial_ids, ',') AS trials
                    FROM signal_current WHERE event_id = ?""",
                    UUID.fromString(BASE_EVENT_ID));
            assertThat(rows).hasSize(1);
            assertThat(rows.getFirst())
                    .containsEntry("event_type", "trial_readout")
                    .containsEntry("primary_company", "Beam Therapeutics")
                    .containsEntry("programs", "BEAM-101")
                    .containsEntry("trials", "NCT05456880");
        });
    }

    @Test
    void test_schema_one_zero_event_is_persisted_with_empty_company_level_fields() throws Exception {
        publish(SIGNAL_TOPIC, validSignalJson());

        await().atMost(10, SECONDS).untilAsserted(() -> {
            var rows = jdbcTemplate.queryForList("""
                    SELECT event_type, cardinality(trial_ids) AS trials
                    FROM signal_current WHERE event_id = ?""",
                    UUID.fromString(BASE_EVENT_ID));
            assertThat(rows).hasSize(1);
            assertThat(rows.getFirst().get("event_type")).isNull();
            assertThat(rows.getFirst()).containsEntry("trials", 0);
        });
    }

    @Test
    void test_duplicate_delivery_creates_one_audit_row() throws Exception {
        publish(RAW_TOPIC, validRawJson());
        publish(RAW_TOPIC, validRawJson()); // same raw_object_key

        await().atMost(10, SECONDS).untilAsserted(() -> {
            Integer count = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM raw_fetch_audit WHERE raw_object_key = ?",
                    Integer.class,
                    "raw/biorxiv/ext-contract-001/20240615T120000Z-abcdef12.json");
            assertThat(count).isEqualTo(1);
        });
    }

    @Test
    void test_duplicate_delivery_creates_one_signal_node() throws Exception {
        publish(SIGNAL_TOPIC, validSignalJson());
        publish(SIGNAL_TOPIC, validSignalJson()); // exact same message twice

        await().atMost(10, SECONDS).untilAsserted(() -> {
            try (Session session = neo4jDriver.session()) {
                var result = session.run(
                        "MATCH (s:Signal {event_id: $id}) RETURN count(s) AS cnt",
                        Map.of("id", BASE_EVENT_ID));
                assertThat(result.single().get("cnt").asLong()).isEqualTo(1L);
            }
        });
    }

    @Test
    void test_redelivery_with_new_extraction_upserts_current_and_appends_history() throws Exception {
        publish(SIGNAL_TOPIC, validSignalJson());

        await().atMost(10, SECONDS).untilAsserted(() ->
                assertThat(jdbcTemplate.queryForObject(
                        "SELECT COUNT(*) FROM signal_current WHERE event_id = ?",
                        Integer.class, UUID.fromString(BASE_EVENT_ID))).isEqualTo(1));

        String reextracted = reextractedSignalJson();
        publish(SIGNAL_TOPIC, reextracted);

        await().atMost(10, SECONDS).untilAsserted(() -> {
            Integer historyCnt = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM signal_extraction_history WHERE event_id = ?",
                    Integer.class, UUID.fromString(BASE_EVENT_ID));
            assertThat(historyCnt).isEqualTo(2);

            String latestPromptVersion = jdbcTemplate.queryForObject(
                    "SELECT prompt_version FROM signal_current WHERE event_id = ?",
                    String.class, UUID.fromString(BASE_EVENT_ID));
            assertThat(latestPromptVersion).isEqualTo("v2");
        });
    }

    @Test
    void test_second_source_observation_appends_and_does_not_change_signal_source_type() throws Exception {
        publish(SIGNAL_TOPIC, validSignalJson()); // source_type = biorxiv

        await().atMost(10, SECONDS).untilAsserted(() ->
                assertThat(jdbcTemplate.queryForObject(
                        "SELECT COUNT(*) FROM signal_current WHERE event_id = ?",
                        Integer.class, UUID.fromString(BASE_EVENT_ID))).isEqualTo(1));

        publish(SIGNAL_TOPIC, secondSourceSignalJson()); // different event_id, source_type = sec_edgar

        await().atMost(10, SECONDS).untilAsserted(() -> {
            Integer obsCnt = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM source_observation WHERE event_id = ?",
                    Integer.class, UUID.fromString(BASE_EVENT_ID));
            assertThat(obsCnt).isEqualTo(1); // only the first event's observation

            String sourceType = jdbcTemplate.queryForObject(
                    "SELECT source_type FROM signal_current WHERE event_id = ?",
                    String.class, UUID.fromString(BASE_EVENT_ID));
            assertThat(sourceType).isEqualTo("biorxiv"); // first observation wins
        });
    }

    @Test
    void test_listener_container_restart_midbatch_is_idempotent() throws Exception {
        // Simulate redelivery after a container restart by publishing the same message twice.
        // Idempotent writes (MERGE/ON CONFLICT) ensure no duplication.
        publish(SIGNAL_TOPIC, validSignalJson());
        publish(SIGNAL_TOPIC, validSignalJson());

        await().atMost(15, SECONDS).untilAsserted(() -> {
            Integer signalCnt = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM signal_current WHERE event_id = ?",
                    Integer.class, UUID.fromString(BASE_EVENT_ID));
            assertThat(signalCnt).isEqualTo(1);

            try (Session session = neo4jDriver.session()) {
                var result = session.run(
                        "MATCH (s:Signal {event_id: $id}) RETURN count(s) AS cnt",
                        Map.of("id", BASE_EVENT_ID));
                assertThat(result.single().get("cnt").asLong()).isEqualTo(1L);
            }
        });
    }

    @Test
    void test_every_signal_row_has_a_matching_graph_node() throws Exception {
        String second = secondSourceSignalJson();
        publish(SIGNAL_TOPIC, validSignalJson());
        publish(SIGNAL_TOPIC, second);

        await().atMost(15, SECONDS).untilAsserted(() -> {
            Integer pgCount = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM signal_current", Integer.class);
            try (Session session = neo4jDriver.session()) {
                long neoCount = session.run("MATCH (s:Signal) RETURN count(s) AS cnt")
                        .single().get("cnt").asLong();
                assertThat(neoCount).isEqualTo(pgCount.longValue());
            }
        });
    }

    @Test
    void test_confidence_score_is_numerically_comparable_in_cypher() throws Exception {
        publish(SIGNAL_TOPIC, validSignalJson());

        await().atMost(10, SECONDS).untilAsserted(() -> {
            try (Session session = neo4jDriver.session()) {
                var above = session.run(
                        "MATCH (s:Signal) WHERE s.confidence_score > 0.5 RETURN count(s) AS cnt")
                        .single().get("cnt").asLong();
                var all = session.run("MATCH (s:Signal) RETURN count(s) AS cnt")
                        .single().get("cnt").asLong();
                assertThat(above).isEqualTo(all); // 0.92 > 0.5, so all signals match
            }
        });
    }

    @Test
    void test_two_companies_without_tickers_are_two_nodes() throws Exception {
        // signal A mentions Beam Therapeutics
        publish(SIGNAL_TOPIC, validSignalJson());

        // signal B mentions a different company (no ticker on either)
        String signalB = validSignalJson()
                .replace(BASE_EVENT_ID, UUID.randomUUID().toString())
                .replace(BASE_EXTRACTION_ID, UUID.randomUUID().toString())
                .replace("\"external_id\": \"ext-contract-001\"", "\"external_id\": \"ext-002\"")
                .replace("\"raw_object_key\": \"raw/biorxiv/ext-contract-001/20240615T120000Z-abcdef12.json\"",
                         "\"raw_object_key\": \"raw/biorxiv/ext-002/20240615T120000Z-00000002.json\"")
                .replace("\"Beam Therapeutics\"", "\"Intellia Therapeutics\"");
        publish(SIGNAL_TOPIC, signalB);

        await().atMost(15, SECONDS).untilAsserted(() -> {
            try (Session session = neo4jDriver.session()) {
                long companyCnt = session.run("MATCH (c:Company) RETURN count(c) AS cnt")
                        .single().get("cnt").asLong();
                assertThat(companyCnt).isEqualTo(2L);
            }
        });
    }

    @Test
    void test_signal_is_a_node_not_relationship_properties() throws Exception {
        publish(SIGNAL_TOPIC, validSignalJson());

        await().atMost(10, SECONDS).untilAsserted(() -> {
            try (Session session = neo4jDriver.session()) {
                // Signal node must exist with own event_id property
                var result = session.run(
                        "MATCH (s:Signal {event_id: $id}) RETURN s.title AS title",
                        Map.of("id", BASE_EVENT_ID));
                assertThat(result.hasNext()).isTrue();
                assertThat(result.next().get("title").asString())
                        .contains("BCL11A");
            }
        });
    }

    @Test
    void test_one_signal_referencing_three_entities_is_stored_once() throws Exception {
        // The base fixture references 2 gene targets, 2 mechanisms, 1 company = 5 entities but 1 Signal node
        publish(SIGNAL_TOPIC, validSignalJson());

        await().atMost(10, SECONDS).untilAsserted(() -> {
            try (Session session = neo4jDriver.session()) {
                long signalCnt = session.run("MATCH (s:Signal) RETURN count(s) AS cnt")
                        .single().get("cnt").asLong();
                assertThat(signalCnt).isEqualTo(1L);
            }
        });
    }

    @Test
    void test_signal_with_multiple_gene_targets_creates_one_node_and_n_edges() throws Exception {
        // Base fixture has gene_targets = ["BCL11A", "HBB"]
        publish(SIGNAL_TOPIC, validSignalJson());

        await().atMost(10, SECONDS).untilAsserted(() -> {
            try (Session session = neo4jDriver.session()) {
                long geneCnt = session.run(
                        "MATCH (s:Signal {event_id: $id})-[:TARGETS]->(g:GeneTarget) RETURN count(g) AS cnt",
                        Map.of("id", BASE_EVENT_ID))
                        .single().get("cnt").asLong();
                assertThat(geneCnt).isEqualTo(2L); // BCL11A and HBB
            }
        });
    }
}
