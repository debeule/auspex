package dev.auspex.corehub;

import dev.auspex.corehub.service.CorroborationService;
import org.junit.jupiter.api.Test;
import org.neo4j.driver.Session;
import org.springframework.beans.factory.annotation.Autowired;

import java.time.Instant;
import java.util.List;
import java.util.Map;

import static java.util.concurrent.TimeUnit.SECONDS;
import static org.assertj.core.api.Assertions.assertThat;
import static org.awaitility.Awaitility.await;

/**
 * Abstract contract test for CorroborationService.
 * Any implementation must pass this suite unmodified (Steps 2.8 and 6.4).
 * Do not inline these cases into a concrete test — the class must survive substitution.
 *
 * Boundary documented: the 90-day window is INCLUSIVE (≤ 90 days corroborates).
 */
abstract class CorroborationServiceContractTest extends AbstractIT {

    // Fixed UUIDs for test signals — must be valid UUIDs for Postgres UUID[] column.
    protected static final String S1 = "00000000-0000-0000-0000-000000000001";
    protected static final String S2 = "00000000-0000-0000-0000-000000000002";
    protected static final String S3 = "00000000-0000-0000-0000-000000000003";
    protected static final String S4 = "00000000-0000-0000-0000-000000000004";
    protected static final String S5 = "00000000-0000-0000-0000-000000000005";

    @Autowired
    protected CorroborationService corroborationService;

    // ── Helpers ───────────────────────────────────────────────────────────────

    /**
     * Inserts a Signal node connected to GeneTarget entities via [:TARGETS].
     * ingestedAt defaults to a fixed past time so the EPOCH watermark covers all test signals.
     */
    protected void insertSignalWithTargets(String eventId, String sourceType, String publishedDate,
                                           String... geneTargets) {
        insertSignalWithTargets(eventId, sourceType, publishedDate,
                Instant.parse("2024-06-15T12:00:00Z"), geneTargets);
    }

    protected void insertSignalWithTargets(String eventId, String sourceType, String publishedDate,
                                           Instant ingestedAt, String... geneTargets) {
        try (Session session = neo4jDriver.session()) {
            session.run("""
                    CREATE (s:Signal {event_id: $eid, source_type: $st,
                                      published_date: datetime($pd), ingested_at: datetime($ia)})
                    WITH s
                    UNWIND $targets AS t
                    MERGE (g:GeneTarget {name: t})
                    CREATE (s)-[:TARGETS]->(g)
                    """,
                    Map.of("eid", eventId, "st", sourceType, "pd", publishedDate,
                            "ia", ingestedAt.toString(), "targets", List.of(geneTargets)));
        }
    }

    protected void insertSignalWithMechanism(String eventId, String sourceType, String publishedDate,
                                             Instant ingestedAt, String... mechanisms) {
        try (Session session = neo4jDriver.session()) {
            session.run("""
                    CREATE (s:Signal {event_id: $eid, source_type: $st,
                                      published_date: datetime($pd), ingested_at: datetime($ia)})
                    WITH s
                    UNWIND $mechs AS m
                    MERGE (n:Mechanism {name: m})
                    CREATE (s)-[:USES_MECHANISM]->(n)
                    """,
                    Map.of("eid", eventId, "st", sourceType, "pd", publishedDate,
                            "ia", ingestedAt.toString(), "mechs", List.of(mechanisms)));
        }
    }

    /** Inserts a Signal connected only via [:MENTIONS] to Company nodes — must NOT corroborate. */
    protected void insertSignalWithCompanyOnly(String eventId, String sourceType, String publishedDate,
                                               String... companies) {
        try (Session session = neo4jDriver.session()) {
            session.run("""
                    CREATE (s:Signal {event_id: $eid, source_type: $st,
                                      published_date: datetime($pd),
                                      ingested_at: datetime('2024-06-15T12:00:00Z')})
                    WITH s
                    UNWIND $comps AS c
                    MERGE (co:Company {name: c})
                    CREATE (s)-[:MENTIONS]->(co)
                    """,
                    Map.of("eid", eventId, "st", sourceType, "pd", publishedDate,
                            "comps", List.of(companies)));
        }
    }

