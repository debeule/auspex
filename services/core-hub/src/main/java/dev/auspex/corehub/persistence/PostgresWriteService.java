package dev.auspex.corehub.persistence;

import dev.auspex.corehub.signal.ResearchSignalEvent;
import dev.auspex.corehub.signal.SignalRecordPort;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.List;

/**
 * Writes to signal_current, signal_extraction_history, and source_observation atomically.
 * All three writes share one JPA transaction; the offset is not committed until both
 * Neo4j and Postgres return successfully.
 */
@Service
public class PostgresWriteService implements SignalRecordPort {

    private static final String UPSERT_SIGNAL_CURRENT = """
            INSERT INTO signal_current (
                event_id, extraction_id, schema_version, source_type, source_url,
                external_id, canonical_id, raw_object_key, published_date, published_date_field,
                ingested_at, title, raw_text_snippet, gene_targets, mechanisms,
                companies_mentioned, summary, directionality, confidence_score,
                prompt_version, prefilter_version, extraction_model, event_type,
                primary_company, program_identifiers, trial_ids, last_updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now())
            ON CONFLICT (event_id) DO UPDATE SET
                extraction_id        = EXCLUDED.extraction_id,
                schema_version       = EXCLUDED.schema_version,
                source_url           = EXCLUDED.source_url,
                raw_object_key       = EXCLUDED.raw_object_key,
                published_date       = EXCLUDED.published_date,
                published_date_field = EXCLUDED.published_date_field,
                ingested_at          = EXCLUDED.ingested_at,
                title                = EXCLUDED.title,
                raw_text_snippet     = EXCLUDED.raw_text_snippet,
                gene_targets         = EXCLUDED.gene_targets,
                mechanisms           = EXCLUDED.mechanisms,
                companies_mentioned  = EXCLUDED.companies_mentioned,
                summary              = EXCLUDED.summary,
                directionality       = EXCLUDED.directionality,
                confidence_score     = EXCLUDED.confidence_score,
                prompt_version       = EXCLUDED.prompt_version,
                prefilter_version    = EXCLUDED.prefilter_version,
                extraction_model     = EXCLUDED.extraction_model,
                event_type           = EXCLUDED.event_type,
                primary_company      = EXCLUDED.primary_company,
                program_identifiers  = EXCLUDED.program_identifiers,
                trial_ids            = EXCLUDED.trial_ids,
                last_updated_at      = now()
            """;

    private static final String INSERT_EXTRACTION_HISTORY = """
            INSERT INTO signal_extraction_history
                (event_id, extraction_id, schema_version, confidence_score,
                 prompt_version, prefilter_version, extraction_model)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (event_id, extraction_id) DO NOTHING
            """;

    private static final String INSERT_SOURCE_OBSERVATION = """
            INSERT INTO source_observation (event_id, source_type, external_id, raw_object_key)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (event_id, source_type, external_id) DO NOTHING
            """;

    private final JdbcTemplate jdbcTemplate;

    public PostgresWriteService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    @Transactional(transactionManager = "jpaTransactionManager")
    public void upsert(ResearchSignalEvent e) {
        upsertSignalCurrent(e);
        insertExtractionHistory(e);
        insertSourceObservation(e);
    }

    private void upsertSignalCurrent(ResearchSignalEvent e) {
        jdbcTemplate.update(conn -> {
            var ps = conn.prepareStatement(UPSERT_SIGNAL_CURRENT);
            ps.setObject(1,  e.eventId());
            ps.setObject(2,  e.extractionId());
            ps.setString(3,  e.schemaVersion());
            ps.setString(4,  e.sourceType());
            ps.setString(5,  e.sourceUrl());
            ps.setString(6,  e.externalId());
            ps.setString(7,  e.canonicalId());
            ps.setObject(8,  e.rawObjectKey());
            ps.setObject(9,  OffsetDateTime.ofInstant(e.publishedDate(), ZoneOffset.UTC));
            ps.setString(10, e.publishedDateField());
            ps.setObject(11, OffsetDateTime.ofInstant(e.ingestedAt(), ZoneOffset.UTC));
            ps.setString(12, e.title());
            ps.setString(13, e.rawTextSnippet());
            ps.setArray(14,  conn.createArrayOf("text", e.geneTargets().toArray()));
            ps.setArray(15,  conn.createArrayOf("text", e.mechanisms().toArray()));
            ps.setArray(16,  conn.createArrayOf("text", e.companiesMentioned().toArray()));
            ps.setString(17, e.summary());
            ps.setString(18, e.directionality());
            ps.setBigDecimal(19, e.confidenceScore());
            ps.setString(20, e.promptVersion());
            ps.setString(21, e.prefilterVersion());
            ps.setString(22, e.extractionModel());
            ps.setString(23, e.eventType());
            ps.setString(24, e.primaryCompany());
            ps.setArray(25,  conn.createArrayOf("text", orEmpty(e.programIdentifiers()).toArray()));
            ps.setArray(26,  conn.createArrayOf("text", orEmpty(e.trialIds()).toArray()));
            return ps;
        });
    }

    private static List<String> orEmpty(List<String> values) {
        return values == null ? List.of() : values;
    }

    private void insertExtractionHistory(ResearchSignalEvent e) {
        jdbcTemplate.update(INSERT_EXTRACTION_HISTORY,
                e.eventId(),
                e.extractionId(),
                e.schemaVersion(),
                e.confidenceScore(),
                e.promptVersion(),
                e.prefilterVersion(),
                e.extractionModel());
    }

    private void insertSourceObservation(ResearchSignalEvent e) {
        jdbcTemplate.update(INSERT_SOURCE_OBSERVATION,
                e.eventId(),
                e.sourceType(),
                e.externalId(),
                e.rawObjectKey());
    }
}
