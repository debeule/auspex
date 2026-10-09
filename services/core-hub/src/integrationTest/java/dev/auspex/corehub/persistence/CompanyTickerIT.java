package dev.auspex.corehub.persistence;

import dev.auspex.corehub.AbstractIT;
import dev.auspex.corehub.signal.ResearchSignalEvent;
import dev.auspex.corehub.watchlist.SecTickerCache;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.neo4j.driver.Session;
import org.neo4j.driver.Value;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.WebApplicationContext;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class CompanyTickerIT extends AbstractIT {

    @Autowired
    Neo4jWriteService neo4jWriteService;

    @Autowired
    SecTickerCache secTickerCache;

    @Autowired
    WebApplicationContext webApplicationContext;

    GraphTestEvents events;
    MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        events = new GraphTestEvents(objectMapper);
        mockMvc = MockMvcBuilders.webAppContextSetup(webApplicationContext).build();
        jdbcTemplate.execute("TRUNCATE watchlist CASCADE");
    }

    @AfterEach
    void emptySecTickers() {
        secTickerCache.replaceEntries(Map.of());
    }

    @Test
    void companyMatchingOneSecTitleGetsItsTicker() {
        secTickerCache.replaceEntries(Map.of("BEAM", "Beam Therapeutics Inc.", "SRPT", "Sarepta Therapeutics, Inc."));

        neo4jWriteService.upsert(mentioning("Beam Therapeutics"));

        assertThat(tickerOf("Beam Therapeutics").asString()).isEqualTo("BEAM");
    }

    @Test
    void companyMatchingTwoSecTitlesGetsNoTicker() {
        secTickerCache.replaceEntries(Map.of("ACME", "Acme Corp", "ACMB", "ACME, Inc."));

        neo4jWriteService.upsert(mentioning("Acme"));

        assertThat(tickerOf("Acme").isNull()).isTrue();
    }

    @Test
    void existingTickerIsNotClearedByALaterUnmatchedMerge() {
        secTickerCache.replaceEntries(Map.of("BEAM", "Beam Therapeutics Inc."));
        neo4jWriteService.upsert(mentioning("Beam Therapeutics"));

        secTickerCache.replaceEntries(Map.of());
        neo4jWriteService.upsert(mentioning("Beam Therapeutics"));

        assertThat(tickerOf("Beam Therapeutics").asString()).isEqualTo("BEAM");
    }

    @Test
    void addingAWatchlistTickerBackfillsTheMatchingCompanyNode() throws Exception {
        neo4jWriteService.upsert(mentioning("Sarepta Therapeutics"));
        assertThat(tickerOf("Sarepta Therapeutics").isNull()).isTrue();

        secTickerCache.replaceEntries(Map.of("SRPT", "SAREPTA THERAPEUTICS, INC."));
        mockMvc.perform(post("/api/v1/watchlist")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"ticker":"SRPT","company_name":"SAREPTA THERAPEUTICS, INC.","gene_targets":[]}
                                """))
                .andExpect(status().isCreated());

        assertThat(tickerOf("Sarepta Therapeutics").asString()).isEqualTo("SRPT");
    }

    @Test
    void signalsByTickerReturnsSignalsMentioningTheTickeredCompany() throws Exception {
        secTickerCache.replaceEntries(Map.of("BEAM", "Beam Therapeutics Inc."));
        ResearchSignalEvent event = mentioning("Beam Therapeutics");
        neo4jWriteService.upsert(event);

        mockMvc.perform(get("/api/v1/signals/{ticker}", "BEAM"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.direct_signals.length()").value(1))
                .andExpect(jsonPath("$.direct_signals[0].event_id").value(event.eventId().toString()));
    }

    private ResearchSignalEvent mentioning(String company) {
        return events.event("biorxiv", List.of("BCL11A"), List.of("base editing"), List.of(company));
    }

    private Value tickerOf(String companyName) {
        try (Session session = neo4jDriver.session()) {
            return session.run("MATCH (c:Company {name: $name}) RETURN c.ticker AS ticker",
                    Map.of("name", companyName)).single().get("ticker");
        }
    }
}
