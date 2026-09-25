package dev.auspex.corehub.watchlist;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.neo4j.driver.Driver;
import org.neo4j.driver.Session;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatusCode;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;
import org.springframework.web.server.ResponseStatusException;

import java.time.Instant;
import java.util.*;

import static org.springframework.http.HttpStatus.CONFLICT;
import static org.springframework.http.HttpStatus.NOT_FOUND;

@Service
public class WatchlistService {

    private static final Logger log = LoggerFactory.getLogger(WatchlistService.class);
    private static final String CT_PATH = "/api/v2/studies";

    private final Driver neo4jDriver;
    private final JdbcTemplate jdbcTemplate;
    private final SecTickerCache secTickerCache;
    private final RestClient ctRestClient;
    private final ObjectMapper objectMapper;

    WatchlistService(
            Driver neo4jDriver,
            JdbcTemplate jdbcTemplate,
            SecTickerCache secTickerCache,
            ObjectMapper objectMapper,
            @Value("${auspex.clinicaltrials.base-url:https://clinicaltrials.gov}") String ctBaseUrl
    ) {
        this.neo4jDriver = neo4jDriver;
        this.jdbcTemplate = jdbcTemplate;
        this.secTickerCache = secTickerCache;
        this.objectMapper = objectMapper;
        this.ctRestClient = RestClient.builder()
                .baseUrl(ctBaseUrl)
                .defaultStatusHandler(HttpStatusCode::isError, (req, resp) ->
                        log.warn("ClinicalTrials API error: {} {}", resp.getStatusCode(), req.getURI()))
                .build();
    }

    public WatchlistPreview preview(String ticker) {
        String companyName = secTickerCache.getName(ticker).orElse(null);
        List<GeneTargetWithCount> graphGeneTargets = queryGraphGeneTargets(ticker);
        List<CtSuggestion> ctSuggestions = companyName != null
                ? fetchCtSuggestions(companyName)
                : List.of();
        return new WatchlistPreview(ticker, companyName, graphGeneTargets, ctSuggestions);
    }

    public List<WatchlistEntry> list() {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT id, ticker, company_name, added_at FROM watchlist ORDER BY added_at");
        return rows.stream().map(row -> {
            UUID id = (UUID) row.get("id");
            List<WatchlistGeneTarget> targets = listGeneTargets(id);
            return new WatchlistEntry(
                    id,
                    (String) row.get("ticker"),
                    (String) row.get("company_name"),
                    ((java.sql.Timestamp) row.get("added_at")).toInstant(),
                    targets
            );
        }).toList();
    }

    public WatchlistEntry add(WatchlistAddRequest req) {
        String ticker = req.ticker().toUpperCase();
        String companyName = req.companyName();
        if (companyName == null || companyName.isBlank()) {
            throw new ResponseStatusException(
                    org.springframework.http.HttpStatus.BAD_REQUEST,
                    "company_name is required; run preview first");
        }
        try {
            Map<String, Object> row = jdbcTemplate.queryForMap(
                    "INSERT INTO watchlist (ticker, company_name) VALUES (?, ?) RETURNING id, ticker, company_name, added_at",
                    ticker, companyName);
            UUID id = (UUID) row.get("id");
            List<WatchlistGeneTarget> targets = req.geneTargets() != null ? req.geneTargets() : List.of();
            for (WatchlistGeneTarget gt : targets) {
                String normalized = gt.geneTarget().trim().toUpperCase();
                jdbcTemplate.update(
                        "INSERT INTO watchlist_gene_target (watchlist_id, gene_target, source) VALUES (?, ?, ?)",
                        id, normalized, gt.source());
            }
            return new WatchlistEntry(
                    id, ticker, companyName,
                    ((java.sql.Timestamp) row.get("added_at")).toInstant(),
                    listGeneTargets(id));
        } catch (DuplicateKeyException ex) {
            throw new ResponseStatusException(CONFLICT, "Ticker already in watchlist: " + ticker);
        }
    }

    public void delete(String ticker) {
        int deleted = jdbcTemplate.update("DELETE FROM watchlist WHERE ticker = ?", ticker.toUpperCase());
        if (deleted == 0) {
            throw new ResponseStatusException(NOT_FOUND, "Ticker not in watchlist: " + ticker);
        }
    }

