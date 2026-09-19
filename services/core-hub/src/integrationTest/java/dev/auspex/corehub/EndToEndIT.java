package dev.auspex.corehub;

import com.fasterxml.jackson.databind.JsonNode;
import com.sun.net.httpserver.HttpServer;
import dev.auspex.corehub.corroboration.CorroborationService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.WebApplicationContext;

import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.nio.file.Path;
import java.time.Duration;
import java.util.Map;
import java.util.UUID;

import static dev.auspex.corehub.TestFixtures.*;
import static java.util.concurrent.TimeUnit.SECONDS;
import static org.assertj.core.api.Assertions.assertThat;
import static org.awaitility.Awaitility.await;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;

/**
 * Full-pipeline end-to-end tests: Kafka → consumer → Neo4j/Postgres → REST.
 * Extends AbstractIT to share the single embedded Kafka + Spring context,
 * avoiding the two-broker conflict that arises with a second @EmbeddedKafka.
 * For verify_pipeline.sh, a JDK HttpServer proxies MockMvc calls to real HTTP.
 */
class EndToEndIT extends AbstractIT {

    // Minimal fixtures with a single shared gene target so corroboration produces
    // exactly one record and assertions stay deterministic.
    private static final String EID1 = "e2e00001-0000-0000-0000-000000000001";
    private static final String EID2 = "e2e00001-0000-0000-0000-000000000002";

    private static final String SIGNAL_1 = """
            {
              "schema_version": "1.0",
              "event_id": "e2e00001-0000-0000-0000-000000000001",
              "extraction_id": "e2ee0001-0000-0000-0000-000000000001",
              "external_id": "ete-biorxiv-001",
              "canonical_id": "doi:10.1101/2024.ete.001",
              "raw_object_key": "raw/biorxiv/ete-001/20240615T120000Z-aaaa0001.json",
              "source_type": "biorxiv",
              "source_url": "https://biorxiv.org/content/10.1101/2024.ete.001",
              "published_date": "2024-06-15T12:00:00Z",
              "published_date_field": "date",
              "ingested_at": "2024-06-15T12:00:00Z",
              "title": "BCL11A base editing in sickle cell disease",
              "raw_text_snippet": "BCL11A editing corrects sickle cell.",
              "gene_targets": ["BCL11A"],
              "mechanisms": [],
              "companies_mentioned": ["Beam Therapeutics"],
              "summary": "BCL11A editing shows efficacy.",
              "directionality": "positive",
              "confidence_score": 0.90,
              "prompt_version": "v1",
              "prefilter_version": "v1",
              "extraction_model": "gpt-4o"
            }
            """;

    private static final String SIGNAL_2 = """
            {
              "schema_version": "1.0",
              "event_id": "e2e00001-0000-0000-0000-000000000002",
              "extraction_id": "e2ee0001-0000-0000-0000-000000000002",
              "external_id": "ete-sec-001",
              "canonical_id": null,
              "raw_object_key": "raw/sec_edgar/ete-sec-001/20240620T000000Z-bbbb0001.json",
              "source_type": "sec_edgar",
              "source_url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany",
              "published_date": "2024-06-20T00:00:00Z",
              "published_date_field": "filed_date",
              "ingested_at": "2024-06-20T00:00:00Z",
              "title": "SEC filing referencing BCL11A programme",
              "raw_text_snippet": "BCL11A programme disclosed in 10-Q.",
              "gene_targets": ["BCL11A"],
              "mechanisms": [],
              "companies_mentioned": [],
              "summary": "BCL11A programme disclosed.",
              "directionality": "neutral",
              "confidence_score": 0.60,
              "prompt_version": "v1",
              "prefilter_version": "v1",
              "extraction_model": "gpt-4o"
            }
            """;

    // Same event_id as SIGNAL_1, new extraction_id — simulates Python re-extraction
    private static final String SIGNAL_1_REEXTRACTED = SIGNAL_1
            .replace("e2ee0001-0000-0000-0000-000000000001", "e2ee0001-0000-0000-0000-0000000000ff")
            .replace("0.90", "0.75");

    @Autowired WebApplicationContext webApplicationContext;
    @Autowired CorroborationService corroborationService;

    MockMvc mockMvc;

    @BeforeEach
    void setupMockMvc() {
        mockMvc = MockMvcBuilders.webAppContextSetup(webApplicationContext).build();
    }

    private void setTicker(String companyName, String ticker) {
        try (var session = neo4jDriver.session()) {
            session.run("MATCH (c:Company {name: $n}) SET c.ticker = $t",
                    Map.of("n", companyName, "t", ticker));
        }
    }

    private int signalCurrentCount() {
        return jdbcTemplate.queryForObject("SELECT COUNT(*) FROM signal_current", Integer.class);
    }

    private int neo4jSignalCount() {
        try (var session = neo4jDriver.session()) {
            return (int) session.run("MATCH (s:Signal) RETURN count(s) AS cnt")
                    .single().get("cnt").asLong();
        }
    }

    private JsonNode getSignals(String ticker) throws Exception {
        String body = mockMvc.perform(get("/api/v1/signals/{ticker}", ticker))
                .andReturn().getResponse().getContentAsString();
        return objectMapper.readTree(body);
    }

    private static int findFreePort() throws Exception {
        try (ServerSocket s = new ServerSocket(0)) {
            return s.getLocalPort();
        }
    }