    protected int liveCorroborationCount() {
        return jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM corroboration WHERE superseded_by IS NULL", Integer.class);
    }

    protected int totalCorroborationCount() {
        return jdbcTemplate.queryForObject("SELECT COUNT(*) FROM corroboration", Integer.class);
    }

    // ── Test cases ────────────────────────────────────────────────────────────

    @Test
    void test_two_distinct_sources_same_target_produces_one_corroboration() {
        insertSignalWithTargets(S1, "biorxiv",   "2024-01-15T00:00:00Z", "BCL11A");
        insertSignalWithTargets(S2, "sec_edgar", "2024-01-20T00:00:00Z", "BCL11A");

        corroborationService.runCorroboration();

        assertThat(liveCorroborationCount()).isEqualTo(1);
    }

    @Test
    void test_two_historical_signals_90_days_apart_corroborate_regardless_of_run_time() {
        // Three years ago — would be excluded by a naive "now − 90d" rolling window.
        // The window is between the two signals, not between each signal and today (§4, [A4]).
        insertSignalWithTargets(S1, "biorxiv",   "2022-01-01T00:00:00Z", "HBB");
        insertSignalWithTargets(S2, "sec_edgar", "2022-04-01T00:00:00Z", "HBB"); // exactly 90 days later

        corroborationService.runCorroboration();

        assertThat(liveCorroborationCount()).isEqualTo(1);
    }

    @Test
    void test_two_signals_same_source_type_produce_none() {
        insertSignalWithTargets(S1, "biorxiv", "2024-01-15T00:00:00Z", "BCL11A");
        insertSignalWithTargets(S2, "biorxiv", "2024-01-20T00:00:00Z", "BCL11A");

        corroborationService.runCorroboration();

        assertThat(liveCorroborationCount()).isEqualTo(0);
    }

    @Test
    void test_signals_91_days_apart_produce_none() {
        insertSignalWithTargets(S1, "biorxiv",   "2024-01-01T00:00:00Z", "BCL11A");
        insertSignalWithTargets(S2, "sec_edgar", "2024-04-01T00:00:00Z", "BCL11A"); // 91 days in 2024 (leap year)

        corroborationService.runCorroboration();

        assertThat(liveCorroborationCount()).isEqualTo(0);
    }

    @Test
    void test_signal_exactly_at_window_boundary() {
        // Boundary is INCLUSIVE: 90 days apart must corroborate.
        // Jan 1 → Apr 1 2023 = 90 days exactly (non-leap year: Jan=31, Feb=28, Mar=31).
        insertSignalWithTargets(S1, "biorxiv",   "2023-01-01T00:00:00Z", "CFTR");
        insertSignalWithTargets(S2, "sec_edgar", "2023-04-01T00:00:00Z", "CFTR");

        corroborationService.runCorroboration();

        assertThat(liveCorroborationCount()).isEqualTo(1);
    }

    @Test
    void test_two_signals_sharing_only_a_company_do_not_corroborate() {
        // [:MENTIONS] is not a corroborating relationship — only [:TARGETS|USES_MECHANISM] counts (§9).
        insertSignalWithCompanyOnly(S1, "biorxiv",   "2024-01-15T00:00:00Z", "Pfizer");
        insertSignalWithCompanyOnly(S2, "sec_edgar", "2024-01-20T00:00:00Z", "Pfizer");

        corroborationService.runCorroboration();

        assertThat(liveCorroborationCount()).isEqualTo(0);
    }

