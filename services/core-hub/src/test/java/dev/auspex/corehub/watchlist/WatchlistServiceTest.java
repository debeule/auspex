package dev.auspex.corehub.watchlist;

import com.fasterxml.jackson.databind.ObjectMapper;
import dev.auspex.corehub.query.SignalQueryService;
import com.github.tomakehurst.wiremock.junit5.WireMockExtension;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.RegisterExtension;
import org.neo4j.driver.Driver;
import org.neo4j.driver.Result;
import org.neo4j.driver.Session;
import org.neo4j.driver.Value;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

import static com.github.tomakehurst.wiremock.client.WireMock.get;
import static com.github.tomakehurst.wiremock.client.WireMock.getRequestedFor;
import static com.github.tomakehurst.wiremock.client.WireMock.okJson;
import static com.github.tomakehurst.wiremock.client.WireMock.urlPathEqualTo;
import static com.github.tomakehurst.wiremock.core.WireMockConfiguration.wireMockConfig;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.when;
import static org.springframework.http.HttpStatus.CONFLICT;

class WatchlistServiceTest {

    @RegisterExtension
    static WireMockExtension wm = WireMockExtension.newInstance()
            .options(wireMockConfig().dynamicPort())
            .build();

    private SecTickerCache secTickerCache;
    private Driver neo4jDriver;
    private Session neo4jSession;
    private JdbcTemplate jdbcTemplate;
    private SignalQueryService signalQueryService;
    private final ObjectMapper objectMapper = new ObjectMapper();

    @BeforeEach
    void setup() {
        secTickerCache = mock(SecTickerCache.class);
        neo4jDriver = mock(Driver.class);
        neo4jSession = mock(Session.class);
        jdbcTemplate = mock(JdbcTemplate.class);
        signalQueryService = mock(SignalQueryService.class);
        when(neo4jDriver.session()).thenReturn(neo4jSession);
    }

    private WatchlistService service() {
        return new WatchlistService(neo4jDriver, jdbcTemplate, secTickerCache, signalQueryService, objectMapper,
                mock(ApplicationEventPublisher.class),
                "http://localhost:" + wm.getPort());
    }

    private Result emptyResult() {
        Result result = mock(Result.class);
        when(result.list(any())).thenReturn(List.of());
        return result;
    }

    @Test
    void test_preview_resolves_company_name_from_cached_sec_mapping() {
        when(secTickerCache.getName("SRPT")).thenReturn(Optional.of("Sarepta Therapeutics"));
        when(secTickerCache.getName("UNKNOWN")).thenReturn(Optional.empty());
        Result noResults = emptyResult();
        when(neo4jSession.run(anyString(), any(Map.class))).thenReturn(noResults);
        wm.stubFor(get(urlPathEqualTo("/api/v2/studies")).willReturn(okJson("{\"studies\":[]}")));

        WatchlistPreview known = service().preview("SRPT");
        WatchlistPreview unknown = service().preview("UNKNOWN");

        assertThat(known.companyName()).isEqualTo("Sarepta Therapeutics");
        assertThat(unknown.companyName()).isNull();
    }

    @Test
    void test_preview_skips_ct_lookup_when_company_name_null() {
        when(secTickerCache.getName("UNKNOWN")).thenReturn(Optional.empty());
        Result noResults = emptyResult();
        when(neo4jSession.run(anyString(), any(Map.class))).thenReturn(noResults);

        service().preview("UNKNOWN");

        wm.verify(0, getRequestedFor(urlPathEqualTo("/api/v2/studies")));
    }

    @Test
    void test_preview_returns_graph_gene_targets_ordered_by_signal_count() {
        when(secTickerCache.getName("SRPT")).thenReturn(Optional.of("Sarepta Therapeutics"));
        wm.stubFor(get(urlPathEqualTo("/api/v2/studies")).willReturn(okJson("{\"studies\":[]}")));

        Result graphResult = mock(Result.class);
        Value dmdName = mock(Value.class); when(dmdName.asString()).thenReturn("DMD");
        Value dmdCount = mock(Value.class); when(dmdCount.asLong()).thenReturn(14L);
        Value aavsName = mock(Value.class); when(aavsName.asString()).thenReturn("AAV9");
        Value aavsCount = mock(Value.class); when(aavsCount.asLong()).thenReturn(3L);

        org.neo4j.driver.Record dmdRow = mock(org.neo4j.driver.Record.class);
        when(dmdRow.get("name")).thenReturn(dmdName);
        when(dmdRow.get("signal_count")).thenReturn(dmdCount);

        org.neo4j.driver.Record aavRow = mock(org.neo4j.driver.Record.class);
        when(aavRow.get("name")).thenReturn(aavsName);
        when(aavRow.get("signal_count")).thenReturn(aavsCount);

        when(graphResult.list(any())).thenAnswer(inv -> {
            java.util.function.Function<org.neo4j.driver.Record, GeneTargetWithCount> mapper = inv.getArgument(0);
            return List.of(mapper.apply(dmdRow), mapper.apply(aavRow));
        });
        when(neo4jSession.run(anyString(), any(Map.class))).thenReturn(graphResult);

        WatchlistPreview preview = service().preview("SRPT");

        assertThat(preview.graphGeneTargets()).hasSize(2);
        assertThat(preview.graphGeneTargets().get(0).name()).isEqualTo("DMD");
        assertThat(preview.graphGeneTargets().get(0).signalCount()).isEqualTo(14L);
        assertThat(preview.graphGeneTargets().get(1).name()).isEqualTo("AAV9");
    }