    @Test
    void test_end_to_end_mock_ingestion_to_rest_response() throws Exception {
        // Two independent sources both targeting BCL11A → one corroboration record
        publish(SIGNAL_TOPIC, SIGNAL_1); // biorxiv, mentions Beam Therapeutics, targets BCL11A
        publish(SIGNAL_TOPIC, SIGNAL_2); // sec_edgar, targets BCL11A only

        await().atMost(10, SECONDS).until(() -> signalCurrentCount() == 2);

        setTicker("Beam Therapeutics", "BEAM");

        corroborationService.runCorroboration();

        JsonNode body = getSignals("BEAM");
        assertThat(body.at("/ticker").asText()).isEqualTo("BEAM");

        // Only SIGNAL_1 has a [:MENTIONS] edge to Beam Therapeutics (= BEAM)
        assertThat(body.at("/direct_signals").size()).isEqualTo(1);
        assertThat(body.at("/direct_signals/0/source_type").asText()).isEqualTo("biorxiv");

        // BCL11A is shared between both sources → exactly one corroboration
        assertThat(body.at("/corroborated_signals").size()).isEqualTo(1);
        assertThat(body.at("/corroborated_signals/0/entity_key").asText())
                .isEqualTo("BCL11A:GeneTarget");

        var participants = body.at("/corroborated_signals/0/participant_event_ids");
        assertThat(participants.size()).isEqualTo(2);
        assertThat(participants.toString()).contains(EID1).contains(EID2);
    }

    @Test
    void test_pipeline_is_rerunnable() throws Exception {
        publish(SIGNAL_TOPIC, SIGNAL_1);
        await().atMost(10, SECONDS).until(() -> signalCurrentCount() == 1);
        setTicker("Beam Therapeutics", "BEAM");
        corroborationService.runCorroboration();

        int pgCount   = signalCurrentCount();
        int neoCount  = neo4jSignalCount();
        int corrCount = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM corroboration", Integer.class);

        // Exact same event re-delivered (simulate consumer restart / rebalance)
        publish(SIGNAL_TOPIC, SIGNAL_1);
        corroborationService.runCorroboration();

        // All store counts must be unchanged after the second run
        await().during(Duration.ofSeconds(2)).atMost(Duration.ofSeconds(5))
               .until(() -> signalCurrentCount() == pgCount);
        assertThat(neo4jSignalCount()).isEqualTo(neoCount);
        assertThat(jdbcTemplate.queryForObject("SELECT COUNT(*) FROM corroboration", Integer.class))
                .isEqualTo(corrCount);

        // REST response unchanged
        JsonNode body = getSignals("BEAM");
        assertThat(body.at("/direct_signals").size()).isEqualTo(1);
    }

    @Test
    void test_archived_but_unpublished_document_is_republished_on_the_next_run() throws Exception {
        // First run: archived to MinIO, published to Kafka, processed
        publish(SIGNAL_TOPIC, SIGNAL_1);
        await().atMost(10, SECONDS).until(() -> signalCurrentCount() == 1);
        setTicker("Beam Therapeutics", "BEAM");

        // Kafka publish failed after MinIO write → Python re-extracts on next run.
        // Same event_id, new extraction_id — the "republished" document.
        publish(SIGNAL_TOPIC, SIGNAL_1_REEXTRACTED);

        await().atMost(10, SECONDS).untilAsserted(() -> {
            // Idempotent upsert on event_id: still exactly one current row
            assertThat(signalCurrentCount()).isEqualTo(1);
            // Both extractions are preserved in history
            assertThat(jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM signal_extraction_history WHERE event_id = ?",
                    Integer.class, UUID.fromString(EID1))).isEqualTo(2);
        });

        // REST shows one signal, not two — re-publish creates no phantom duplicate
        JsonNode body = getSignals("BEAM");
        assertThat(body.at("/direct_signals").size()).isEqualTo(1);
    }

    @Test
    void test_verify_script_exits_zero_on_clean_stack() throws Exception {
        // Bridge MockMvc to real HTTP so the bash script can call curl.
        int proxyPort = findFreePort();
        HttpServer httpServer = HttpServer.create(new InetSocketAddress(proxyPort), 0);
        httpServer.createContext("/", exchange -> {
            try {
                String path = exchange.getRequestURI().getPath();
                var result = mockMvc.perform(get(path)).andReturn();
                int status  = result.getResponse().getStatus();
                byte[] body = result.getResponse().getContentAsByteArray();
                String ct   = result.getResponse().getContentType();
                if (ct != null) exchange.getResponseHeaders().set("Content-Type", ct);
                exchange.sendResponseHeaders(status, body.length);
                try (var out = exchange.getResponseBody()) { out.write(body); }
            } catch (Exception e) {
                throw new java.io.IOException(e);
            }
        });
        httpServer.start();

        try {
            Path script = Path.of("").toAbsolutePath().resolve("../../verify_pipeline.sh");
            ProcessBuilder pb = new ProcessBuilder("bash", script.toString());
            pb.environment().put("CORE_HUB_URL", "http://localhost:" + proxyPort);
            pb.redirectErrorStream(true);
            Process process = pb.start();
            String output = new String(process.getInputStream().readAllBytes());
            boolean finished = process.waitFor(30, SECONDS);
            assertThat(finished).as("verify_pipeline.sh timed out").isTrue();
            assertThat(process.exitValue()).as("verify_pipeline.sh output:\n" + output).isEqualTo(0);
        } finally {
            httpServer.stop(0);
        }
    }
}
