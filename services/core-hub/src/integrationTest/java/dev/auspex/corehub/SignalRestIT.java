package dev.auspex.corehub;

import org.hamcrest.Matchers;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.neo4j.driver.Session;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.WebApplicationContext;

import java.sql.Array;
import java.sql.PreparedStatement;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class SignalRestIT extends AbstractIT {

    // Fixed event IDs for this test class (different prefix from corroboration tests)
    private static final String R1 = "aaaaaaaa-0000-0000-0000-000000000001"; // biorxiv, MRNA, BCL11A
    private static final String R2 = "aaaaaaaa-0000-0000-0000-000000000002"; // sec_edgar, BCL11A only
    private static final String R3 = "aaaaaaaa-0000-0000-0000-000000000003"; // clinicaltrials, MRNA, no shared entity
    private static final String R4 = "aaaaaaaa-0000-0000-0000-000000000004"; // fda, PFE

    @Autowired
    WebApplicationContext webApplicationContext;

    MockMvc mockMvc;

    @BeforeEach
    void setupMockMvc() {
        mockMvc = MockMvcBuilders.webAppContextSetup(webApplicationContext).build();
    }

    private void insertSignal(String eventId, String sourceType, String publishedDate, double confidence) {
        try (Session session = neo4jDriver.session()) {
            session.run("""
                    CREATE (s:Signal {event_id: $eid, source_type: $st,
                                      published_date: datetime($pd),
                                      ingested_at: datetime('2024-06-15T12:00:00Z'),
                                      title: $title, summary: 'Test summary',
                                      confidence_score: $conf})
                    """,
                    Map.of("eid", eventId, "st", sourceType, "pd", publishedDate,
                           "title", "Signal " + eventId, "conf", confidence));
        }
    }

    private void addCompanyMention(String eventId, String companyName, String ticker) {
        try (Session session = neo4jDriver.session()) {
            session.run("""
                    MATCH (s:Signal {event_id: $eid})
                    MERGE (c:Company {name: $cn})
                    SET c.ticker = $tk
                    MERGE (s)-[:MENTIONS]->(c)
                    """,
                    Map.of("eid", eventId, "cn", companyName, "tk", ticker));
        }
    }

    private void addGeneTarget(String eventId, String gene) {
        try (Session session = neo4jDriver.session()) {
            session.run("""
                    MATCH (s:Signal {event_id: $eid})
                    MERGE (g:GeneTarget {name: $gene})
                    MERGE (s)-[:TARGETS]->(g)
                    """,
                    Map.of("eid", eventId, "gene", gene));
        }
    }

    private void insertCorroboration(String entityKey, String participantsHash, String[] participantIds,
                                      int distinctSourceCount, Instant corroboratedAt, String supersededBy) {
        jdbcTemplate.update(con -> {
            PreparedStatement ps = con.prepareStatement("""
                    INSERT INTO corroboration
                        (entity_key, participants_hash, participant_event_ids,
                         distinct_source_count, corroborated_at, first_detected_at, superseded_by)
                    VALUES (?, ?, ?, ?, ?, now(), ?)
                    """);
            ps.setString(1, entityKey);
            ps.setString(2, participantsHash);
            Array arr = con.createArrayOf("uuid", participantIds);
            ps.setArray(3, arr);
            ps.setInt(4, distinctSourceCount);
            ps.setTimestamp(5, Timestamp.from(corroboratedAt));
            ps.setString(6, supersededBy);
            return ps;
        });
    }

    private int neo4jNodeCount() {
        try (Session session = neo4jDriver.session()) {
            return session.run("MATCH (n) WHERE NOT n:GraphSchema RETURN count(n) AS cnt")
                    .single().get("cnt").asInt();
        }
    }

    @Test
    void test_returns_direct_and_corroborated_signals() throws Exception {
        // R1: biorxiv, mentions MRNA company, targets BCL11A
        insertSignal(R1, "biorxiv", "2024-01-15T00:00:00Z", 0.85);
        addCompanyMention(R1, "Moderna Inc", "MRNA");
        addGeneTarget(R1, "BCL11A");

        // R2: sec_edgar, targets BCL11A only — reachable only via shared gene, not via ticker
        insertSignal(R2, "sec_edgar", "2024-01-20T00:00:00Z", 0.70);
        addGeneTarget(R2, "BCL11A");

        // R3: clinicaltrials, mentions MRNA, no shared entity with R1/R2
        insertSignal(R3, "clinicaltrials", "2024-01-10T00:00:00Z", 0.60);
        addCompanyMention(R3, "Moderna Inc", "MRNA");

        // R4: fda, mentions PFE — different ticker, must not appear
        insertSignal(R4, "fda", "2024-01-12T00:00:00Z", 0.65);
        addCompanyMention(R4, "Pfizer Inc", "PFE");

        // Corroboration for {R1, R2} on BCL11A:GeneTarget
        insertCorroboration("BCL11A:GeneTarget", "hash-r1-r2",
                new String[]{R1, R2}, 2,
                Instant.parse("2024-01-20T00:00:00Z"), null);

        mockMvc.perform(get("/api/v1/signals/{ticker}", "MRNA"))
                .andExpect(status().isOk())
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                // Direct: R1 and R3 mention MRNA
                .andExpect(jsonPath("$.direct_signals").isArray())
                .andExpect(jsonPath("$.direct_signals.length()").value(2))
                // Corroborated: one record involving BCL11A:GeneTarget (includes R2 — the product claim)
                .andExpect(jsonPath("$.corroborated_signals").isArray())
                .andExpect(jsonPath("$.corroborated_signals.length()").value(1))
                .andExpect(jsonPath("$.corroborated_signals[0].entity_key").value("BCL11A:GeneTarget"))
                // Participant list includes R2 which does not mention MRNA — the product claim
                .andExpect(jsonPath("$.corroborated_signals[0].participant_event_ids",
                        Matchers.hasItems(R1, R2)));
    }

    @Test
    void test_superseded_corroborations_are_excluded_from_responses() throws Exception {
        insertSignal(R1, "biorxiv", "2024-01-15T00:00:00Z", 0.80);
        addCompanyMention(R1, "Moderna Inc", "MRNA");
        addGeneTarget(R1, "BCL11A");

        insertSignal(R2, "sec_edgar", "2024-01-20T00:00:00Z", 0.75);
        addGeneTarget(R2, "BCL11A");

        // Superseded corroboration: superseded_by is non-null
        insertCorroboration("BCL11A:GeneTarget", "old-hash",
                new String[]{R1, R2}, 2,
                Instant.parse("2024-01-20T00:00:00Z"), "newer-hash");

        mockMvc.perform(get("/api/v1/signals/{ticker}", "MRNA"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.direct_signals.length()").value(1))
                .andExpect(jsonPath("$.corroborated_signals.length()").value(0));
    }

    @Test
    void test_unknown_ticker_returns_empty_lists_not_500() throws Exception {
        mockMvc.perform(get("/api/v1/signals/{ticker}", "ZZZZ"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ticker").value("ZZZZ"))
                .andExpect(jsonPath("$.direct_signals.length()").value(0))
                .andExpect(jsonPath("$.corroborated_signals.length()").value(0));
    }

    @Test
    void test_dotted_ticker_is_accepted_and_routed() throws Exception {
        mockMvc.perform(get("/api/v1/signals/{ticker}", "BRK.A"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ticker").value("BRK.A"))
                .andExpect(jsonPath("$.direct_signals.length()").value(0));
    }

    @Test
    void test_injection_payload_is_rejected_or_bound_and_node_count_is_unchanged() throws Exception {
        insertSignal(R1, "biorxiv", "2024-01-15T00:00:00Z", 0.80);
        int nodesBefore = neo4jNodeCount();

        // Cypher injection payload — fails allowlist (contains " and spaces)
        mockMvc.perform(get("/api/v1/signals/{ticker}", "A\"OR1=1"))
                .andExpect(status().isBadRequest());

        // SQL injection payload — fails allowlist (starts with ')
        mockMvc.perform(get("/api/v1/signals/{ticker}", "'DROP-TABLE"))
                .andExpect(status().isBadRequest());

        assertThat(neo4jNodeCount()).isEqualTo(nodesBefore);
    }

    @Test
    void test_ticker_allowlist_rejects_lowercase_unicode_and_overlong() throws Exception {
        // Lowercase start
        mockMvc.perform(get("/api/v1/signals/{ticker}", "mrna"))
                .andExpect(status().isBadRequest());

        // Too long (11 chars)
        mockMvc.perform(get("/api/v1/signals/{ticker}", "TOOLONGABCDE"))
                .andExpect(status().isBadRequest());

        // Unicode character
        mockMvc.perform(get("/api/v1/signals/{ticker}", "MR★NA"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void test_confidence_score_serialized_in_0_1_range() throws Exception {
        insertSignal(R1, "biorxiv", "2024-01-15T00:00:00Z", 0.80);
        addCompanyMention(R1, "Moderna Inc", "MRNA");
        insertSignal(R2, "sec_edgar", "2024-01-20T00:00:00Z", 0.70);
        insertCorroboration("TEST:GeneTarget", "hash-test",
                new String[]{R1, R2}, 2,
                Instant.parse("2024-01-20T00:00:00Z"), null);

        mockMvc.perform(get("/api/v1/signals/{ticker}", "MRNA"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.corroborated_signals[0].confidence",
                        Matchers.allOf(Matchers.greaterThanOrEqualTo(0.0), Matchers.lessThanOrEqualTo(1.0))));
    }

    @Test
    void test_timestamps_serialized_as_utc_z() throws Exception {
        insertSignal(R1, "biorxiv", "2024-01-15T00:00:00Z", 0.80);
        addCompanyMention(R1, "Moderna Inc", "MRNA");
        insertSignal(R2, "sec_edgar", "2024-01-20T00:00:00Z", 0.70);
        insertCorroboration("BCL11A:GeneTarget", "hash-ts",
                new String[]{R1, R2}, 2,
                Instant.parse("2024-01-20T00:00:00Z"), null);

        mockMvc.perform(get("/api/v1/signals/{ticker}", "MRNA"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.direct_signals[0].published_at",
                        Matchers.endsWith("Z")))
                .andExpect(jsonPath("$.corroborated_signals[0].corroborated_at",
                        Matchers.endsWith("Z")));
    }

    @Test
    void test_error_handler_returns_structured_body_not_stacktrace() throws Exception {
        mockMvc.perform(get("/api/v1/signals/{ticker}", "bad-ticker"))
                .andExpect(status().isBadRequest())
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.message").exists())
                .andExpect(jsonPath("$.status").value(400))
                .andExpect(jsonPath("$.trace").doesNotExist())
                .andExpect(jsonPath("$.exception").doesNotExist());
    }
}