    @Test
    void test_high_degree_entity_is_skipped_by_the_degree_cap() {
        // application-test.yml sets corroboration.degree-cap=4.
        // Five signals on the same entity → degree=5 > cap → all skipped.
        insertSignalWithTargets(S1, "biorxiv",        "2024-01-01T00:00:00Z", "HIGH_DEGREE");
        insertSignalWithTargets(S2, "sec_edgar",      "2024-01-05T00:00:00Z", "HIGH_DEGREE");
        insertSignalWithTargets(S3, "clinicaltrials", "2024-01-10T00:00:00Z", "HIGH_DEGREE");
        insertSignalWithTargets(S4, "fda",            "2024-01-15T00:00:00Z", "HIGH_DEGREE");
        insertSignalWithTargets(S5, "patents",        "2024-01-20T00:00:00Z", "HIGH_DEGREE");

        corroborationService.runCorroboration();

        assertThat(liveCorroborationCount()).isEqualTo(0);
    }

    @Test
    void test_corroborated_at_is_latest_participant_publication_not_run_time() {
        // corroborated_at = max(participant.published_date), not Instant.now() (§4.1 [A15]).
        insertSignalWithTargets(S1, "biorxiv",   "2024-01-01T00:00:00Z", "SMN1");
        insertSignalWithTargets(S2, "sec_edgar", "2024-01-20T00:00:00Z", "SMN1"); // later publication

        corroborationService.runCorroboration();

        Instant storedCorroboratedAt = jdbcTemplate.queryForObject(
                "SELECT corroborated_at FROM corroboration WHERE superseded_by IS NULL",
                (rs, n) -> rs.getTimestamp("corroborated_at").toInstant());
        assertThat(storedCorroboratedAt).isEqualTo(Instant.parse("2024-01-20T00:00:00Z"));
    }

    @Test
    void test_repeated_scheduler_runs_do_not_duplicate() {
        insertSignalWithTargets(S1, "biorxiv",   "2024-01-15T00:00:00Z", "ADA");
        insertSignalWithTargets(S2, "sec_edgar", "2024-01-20T00:00:00Z", "ADA");

        corroborationService.runCorroboration();
        assertThat(totalCorroborationCount()).isEqualTo(1);

        corroborationService.runCorroboration();
        assertThat(totalCorroborationCount()).isEqualTo(1);
    }

    @Test
    void test_watermark_advances_and_is_not_reprocessed() {
        Instant t1 = Instant.parse("2024-06-01T10:00:00Z");
        insertSignalWithTargets(S1, "biorxiv",   "2024-01-15T00:00:00Z", t1, "RAG1");
        insertSignalWithTargets(S2, "sec_edgar", "2024-01-20T00:00:00Z", t1, "RAG1");

        corroborationService.runCorroboration(); // watermark advances to t1
        assertThat(totalCorroborationCount()).isEqualTo(1);

        // Second run: watermark = t1, no signals with ingested_at > t1 → no new work
        corroborationService.runCorroboration();
        assertThat(totalCorroborationCount()).isEqualTo(1);
    }

    @Test
    void test_fourth_signal_supersedes_rather_than_duplicating() {
        // Three signals corroborated in run 1; a fourth joins in run 2.
        Instant early = Instant.parse("2024-06-01T10:00:00Z");
        Instant later = Instant.parse("2024-06-01T11:00:00Z");

        insertSignalWithTargets(S1, "biorxiv",        "2024-01-01T00:00:00Z", early, "BRCA1");
        insertSignalWithTargets(S2, "sec_edgar",      "2024-01-10T00:00:00Z", early, "BRCA1");
        insertSignalWithTargets(S3, "clinicaltrials", "2024-01-20T00:00:00Z", early, "BRCA1");

        corroborationService.runCorroboration(); // run 1: watermark = early

        assertThat(liveCorroborationCount()).isGreaterThanOrEqualTo(1);

        // Fourth signal triggers supersession of every smaller subset.
        insertSignalWithTargets(S4, "fda", "2024-01-25T00:00:00Z", later, "BRCA1");
        corroborationService.runCorroboration(); // run 2

        // Exactly one live record (the largest participant set).
        assertThat(liveCorroborationCount()).isEqualTo(1);
        int distinctSources = jdbcTemplate.queryForObject(
                "SELECT distinct_source_count FROM corroboration WHERE superseded_by IS NULL",
                Integer.class);
        assertThat(distinctSources).isEqualTo(4);
    }

