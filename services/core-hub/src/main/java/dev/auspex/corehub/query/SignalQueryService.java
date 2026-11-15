package dev.auspex.corehub.query;

import dev.auspex.corehub.rest.dto.ContextCorroborationDto;
import dev.auspex.corehub.rest.dto.CorroboratedSignalDto;
import dev.auspex.corehub.rest.dto.DirectSignalDto;
import dev.auspex.corehub.rest.dto.TickerSignalsResponse;
import dev.auspex.corehub.corroboration.CorroborationScorer;
import org.neo4j.driver.Driver;
import org.neo4j.driver.Session;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.sql.Array;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.Instant;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

@Service
public class SignalQueryService {

    static final String NO_INDEPENDENT_PAIR_FOR_TICKER = "no_independent_pair_for_ticker";

    private final Driver neo4jDriver;
    private final JdbcTemplate jdbcTemplate;
    private final CorroborationScorer scorer;

    SignalQueryService(Driver neo4jDriver, JdbcTemplate jdbcTemplate, CorroborationScorer scorer) {
        this.neo4jDriver = neo4jDriver;
        this.jdbcTemplate = jdbcTemplate;
        this.scorer = scorer;
    }

    public TickerSignalsResponse query(String ticker) {
        List<DirectSignalDto> directSignals = directSignals(ticker);
        if (directSignals.isEmpty()) {
            return new TickerSignalsResponse(ticker, List.of(), List.of(), List.of());
        }
        String[] directIds = directSignals.stream().map(DirectSignalDto::eventId).toArray(String[]::new);
        List<CorroboratedSignalDto> tickerRecords = tickerRecords(ticker);
        Set<String> entitiesWithTickerRecord = tickerRecords.stream()
                .map(CorroboratedSignalDto::entityKey).collect(Collectors.toSet());
        List<ContextCorroborationDto> context = contextRecords(directIds).stream()
                .filter(c -> !entitiesWithTickerRecord.contains(c.entityKey()))
                .toList();
        return new TickerSignalsResponse(ticker, directSignals, tickerRecords, context);
    }

    /** Signals that mention the company, newest first. */
    public List<DirectSignalDto> directSignals(String ticker) {
        try (Session session = neo4jDriver.session()) {
            return session.run("""
                            MATCH (s:Signal)-[:MENTIONS]->(c:Company {ticker: $ticker})
                            RETURN s.event_id                      AS eventId,
                                   s.source_type                   AS sourceType,
                                   s.title                         AS title,
                                   s.summary                       AS summary,
                                   s.confidence_score              AS confidenceScore,
                                   s.published_date.epochSeconds   AS publishedAtEpoch
                            ORDER BY publishedAtEpoch DESC, eventId
                            """,
                            Map.of("ticker", ticker))
                    .list(r -> new DirectSignalDto(
                            r.get("eventId").asString(),
                            r.get("sourceType").asString(),
                            r.get("title").asString(),
                            r.get("summary").asString(),
                            r.get("confidenceScore").asDouble(0.0),
                            Instant.ofEpochSecond(r.get("publishedAtEpoch").asLong())
                    ));
        }
    }

    private record Row(String entityKey, String excludedReason, List<String> participants,
                       int distinctSourceCount, Instant episodeOpenedAt, Instant corroboratedAt) {}

    private static Row row(ResultSet rs) throws SQLException {
        Object[] raw = (Object[]) rs.getArray("participant_event_ids").getArray();
        return new Row(
                rs.getString("entity_key"),
                rs.getString("excluded_reason"),
                Arrays.stream(raw).map(Object::toString).toList(),
                rs.getInt("distinct_source_count"),
                rs.getTimestamp("episode_opened_at").toInstant(),
                rs.getTimestamp("corroborated_at").toInstant());
    }

    /** Live ticker records of the ticker, each with its score. */
    private List<CorroboratedSignalDto> tickerRecords(String ticker) {
        List<Row> rows = jdbcTemplate.query("""
                SELECT entity_key, excluded_reason, participant_event_ids, distinct_source_count,
                       episode_opened_at, corroborated_at
                FROM corroboration
                WHERE superseded_by IS NULL AND excluded_reason IS NULL AND ticker = ?
                ORDER BY episode_opened_at DESC, entity_key
                """, (rs, n) -> row(rs), ticker);
        return rows.stream().map(r -> new CorroboratedSignalDto(
                r.entityKey(),
                ticker,
                querySourceTypes(r.participants()),
                r.episodeOpenedAt(),
                r.corroboratedAt(),
                scorer.score(r.distinctSourceCount(), r.corroboratedAt()),
                r.participants())).toList();
    }

    /** Live entity records listing any of the direct signals, with the reason they are context only. */
    private List<ContextCorroborationDto> contextRecords(String[] directIds) {
        List<Row> rows = jdbcTemplate.query(con -> {
            PreparedStatement ps = con.prepareStatement("""
                    SELECT entity_key, excluded_reason, participant_event_ids, distinct_source_count,
                           episode_opened_at, corroborated_at
                    FROM corroboration
                    WHERE superseded_by IS NULL AND ticker = '' AND participant_event_ids && ?
                    ORDER BY episode_opened_at DESC, entity_key
                    """);
            Array arr = con.createArrayOf("uuid", directIds);
            ps.setArray(1, arr);
            return ps;
        }, (rs, n) -> row(rs));
        return rows.stream().map(r -> new ContextCorroborationDto(
                r.entityKey(),
                r.excludedReason() != null ? r.excludedReason() : NO_INDEPENDENT_PAIR_FOR_TICKER,
                querySourceTypes(r.participants()),
                r.episodeOpenedAt(),
                r.corroboratedAt(),
                r.participants())).toList();
    }

    private List<String> querySourceTypes(List<String> eventIds) {
        try (Session session = neo4jDriver.session()) {
            var result = session.run("""
                            MATCH (s:Signal) WHERE s.event_id IN $eventIds
                            RETURN collect(distinct s.source_type) AS sourceTypes
                            """,
                    Map.of("eventIds", eventIds));
            if (!result.hasNext()) return List.of();
            return result.next().get("sourceTypes").asList(v -> v.asString()).stream().sorted().toList();
        }
    }
}
