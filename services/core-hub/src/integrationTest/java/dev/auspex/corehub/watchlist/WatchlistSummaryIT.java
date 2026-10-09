package dev.auspex.corehub.watchlist;

import dev.auspex.corehub.AbstractIT;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.neo4j.driver.Session;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.WebApplicationContext;

import static org.hamcrest.Matchers.hasSize;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class WatchlistSummaryIT extends AbstractIT {

    @Autowired
    WebApplicationContext webApplicationContext;

    MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        mockMvc = MockMvcBuilders.webAppContextSetup(webApplicationContext).build();
        jdbcTemplate.execute("TRUNCATE watchlist CASCADE");
    }

    @Test
    void summaryIncludesDirectSignalsMentioningTheCompany() throws Exception {
        jdbcTemplate.update("INSERT INTO watchlist (ticker, company_name) VALUES ('BEAM', 'Beam Therapeutics')");
        try (Session session = neo4jDriver.session()) {
            session.run("""
                    CREATE (beam:Company {ticker: 'BEAM', name: 'beam therapeutics'})
                    CREATE (other:Company {ticker: 'CRSP', name: 'crispr therapeutics'})
                    CREATE (older:Signal {event_id: 'summary-e001', source_type: 'biorxiv',
                                          title: 'Base editing in HSCs', summary: 'Preprint',
                                          published_date: datetime('2024-06-15T12:00:00Z'),
                                          confidence_score: 0.8})
                    CREATE (newer:Signal {event_id: 'summary-e002', source_type: 'sec_8k',
                                          title: 'BEAM-101 data update', summary: '8-K item 8.01',
                                          published_date: datetime('2024-09-01T20:05:00Z'),
                                          confidence_score: 0.9})
                    CREATE (unrelated:Signal {event_id: 'summary-e003', source_type: 'biorxiv',
                                              title: 'Cas9 delivery', summary: 'Other company',
                                              published_date: datetime('2024-07-01T00:00:00Z'),
                                              confidence_score: 0.7})
                    CREATE (older)-[:MENTIONS]->(beam)
                    CREATE (newer)-[:MENTIONS]->(beam)
                    CREATE (unrelated)-[:MENTIONS]->(other)
                    """);
        }

        mockMvc.perform(get("/api/v1/watchlist/BEAM/summary"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.direct_signals", hasSize(2)))
                .andExpect(jsonPath("$.direct_signals[0].event_id").value("summary-e002"))
                .andExpect(jsonPath("$.direct_signals[0].source_type").value("sec_8k"))
                .andExpect(jsonPath("$.direct_signals[0].title").value("BEAM-101 data update"))
                .andExpect(jsonPath("$.direct_signals[0].summary").value("8-K item 8.01"))
                .andExpect(jsonPath("$.direct_signals[0].confidence_score").value(0.9))
                .andExpect(jsonPath("$.direct_signals[0].published_at").value("2024-09-01T20:05:00Z"))
                .andExpect(jsonPath("$.direct_signals[1].event_id").value("summary-e001"))
                .andExpect(jsonPath("$.stats.total_direct").value(2));
    }
}