    @Test
    void test_superseded_rows_are_retained_for_backtesting_but_excluded_from_notifications() {
        Instant early = Instant.parse("2024-06-01T10:00:00Z");
        Instant later = Instant.parse("2024-06-01T11:00:00Z");

        insertSignalWithTargets(S1, "biorxiv",   "2024-01-01T00:00:00Z", early, "PCSK9");
        insertSignalWithTargets(S2, "sec_edgar", "2024-01-10T00:00:00Z", early, "PCSK9");
        corroborationService.runCorroboration(); // run 1: creates {S1,S2}

        await().atMost(5, SECONDS).untilAsserted(() ->
                assertThat(testCorroboratedListener.records()).hasSize(1)); // {S1,S2} published

        insertSignalWithTargets(S3, "clinicaltrials", "2024-01-20T00:00:00Z", later, "PCSK9");
        corroborationService.runCorroboration(); // run 2: creates {S1,S2,S3}, supersedes {S1,S2}

        // DB: superseded row is retained, not deleted
        assertThat(totalCorroborationCount()).isGreaterThanOrEqualTo(2);
        assertThat(liveCorroborationCount()).isEqualTo(1);

        // Notifications: {S1,S2,S3} published in run 2; {S1,S2} NOT re-published
        await().atMost(5, SECONDS).untilAsserted(() ->
                assertThat(testCorroboratedListener.records()).hasSize(2));
    }

    @Test
    void test_corroboration_via_mechanism_when_no_gene_target() {
        Instant t = Instant.parse("2024-06-15T12:00:00Z");
        insertSignalWithMechanism(S1, "biorxiv",   "2024-01-15T00:00:00Z", t, "base editing");
        insertSignalWithMechanism(S2, "sec_edgar", "2024-01-20T00:00:00Z", t, "base editing");

        corroborationService.runCorroboration();

        assertThat(liveCorroborationCount()).isEqualTo(1);
        String entityKey = jdbcTemplate.queryForObject(
                "SELECT entity_key FROM corroboration WHERE superseded_by IS NULL", String.class);
        assertThat(entityKey).isEqualTo("base editing:Mechanism");
    }

    @Test
    void test_three_distinct_sources_produce_one_live_record_not_one_per_pair() {
        insertSignalWithTargets(S1, "biorxiv",        "2024-01-01T00:00:00Z", "VEGFA");
        insertSignalWithTargets(S2, "sec_edgar",      "2024-01-10T00:00:00Z", "VEGFA");
        insertSignalWithTargets(S3, "clinicaltrials", "2024-01-20T00:00:00Z", "VEGFA");

        corroborationService.runCorroboration();

        assertThat(liveCorroborationCount()).isEqualTo(1);
        int distinctSources = jdbcTemplate.queryForObject(
                "SELECT distinct_source_count FROM corroboration WHERE superseded_by IS NULL",
                Integer.class);
        assertThat(distinctSources).isEqualTo(3);
    }

    @Test
    void test_corroboration_survives_reextraction_of_a_participant() {
        Instant t1 = Instant.parse("2024-06-01T10:00:00Z");
        Instant t2 = Instant.parse("2024-06-01T11:00:00Z");

        insertSignalWithTargets(S1, "biorxiv",   "2024-01-15T00:00:00Z", t1, "FLT3");
        insertSignalWithTargets(S2, "sec_edgar", "2024-01-20T00:00:00Z", t1, "FLT3");
        corroborationService.runCorroboration(); // creates {S1,S2}
        assertThat(totalCorroborationCount()).isEqualTo(1);

        // Re-extraction: same event_id, updated ingested_at (simulates re-processing via listener)
        try (Session session = neo4jDriver.session()) {
            session.run("MATCH (s:Signal {event_id: $eid}) SET s.ingested_at = datetime($ia)",
                    Map.of("eid", S1, "ia", t2.toString()));
        }

        corroborationService.runCorroboration(); // re-processes S1 — same group, same hash
        assertThat(totalCorroborationCount()).isEqualTo(1); // no duplicate
    }
}