    @Test
    void test_preview_returns_ct_suggestions_from_wiremock_stub() {
        when(secTickerCache.getName("SRPT")).thenReturn(Optional.of("Sarepta Therapeutics"));
        Result noResults = emptyResult();
        when(neo4jSession.run(anyString(), any(Map.class))).thenReturn(noResults);

        String ctJson = """
                {
                  "studies": [
                    {
                      "protocolSection": {
                        "conditionsModule": {"conditions": ["Duchenne Muscular Dystrophy"]},
                        "armsInterventionsModule": {
                          "interventions": [{"interventionMeshTerms": ["AAV9-micro-dystrophin"]}]
                        }
                      }
                    }
                  ]
                }
                """;
        wm.stubFor(get(urlPathEqualTo("/api/v2/studies")).willReturn(okJson(ctJson)));

        WatchlistPreview preview = service().preview("SRPT");

        assertThat(preview.ctSuggestions()).hasSize(2);
        assertThat(preview.ctSuggestions().get(0).term()).isEqualTo("Duchenne Muscular Dystrophy");
        assertThat(preview.ctSuggestions().get(0).type()).isEqualTo("condition");
        assertThat(preview.ctSuggestions().get(1).term()).isEqualTo("AAV9-micro-dystrophin");
        assertThat(preview.ctSuggestions().get(1).type()).isEqualTo("intervention");
    }

    @Test
    void test_add_persists_entry_and_gene_targets() {
        UUID id = UUID.randomUUID();
        when(jdbcTemplate.queryForMap(anyString(), anyString(), anyString()))
                .thenReturn(Map.of("id", id, "ticker", "BEAM",
                        "company_name", "Beam Therapeutics",
                        "added_at", java.sql.Timestamp.from(java.time.Instant.now())));
        when(jdbcTemplate.query(anyString(), any(org.springframework.jdbc.core.RowMapper.class), any()))
                .thenReturn(List.of(new WatchlistGeneTarget("BCL11A", "graph")));

        WatchlistAddRequest req = new WatchlistAddRequest(
                "BEAM", "Beam Therapeutics",
                List.of(new WatchlistGeneTarget("BCL11A", "graph")));

        WatchlistEntry entry = service().add(req);

        assertThat(entry.ticker()).isEqualTo("BEAM");
        assertThat(entry.companyName()).isEqualTo("Beam Therapeutics");
    }

    @Test
    void test_add_duplicate_ticker_returns_409() {
        when(jdbcTemplate.queryForMap(anyString(), anyString(), anyString()))
                .thenThrow(new DuplicateKeyException("duplicate key value"));

        WatchlistAddRequest req = new WatchlistAddRequest("BEAM", "Beam Therapeutics", List.of());

        assertThatThrownBy(() -> service().add(req))
                .hasFieldOrPropertyWithValue("statusCode", CONFLICT);
    }

    @Test
    void test_patch_gene_targets_adds_and_removes_selectively() {
        UUID id = UUID.randomUUID();
        when(jdbcTemplate.queryForObject(anyString(), any(Class.class), anyString())).thenReturn(id);
        when(jdbcTemplate.query(anyString(), any(org.springframework.jdbc.core.RowMapper.class), any()))
                .thenReturn(List.of(new WatchlistGeneTarget("HBB", "manual")));

        List<WatchlistGeneTarget> result = service().patchGeneTargets(
                "BEAM", new WatchlistPatchRequest(List.of("HBB"), List.of("DMD")));

        assertThat(result).hasSize(1);
        assertThat(result.get(0).geneTarget()).isEqualTo("HBB");
    }

    @Test
    void test_summary_corroborations_filtered_to_tracked_gene_targets() {
        UUID id = UUID.randomUUID();
        when(jdbcTemplate.queryForMap(anyString(), any(Object[].class)))
                .thenReturn(Map.of("id", id, "company_name", "Sarepta Therapeutics"));
        when(jdbcTemplate.query(anyString(), any(org.springframework.jdbc.core.RowMapper.class), any()))
                .thenReturn(List.of(new WatchlistGeneTarget("DMD", "graph")));

        // queryFilteredCorroborations: one match, one non-match — JdbcTemplate stub returns just the match
        var matchingCorr = new WatchlistSummary.CorroborationRef("DMD | GeneTarget",
                java.time.Instant.now(), 0.66);
        when(jdbcTemplate.query(any(org.springframework.jdbc.core.PreparedStatementCreator.class),
                any(org.springframework.jdbc.core.RowMapper.class)))
                .thenReturn(List.of(matchingCorr));

        // Neo4j session for gene target stats and count queries
        Result emptyNeo4j = mock(Result.class);
        when(emptyNeo4j.hasNext()).thenReturn(false);
        when(neo4jSession.run(anyString(), any(Map.class))).thenReturn(emptyNeo4j);

        WatchlistSummary summary = service().summary("SRPT");

        assertThat(summary.corroborations()).hasSize(1);
        assertThat(summary.corroborations().get(0).entityKey()).startsWith("DMD");
    }
}
