package dev.auspex.corehub;

import dev.auspex.corehub.corroboration.CorroborationService;
import dev.auspex.corehub.persistence.Neo4jWriteService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.WebApplicationContext;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.containsInAnyOrder;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class TickerCorroborationIT extends AbstractIT {

    @Autowired
    Neo4jWriteService graph;

    @Autowired
    CorroborationService corroborationService;

    @Autowired
    WebApplicationContext webApplicationContext;

    CorroborationSignals signals;
    MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        signals = new CorroborationSignals(objectMapper, jdbcTemplate, neo4jDriver);
        mockMvc = MockMvcBuilders.webAppContextSetup(webApplicationContext).build();
    }

    private UUID write(String sourceType, String date, String gene, List<String> companies) {
        UUID id = UUID.randomUUID();
        graph.upsert(signals.event(id, sourceType, date, sourceType + " " + date, List.of(gene), List.of(), companies));
        return id;
    }

    private List<CorroborationSignals.Row> tickerRows(String ticker) {
        return signals.live().stream().filter(r -> r.ticker().equals(ticker)).toList();
    }

    @Test
    void twoIndependentSourcesNamingOneCompanyProduceATickerRecord() {
        UUID a = write("biorxiv", "2024-01-01", "SOD1", List.of("Acme Bio"));
        UUID b = write("edgar", "2024-01-10", "SOD1", List.of("Acme Bio"));
        signals.setTicker("Acme Bio", "ACME");

        corroborationService.runCorroboration();

        assertThat(tickerRows("ACME")).singleElement().satisfies(row -> {
            assertThat(row.entityKey()).isEqualTo("SOD1:GeneTarget");
            assertThat(row.participants()).containsExactlyInAnyOrder(a, b);
            assertThat(row.distinctSourceCount()).isEqualTo(2);
        });
        assertThat(tickerRows("")).hasSize(1);
    }

    @Test
    void companyNamedByOneParticipantGetsNoTickerRecord() {
        write("biorxiv", "2024-01-01", "TTR", List.of("Acme Bio"));
        write("edgar", "2024-01-10", "TTR", List.of());
        signals.setTicker("Acme Bio", "ACME");

        corroborationService.runCorroboration();

        assertThat(signals.live()).singleElement().satisfies(row -> {
            assertThat(row.ticker()).isEmpty();
            assertThat(row.entityKey()).isEqualTo("TTR:GeneTarget");
        });
    }

    @Test
    void tickerRecordOpensWhenTheSecondSourceNamingTheCompanyIsPublished() {
        write("biorxiv", "2024-01-01", "APOE", List.of("Acme Bio"));
        write("edgar", "2024-01-10", "APOE", List.of());
        signals.setTicker("Acme Bio", "ACME");
        corroborationService.runCorroboration();
        assertThat(tickerRows("ACME")).isEmpty();

        write("clinicaltrials", "2024-02-01", "APOE", List.of("Acme Bio"));
        corroborationService.runCorroboration();

        assertThat(tickerRows("ACME")).singleElement().satisfies(row -> {
            assertThat(row.episodeOpenedAt()).isEqualTo(Instant.parse("2024-02-01T00:00:00Z"));
            assertThat(row.participants()).hasSize(2);
        });
        assertThat(tickerRows("")).singleElement().satisfies(row ->
                assertThat(row.episodeOpenedAt()).isEqualTo(Instant.parse("2024-01-10T00:00:00Z")));
    }

    @Test
    void tickerEndpointReturnsOnlyThatTickersRecords() throws Exception {
        UUID a = write("biorxiv", "2024-01-01", "PCSK9", List.of("Acme Bio"));
        UUID b = write("edgar", "2024-01-10", "PCSK9", List.of("Acme Bio", "Beta Thera"));
        write("clinicaltrials", "2024-01-20", "PCSK9", List.of("Beta Thera"));
        signals.setTicker("Acme Bio", "ACME");
        signals.setTicker("Beta Thera", "BETA");
        corroborationService.runCorroboration();
        assertThat(tickerRows("BETA")).hasSize(1);

        mockMvc.perform(get("/api/v1/signals/{ticker}", "ACME"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.corroborated_signals.length()").value(1))
                .andExpect(jsonPath("$.corroborated_signals[0].ticker").value("ACME"))
                .andExpect(jsonPath("$.corroborated_signals[0].entity_key").value("PCSK9:GeneTarget"))
                .andExpect(jsonPath("$.corroborated_signals[0].episode_opened_at").value("2024-01-10T00:00:00Z"))
                .andExpect(jsonPath("$.corroborated_signals[0].distinct_source_types",
                        containsInAnyOrder("biorxiv", "edgar")))
                .andExpect(jsonPath("$.corroborated_signals[0].participant_event_ids",
                        containsInAnyOrder(a.toString(), b.toString())))
                .andExpect(jsonPath("$.context_corroborations.length()").value(0));
    }

    @Test
    void tickerEndpointListsContextCorroborationsWithTheirReason() throws Exception {
        UUID a = write("biorxiv", "2024-01-01", "LRRK2", List.of("Acme Bio"));
        UUID b = write("edgar", "2024-01-10", "LRRK2", List.of());
        UUID c = UUID.randomUUID();
        graph.upsert(signals.event(c, "biorxiv", "2024-01-01", "c", List.of(), List.of("Gene Therapy"),
                List.of("Acme Bio")));
        UUID d = UUID.randomUUID();
        graph.upsert(signals.event(d, "edgar", "2024-01-10", "d", List.of(), List.of("gene therapy"),
                List.of("Acme Bio")));
        signals.setTicker("Acme Bio", "ACME");
        corroborationService.runCorroboration();

        mockMvc.perform(get("/api/v1/signals/{ticker}", "ACME"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.corroborated_signals.length()").value(0))
                .andExpect(jsonPath("$.context_corroborations.length()").value(2))
                .andExpect(jsonPath("$.context_corroborations[?(@.entity_key == 'LRRK2:GeneTarget')].reason")
                        .value("no_independent_pair_for_ticker"))
                .andExpect(jsonPath("$.context_corroborations[?(@.entity_key == 'LRRK2:GeneTarget')].participant_event_ids[*]",
                        containsInAnyOrder(a.toString(), b.toString())))
                .andExpect(jsonPath("$.context_corroborations[?(@.entity_key == 'gene therapy:Mechanism')].reason")
                        .value("broad_entity"))
                .andExpect(jsonPath("$.context_corroborations[?(@.entity_key == 'gene therapy:Mechanism')].participant_event_ids[*]",
                        containsInAnyOrder(c.toString(), d.toString())));
    }
}
