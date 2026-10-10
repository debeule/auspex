package dev.auspex.corehub.health;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.HashMap;
import java.util.Map;

@Component
public class PostgresSignalAgeReader implements SignalAgeReader {

    private static final String LATEST_BY_SOURCE =
            "SELECT source_type, max(ingested_at) AS latest FROM signal_current GROUP BY source_type";

    private final JdbcTemplate jdbcTemplate;

    public PostgresSignalAgeReader(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    @Override
    public Map<String, Instant> latestIngestedAtBySource() {
        Map<String, Instant> latest = new HashMap<>();
        jdbcTemplate.query(LATEST_BY_SOURCE, row -> {
            latest.put(row.getString("source_type"), row.getObject("latest", Timestamp.class).toInstant());
        });
        return latest;
    }
}
