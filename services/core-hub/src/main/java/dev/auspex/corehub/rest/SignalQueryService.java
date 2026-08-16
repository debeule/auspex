package dev.auspex.corehub.rest;

import dev.auspex.corehub.rest.dto.CorroboratedSignalDto;
import dev.auspex.corehub.rest.dto.DirectSignalDto;
import dev.auspex.corehub.rest.dto.TickerSignalsResponse;
import org.neo4j.driver.Driver;
import org.neo4j.driver.Session;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.sql.Array;
import java.sql.PreparedStatement;
import java.time.Instant;
import java.util.Arrays;
import java.util.List;
import java.util.Map;

@Service
class SignalQueryService {

    private final Driver neo4jDriver;
    private final JdbcTemplate jdbcTemplate;

    SignalQueryService(Driver neo4jDriver, JdbcTemplate jdbcTemplate) {
        this.neo4jDriver = neo4jDriver;
        this.jdbcTemplate = jdbcTemplate;
    }

    TickerSignalsResponse query(String ticker) {
        List<DirectSignalDto> directSignals = queryDirectSignals(ticker);
        if (directSignals.isEmpty()) {
            return new TickerSignalsResponse(ticker, List.of(), List.of());
        }
        String[] directIds = directSignals.stream().map(DirectSignalDto::eventId).toArray(String[]::new);
        List<CorroboratedSignalDto> corroboratedSignals = queryCorroborations(directIds);
        return new TickerSignalsResponse(ticker, directSignals, corroboratedSignals);
    }

    private List<DirectSignalDto> queryDirectSignals(String ticker) {
        try (Session session = neo4jDriver.session()) {
            return session.run("""
                            MATCH (s:Signal)-[:MENTIONS]->(c:Company {ticker: $ticker})
                            RETURN s.event_id                      AS eventId,
                                   s.source_type                   AS sourceType,
                                   s.title                         AS title,
                                   s.summary                       AS summary,
                                   s.confidence_score              AS confidenceScore,
                                   s.published_date.epochSeconds   AS publishedAtEpoch
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

    private List<CorroboratedSignalDto> queryCorroborations(String[] directIds) {
        record CorrRow(String entityKey, String[] participantIds, int distinctSourceCount, Instant corroboratedAt) {}

        List<CorrRow> rows = jdbcTemplate.query(con -> {
            PreparedStatement ps = con.prepareStatement("""
                    SELECT entity_key, participant_event_ids, distinct_source_count, corroborated_at
                    FROM corroboration
                    WHERE superseded_by IS NULL
                      AND participant_event_ids && ?
                    """);
            Array arr = con.createArrayOf("uuid", directIds);
            ps.setArray(1, arr);
            return ps;
        }, (rs, n) -> {
            Object[] raw = (Object[]) rs.getArray("participant_event_ids").getArray();
            String[] ids = Arrays.stream(raw).map(Object::toString).toArray(String[]::new);
            return new CorrRow(
                    rs.getString("entity_key"),
                    ids,
                    rs.getInt("distinct_source_count"),
                    rs.getTimestamp("corroborated_at").toInstant()
            );
        });

        if (rows.isEmpty()) return List.of();

        return rows.stream().map(row -> {
            List<String> participants = Arrays.asList(row.participantIds());
            List<String> sourceTypes = querySourceTypes(participants);
            double confidence = Math.min(1.0, row.distinctSourceCount() * 0.25);
            return new CorroboratedSignalDto(
                    row.entityKey(),
                    sourceTypes,
                    row.corroboratedAt(),
                    confidence,
                    participants
            );
        }).toList();
    }

    private List<String> querySourceTypes(List<String> eventIds) {
        try (Session session = neo4jDriver.session()) {
            var result = session.run("""
                            MATCH (s:Signal) WHERE s.event_id IN $eventIds
                            RETURN collect(distinct s.source_type) AS sourceTypes
                            """,
                    Map.of("eventIds", eventIds));
            if (!result.hasNext()) return List.of();
            return result.next().get("sourceTypes").asList(v -> v.asString());
        }
    }
}
