package dev.auspex.corehub;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import dev.auspex.corehub.signal.ResearchSignalEvent;
import org.neo4j.driver.Driver;
import org.neo4j.driver.Session;
import org.springframework.jdbc.core.JdbcTemplate;

import java.time.Instant;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/** Builds signal events for the corroboration tests and reads back what the scan wrote. */
final class CorroborationSignals {

    /** A live row of {@code corroboration}. */
    record Row(String entityKey, String ticker, List<UUID> participants, int distinctSourceCount,
               Instant episodeOpenedAt, Instant corroboratedAt, String excludedReason, Instant publishedAt) {}

    private final ObjectMapper objectMapper;
    private final JdbcTemplate jdbc;
    private final Driver driver;

    CorroborationSignals(ObjectMapper objectMapper, JdbcTemplate jdbc, Driver driver) {
        this.objectMapper = objectMapper;
        this.jdbc = jdbc;
        this.driver = driver;
    }

    /** One signal event; {@code title} null for none. */
    ResearchSignalEvent event(UUID eventId, String sourceType, String publishedDate, String title,
                              List<String> geneTargets, List<String> mechanisms, List<String> companies) {
        try {
            ObjectNode node = (ObjectNode) objectMapper.readTree(TestFixtures.validSignalJson());
            node.put("event_id", eventId.toString());
            node.put("extraction_id", UUID.randomUUID().toString());
            node.put("external_id", "ext-" + eventId);
            node.put("source_type", sourceType);
            node.put("raw_object_key", "raw/" + sourceType + "/ext-" + eventId + "/20240615T120000Z-abcdef12.json");
            node.put("published_date", publishedDate + "T00:00:00Z");
            node.put("ingested_at", "2024-06-15T12:00:00Z");
            if (title == null) {
                node.putNull("title");
            } else {
                node.put("title", title);
            }
            node.set("gene_targets", array(geneTargets));
            node.set("mechanisms", array(mechanisms));
            node.set("companies_mentioned", array(companies));
            node.putNull("primary_company");
            return objectMapper.treeToValue(node, ResearchSignalEvent.class);
        } catch (Exception ex) {
            throw new IllegalStateException(ex);
        }
    }

    void setTicker(String company, String ticker) {
        try (Session session = driver.session()) {
            session.run("MATCH (c:Company {name: $name}) SET c.ticker = $ticker",
                    Map.of("name", company, "ticker", ticker)).consume();
        }
    }

    boolean isPending(UUID eventId) {
        try (Session session = driver.session()) {
            return session.run("MATCH (s:Signal {event_id: $id}) RETURN s.corroboration_pending AS p",
                    Map.of("id", eventId.toString())).single().get("p").asBoolean();
        }
    }

    List<Row> live() {
        return rows("superseded_by IS NULL");
    }

    List<Row> all() {
        return rows("TRUE");
    }

    private List<Row> rows(String filter) {
        String sql = "TRUE".equals(filter)
                ? "SELECT * FROM corroboration ORDER BY entity_key, ticker, episode_opened_at"
                : "SELECT * FROM corroboration WHERE superseded_by IS NULL ORDER BY entity_key, ticker, episode_opened_at";
        return jdbc.query(sql, (rs, n) -> {
            Object[] ids = (Object[]) rs.getArray("participant_event_ids").getArray();
            var published = rs.getTimestamp("published_at");
            return new Row(rs.getString("entity_key"), rs.getString("ticker"),
                    Arrays.stream(ids).map(o -> UUID.fromString(o.toString())).sorted().toList(),
                    rs.getInt("distinct_source_count"),
                    rs.getTimestamp("episode_opened_at").toInstant(),
                    rs.getTimestamp("corroborated_at").toInstant(),
                    rs.getString("excluded_reason"),
                    published == null ? null : published.toInstant());
        });
    }

    private ArrayNode array(List<String> values) {
        ArrayNode array = objectMapper.createArrayNode();
        values.forEach(array::add);
        return array;
    }
}
