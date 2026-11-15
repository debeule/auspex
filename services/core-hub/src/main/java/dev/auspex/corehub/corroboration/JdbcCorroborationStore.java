package dev.auspex.corehub.corroboration;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.Arrays;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;

/** Postgres side of the corroboration scan and the rules sync; every value is bound. */
@Component
class JdbcCorroborationStore implements CorroborationStore {

    private final JdbcTemplate jdbc;

    JdbcCorroborationStore(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @Override
    public String appliedRulesHash() {
        List<String> hashes = jdbc.query("SELECT rules_hash FROM corroboration_rules_state",
                (rs, n) -> rs.getString("rules_hash"));
        return hashes.isEmpty() ? null : hashes.getFirst();
    }

    @Override
    public void storeAppliedRulesHash(String hash, Instant appliedAt) {
        jdbc.update("""
                INSERT INTO corroboration_rules_state (singleton, rules_hash, applied_at)
                VALUES (TRUE, ?, ?)
                ON CONFLICT (singleton) DO UPDATE SET rules_hash = EXCLUDED.rules_hash,
                                                      applied_at = EXCLUDED.applied_at
                """, hash, Timestamp.from(appliedAt));
    }

    @Override
    public Set<String> liveEntityKeysListing(List<String> eventIds) {
        return new LinkedHashSet<>(jdbc.query(con -> {
            PreparedStatement ps = con.prepareStatement("""
                    SELECT DISTINCT entity_key FROM corroboration
                    WHERE superseded_by IS NULL AND participant_event_ids && ?
                    """);
            ps.setArray(1, con.createArrayOf("uuid", eventIds.toArray(String[]::new)));
            return ps;
        }, (rs, n) -> rs.getString("entity_key")));
    }

    @Override
    public List<CorroborationRow> rows(String entityKey) {
        return jdbc.query("""
                SELECT entity_key, ticker, participants_hash, participant_event_ids, distinct_source_count,
                       corroborated_at, episode_opened_at, first_detected_at, excluded_reason, published_at,
                       superseded_by
                FROM corroboration WHERE entity_key = ?
                """, (rs, n) -> row(rs), entityKey);
    }

    @Override
    public void insert(CorroborationRow row) {
        jdbc.update(con -> {
            PreparedStatement ps = con.prepareStatement("""
                    INSERT INTO corroboration
                        (entity_key, ticker, participants_hash, participant_event_ids, distinct_source_count,
                         corroborated_at, episode_opened_at, first_detected_at, excluded_reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (entity_key, ticker, participants_hash) DO NOTHING
                    """);
            ps.setString(1, row.entityKey());
            ps.setString(2, row.ticker());
            ps.setString(3, row.participantsHash());
            ps.setArray(4, con.createArrayOf("uuid",
                    row.participantEventIds().stream().map(UUID::toString).toArray(String[]::new)));
            ps.setInt(5, row.distinctSourceCount());
            ps.setTimestamp(6, Timestamp.from(row.corroboratedAt()));
            ps.setTimestamp(7, Timestamp.from(row.episodeOpenedAt()));
            ps.setTimestamp(8, Timestamp.from(row.firstDetectedAt()));
            ps.setString(9, row.excludedReason());
            return ps;
        });
    }

    @Override
    public void revive(String entityKey, String ticker, String participantsHash) {
        jdbc.update("""
                UPDATE corroboration SET superseded_by = NULL
                WHERE entity_key = ? AND ticker = ? AND participants_hash = ?
                """, entityKey, ticker, participantsHash);
    }

    @Override
    public void supersede(String entityKey, String ticker, String participantsHash, String supersededBy) {
        jdbc.update("""
                UPDATE corroboration SET superseded_by = ?
                WHERE entity_key = ? AND ticker = ? AND participants_hash = ?
                """, supersededBy, entityKey, ticker, participantsHash);
    }

    @Override
    public void setExcludedReason(String entityKey, String ticker, String participantsHash, String excludedReason) {
        jdbc.update("""
                UPDATE corroboration SET excluded_reason = ?
                WHERE entity_key = ? AND ticker = ? AND participants_hash = ?
                """, excludedReason, entityKey, ticker, participantsHash);
    }

    @Override
    public void markPublished(String entityKey, String ticker, String participantsHash, Instant publishedAt) {
        jdbc.update("""
                UPDATE corroboration SET published_at = ?
                WHERE entity_key = ? AND ticker = ? AND participants_hash = ?
                """, Timestamp.from(publishedAt), entityKey, ticker, participantsHash);
    }

    private static CorroborationRow row(ResultSet rs) throws SQLException {
        Object[] ids = (Object[]) rs.getArray("participant_event_ids").getArray();
        Timestamp published = rs.getTimestamp("published_at");
        return new CorroborationRow(
                rs.getString("entity_key"),
                rs.getString("ticker"),
                rs.getString("participants_hash"),
                Arrays.stream(ids).map(o -> UUID.fromString(o.toString())).toList(),
                rs.getInt("distinct_source_count"),
                rs.getTimestamp("corroborated_at").toInstant(),
                rs.getTimestamp("episode_opened_at").toInstant(),
                rs.getTimestamp("first_detected_at").toInstant(),
                rs.getString("excluded_reason"),
                published == null ? null : published.toInstant(),
                rs.getString("superseded_by"));
    }
}
