package dev.auspex.corehub;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.neo4j.driver.Session;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.WebApplicationContext;

import java.util.Map;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class WatchlistIT extends AbstractIT {

    @Autowired
    WebApplicationContext webApplicationContext;

    MockMvc mockMvc;

    @BeforeEach
    void setupMockMvc() {
        mockMvc = MockMvcBuilders.webAppContextSetup(webApplicationContext).build();
    }

    @BeforeEach
    void cleanWatchlist() {
        jdbcTemplate.execute("TRUNCATE watchlist CASCADE");
    }

    @Test
    void test_watchlist_entry_persists_and_cascades_on_delete() throws Exception {
        String addBody = """
                {"ticker":"SRPT","company_name":"Sarepta Therapeutics",
                 "gene_targets":[{"gene_target":"DMD","source":"graph"}]}
                """;

        mockMvc.perform(post("/api/v1/watchlist")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(addBody))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.ticker").value("SRPT"));

        Integer watchlistCount = jdbcTemplate.queryForObject(
                "SELECT count(*) FROM watchlist WHERE ticker = 'SRPT'", Integer.class);
        Integer geneTargetCount = jdbcTemplate.queryForObject(
                "SELECT count(*) FROM watchlist_gene_target wgt " +
                "JOIN watchlist w ON w.id = wgt.watchlist_id WHERE w.ticker = 'SRPT'", Integer.class);
        assertThat(watchlistCount).isEqualTo(1);
        assertThat(geneTargetCount).isEqualTo(1);

        mockMvc.perform(delete("/api/v1/watchlist/SRPT"))
                .andExpect(status().isNoContent());

        Integer afterDelete = jdbcTemplate.queryForObject(
                "SELECT count(*) FROM watchlist WHERE ticker = 'SRPT'", Integer.class);
        Integer geneTargetAfterDelete = jdbcTemplate.queryForObject(
                "SELECT count(*) FROM watchlist_gene_target", Integer.class);
        assertThat(afterDelete).isEqualTo(0);
        assertThat(geneTargetAfterDelete).isEqualTo(0);
    }

    @Test
    void test_summary_queries_neo4j_and_postgres() throws Exception {
        // Seed watchlist entry
        jdbcTemplate.update(
                "INSERT INTO watchlist (ticker, company_name) VALUES ('BEAM', 'Beam Therapeutics')");
        UUID watchlistId = jdbcTemplate.queryForObject(
                "SELECT id FROM watchlist WHERE ticker = 'BEAM'", UUID.class);
        jdbcTemplate.update(
                "INSERT INTO watchlist_gene_target (watchlist_id, gene_target, source) VALUES (?, 'BCL11A', 'graph')",
                watchlistId);

        // Seed Neo4j
        try (Session session = neo4jDriver.session()) {
            session.run("""
                    CREATE (c:Company {ticker: 'BEAM', name: 'Beam Therapeutics'})
                    CREATE (g:GeneTarget {name: 'BCL11A'})
                    CREATE (s:Signal {event_id: 'sum-e001', source_type: 'biorxiv',
                                     published_date: datetime('2024-06-15T12:00:00Z'),
                                     confidence_score: 0.9})
                    CREATE (s)-[:MENTIONS]->(c)
                    CREATE (s)-[:TARGETS]->(g)
                    """);
        }

        // Seed Postgres corroboration with matching gene target key
        jdbcTemplate.update("""
                INSERT INTO corroboration (entity_key, participants_hash, participant_event_ids,
                                           distinct_source_count, corroborated_at)
                VALUES ('BCL11A | GeneTarget', 'testhash001',
                        ARRAY['00000000-0000-0000-0000-000000000001']::uuid[], 2, NOW())
                """);

        mockMvc.perform(get("/api/v1/watchlist/BEAM/summary"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ticker").value("BEAM"))
                .andExpect(jsonPath("$.stats.total_corroborations").value(1));
    }

    @Test
    void test_company_name_null_graceful() throws Exception {
        String body = """
                {"ticker":"XYZQ","company_name":null,"geneTargets":[]}
                """;

        mockMvc.perform(post("/api/v1/watchlist")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value(
                        org.hamcrest.Matchers.containsString("company_name")));
    }
}