    public List<WatchlistGeneTarget> patchGeneTargets(String ticker, WatchlistPatchRequest req) {
        UUID id = findWatchlistId(ticker);
        if (req.remove() != null) {
            for (String gt : req.remove()) {
                jdbcTemplate.update(
                        "DELETE FROM watchlist_gene_target WHERE watchlist_id = ? AND gene_target = ?",
                        id, gt.trim().toUpperCase());
            }
        }
        if (req.add() != null) {
            for (String gt : req.add()) {
                String normalized = gt.trim().toUpperCase();
                jdbcTemplate.update(
                        "INSERT INTO watchlist_gene_target (watchlist_id, gene_target, source) VALUES (?, ?, 'manual') ON CONFLICT DO NOTHING",
                        id, normalized);
            }
        }
        return listGeneTargets(id);
    }

    public WatchlistSummary summary(String ticker) {
        String upper = ticker.toUpperCase();
        Map<String, Object> watchlistRow = jdbcTemplate.queryForMap(
                "SELECT id, company_name FROM watchlist WHERE ticker = ?", upper);
        UUID id = (UUID) watchlistRow.get("id");
        String companyName = (String) watchlistRow.get("company_name");

        List<WatchlistGeneTarget> trackedTargets = listGeneTargets(id);
        String[] tracked = trackedTargets.stream().map(WatchlistGeneTarget::geneTarget).toArray(String[]::new);

        List<WatchlistSummary.WatchlistGeneTargetStat> geneTargetStats = queryGeneTargetStats(upper, trackedTargets);
        List<WatchlistSummary.CorroborationRef> corroborations = queryFilteredCorroborations(tracked);

        long totalDirect = queryDirectSignalCount(upper);
        String mostActive = geneTargetStats.stream()
                .max(Comparator.comparingLong(WatchlistSummary.WatchlistGeneTargetStat::signalCount))
                .map(WatchlistSummary.WatchlistGeneTargetStat::name)
                .orElse(null);
        Instant lastSignalAt = queryLastSignalAt(upper);

        return new WatchlistSummary(
                upper, companyName,
                geneTargetStats,
                List.of(),
                corroborations,
                new WatchlistSummary.Stats(totalDirect, corroborations.size(), mostActive, lastSignalAt)
        );
    }

    private List<WatchlistGeneTarget> listGeneTargets(UUID watchlistId) {
        return jdbcTemplate.query(
                "SELECT gene_target, source FROM watchlist_gene_target WHERE watchlist_id = ? ORDER BY gene_target",
                (rs, n) -> new WatchlistGeneTarget(rs.getString("gene_target"), rs.getString("source")),
                watchlistId);
    }

    private UUID findWatchlistId(String ticker) {
        try {
            return jdbcTemplate.queryForObject(
                    "SELECT id FROM watchlist WHERE ticker = ?",
                    UUID.class, ticker.toUpperCase());
        } catch (org.springframework.dao.EmptyResultDataAccessException ex) {
            throw new ResponseStatusException(NOT_FOUND, "Ticker not in watchlist: " + ticker);
        }
    }

    private List<GeneTargetWithCount> queryGraphGeneTargets(String ticker) {
        try (Session session = neo4jDriver.session()) {
            return session.run("""
                            MATCH (s:Signal)-[:MENTIONS]->(c:Company {ticker: $ticker}),
                                  (s)-[:TARGETS]->(g:GeneTarget)
                            RETURN DISTINCT g.name AS name, count(s) AS signal_count
                            ORDER BY signal_count DESC
                            """,
                    Map.of("ticker", ticker))
                    .list(r -> new GeneTargetWithCount(
                            r.get("name").asString(),
                            r.get("signal_count").asLong()));
        }
    }

    private List<CtSuggestion> fetchCtSuggestions(String companyName) {
        try {
            String json = ctRestClient.get()
                    .uri(u -> u.path(CT_PATH)
                            .queryParam("query.spons", companyName)
                            .queryParam("fields",
                                    "protocolSection.conditionsModule.conditions," +
                                    "protocolSection.armsInterventionsModule.interventions.interventionMeshTerms")
                            .queryParam("pageSize", 50)
                            .build())
                    .retrieve()
                    .body(String.class);
            if (json == null) return List.of();
            return parseSuggestions(json);
        } catch (Exception ex) {
            log.warn("ClinicalTrials lookup failed for {}: {}", companyName, ex.getMessage());
            return List.of();
        }
    }

