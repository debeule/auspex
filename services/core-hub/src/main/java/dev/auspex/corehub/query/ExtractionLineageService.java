package dev.auspex.corehub.query;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.sql.Timestamp;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.List;

/**
 * Counts signals per extraction model within a published-date window, so callers
 * outside core-hub can check extraction lineage without reading Postgres.
 */
@Service
public class ExtractionLineageService {

    public record ExtractionModelCount(String extractionModel, long documents) {}

    private final JdbcTemplate jdbcTemplate;

    ExtractionLineageService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    /** {@code from} and {@code to} are inclusive UTC dates. */
    public List<ExtractionModelCount> modelsInWindow(String sourceType, LocalDate from, LocalDate to) {
        Timestamp start = Timestamp.from(from.atStartOfDay(ZoneOffset.UTC).toInstant());
        Timestamp endExclusive = Timestamp.from(to.plusDays(1).atStartOfDay(ZoneOffset.UTC).toInstant());
        return jdbcTemplate.query("""
                        SELECT h.extraction_model, COUNT(DISTINCT h.event_id) AS documents
                        FROM signal_extraction_history h
                        JOIN signal_current c ON c.event_id = h.event_id
                        WHERE c.source_type = ?
                          AND c.published_date >= ?
                          AND c.published_date < ?
                        GROUP BY h.extraction_model
                        ORDER BY h.extraction_model
                        """,
                (rs, n) -> new ExtractionModelCount(rs.getString("extraction_model"), rs.getLong("documents")),
                sourceType, start, endExclusive);
    }
}