    private List<CtSuggestion> parseSuggestions(String json) {
        try {
            JsonNode root = objectMapper.readTree(json);
            LinkedHashSet<String> conditions = new LinkedHashSet<>();
            LinkedHashSet<String> interventions = new LinkedHashSet<>();
            for (JsonNode study : root.path("studies")) {
                JsonNode conds = study.path("protocolSection").path("conditionsModule").path("conditions");
                if (conds.isArray()) {
                    for (JsonNode c : conds) conditions.add(c.asText());
                }
                JsonNode arms = study.path("protocolSection").path("armsInterventionsModule").path("interventions");
                if (arms.isArray()) {
                    for (JsonNode arm : arms) {
                        JsonNode meshTerms = arm.path("interventionMeshTerms");
                        if (meshTerms.isArray()) {
                            for (JsonNode m : meshTerms) interventions.add(m.asText());
                        }
                    }
                }
            }
            List<CtSuggestion> result = new ArrayList<>();
            conditions.forEach(t -> result.add(new CtSuggestion(t, "condition")));
            interventions.forEach(t -> result.add(new CtSuggestion(t, "intervention")));
            return result;
        } catch (Exception ex) {
            log.warn("Failed to parse ClinicalTrials response: {}", ex.getMessage());
            return List.of();
        }
    }

    private List<WatchlistSummary.WatchlistGeneTargetStat> queryGeneTargetStats(
            String ticker, List<WatchlistGeneTarget> trackedTargets) {
        if (trackedTargets.isEmpty()) return List.of();
        List<WatchlistSummary.WatchlistGeneTargetStat> stats = new ArrayList<>();
        try (Session session = neo4jDriver.session()) {
            for (WatchlistGeneTarget gt : trackedTargets) {
                var result = session.run("""
                        MATCH (s:Signal)-[:MENTIONS]->(c:Company {ticker: $ticker}),
                              (s)-[:TARGETS]->(g:GeneTarget {name: $gene})
                        RETURN count(s) AS cnt,
                               max(s.published_date.epochSeconds) AS lastEpoch
                        """, Map.of("ticker", ticker, "gene", gt.geneTarget()));
                if (result.hasNext()) {
                    var row = result.next();
                    long cnt = row.get("cnt").asLong();
                    Instant lastSeen = row.get("lastEpoch").isNull()
                            ? null
                            : Instant.ofEpochSecond(row.get("lastEpoch").asLong());
                    stats.add(new WatchlistSummary.WatchlistGeneTargetStat(gt.geneTarget(), gt.source(), cnt, lastSeen));
                }
            }
        }
        return stats;
    }

    private List<WatchlistSummary.CorroborationRef> queryFilteredCorroborations(String[] trackedGeneTargets) {
        if (trackedGeneTargets.length == 0) return List.of();
        return jdbcTemplate.query(con -> {
            var ps = con.prepareStatement("""
                    SELECT entity_key, corroborated_at, distinct_source_count
                    FROM corroboration
                    WHERE superseded_by IS NULL
                      AND SPLIT_PART(entity_key, ' | ', 1) = ANY(?)
                    ORDER BY corroborated_at DESC
                    """);
            ps.setArray(1, con.createArrayOf("text", trackedGeneTargets));
            return ps;
        }, (rs, n) -> new WatchlistSummary.CorroborationRef(
                rs.getString("entity_key"),
                rs.getTimestamp("corroborated_at").toInstant(),
                rs.getInt("distinct_source_count") / 3.0));
    }

    private long queryDirectSignalCount(String ticker) {
        try (Session session = neo4jDriver.session()) {
            var result = session.run(
                    "MATCH (s:Signal)-[:MENTIONS]->(c:Company {ticker: $ticker}) RETURN count(s) AS cnt",
                    Map.of("ticker", ticker));
            return result.hasNext() ? result.next().get("cnt").asLong() : 0L;
        }
    }

    private Instant queryLastSignalAt(String ticker) {
        try (Session session = neo4jDriver.session()) {
            var result = session.run(
                    "MATCH (s:Signal)-[:MENTIONS]->(c:Company {ticker: $ticker}) RETURN max(s.published_date.epochSeconds) AS epoch",
                    Map.of("ticker", ticker));
            if (!result.hasNext()) return null;
            var row = result.next();
            return row.get("epoch").isNull() ? null : Instant.ofEpochSecond(row.get("epoch").asLong());
        }
    }
}
