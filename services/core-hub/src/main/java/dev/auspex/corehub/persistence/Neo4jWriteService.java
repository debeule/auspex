package dev.auspex.corehub.persistence;

import dev.auspex.corehub.signal.ResearchSignalEvent;
import dev.auspex.corehub.signal.SignalGraphPort;
import org.neo4j.driver.Driver;
import org.neo4j.driver.Session;
import org.neo4j.driver.TransactionContext;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.Map;

/**
 * Writes Signal nodes and their entity relationships to Neo4j.
 * Uses MERGE on natural keys throughout — never CREATE — to stay idempotent.
 * confidence_score stored as double (Neo4j has no decimal type).
 */
@Service
public class Neo4jWriteService implements SignalGraphPort {

    private final Driver driver;
    private final CompanyTickerService companyTickers;

    public Neo4jWriteService(Driver driver, CompanyTickerService companyTickers) {
        this.driver = driver;
        this.companyTickers = companyTickers;
    }

    public void upsert(ResearchSignalEvent event) {
        try (Session session = driver.session()) {
            session.executeWrite(tx -> {
                mergeSignal(tx, event);
                String eventId = event.eventId().toString();
                for (String gene : event.geneTargets()) {
                    mergeGeneRelationship(tx, eventId, gene);
                }
                for (String mechanism : event.mechanisms()) {
                    mergeMechanismRelationship(tx, eventId, mechanism);
                }
                for (String company : event.companiesMentioned()) {
                    mergeCompanyRelationship(tx, eventId, company);
                }
                return null;
            });
        }
    }

    private void mergeSignal(TransactionContext tx, ResearchSignalEvent e) {
        Map<String, Object> params = new HashMap<>();
        params.put("event_id",             e.eventId().toString());
        params.put("extraction_id",        e.extractionId().toString());
        params.put("schema_version",       e.schemaVersion());
        params.put("source_type",          e.sourceType());
        params.put("source_url",           e.sourceUrl());
        params.put("external_id",          e.externalId());
        params.put("canonical_id",         e.canonicalId());
        params.put("raw_object_key",       e.rawObjectKey());
        params.put("published_date",       e.publishedDate().toString());
        params.put("published_date_field", e.publishedDateField());
        params.put("ingested_at",          e.ingestedAt().toString());
        params.put("title",                e.title());
        params.put("raw_text_snippet",     e.rawTextSnippet());
        params.put("summary",              e.summary());
        params.put("directionality",       e.directionality());
        params.put("confidence_score",     e.confidenceScore().doubleValue());
        params.put("prompt_version",       e.promptVersion());
        params.put("prefilter_version",    e.prefilterVersion());
        params.put("extraction_model",     e.extractionModel());

        tx.run("""
                MERGE (s:Signal {event_id: $event_id})
                SET s.extraction_id        = $extraction_id,
                    s.schema_version       = $schema_version,
                    s.source_type          = $source_type,
                    s.source_url           = $source_url,
                    s.external_id          = $external_id,
                    s.canonical_id         = $canonical_id,
                    s.raw_object_key       = $raw_object_key,
                    s.published_date       = datetime($published_date),
                    s.published_date_field = $published_date_field,
                    s.ingested_at          = datetime($ingested_at),
                    s.title                = $title,
                    s.raw_text_snippet     = $raw_text_snippet,
                    s.summary              = $summary,
                    s.directionality       = $directionality,
                    s.confidence_score     = $confidence_score,
                    s.prompt_version       = $prompt_version,
                    s.prefilter_version    = $prefilter_version,
                    s.extraction_model     = $extraction_model
                """, params);
    }

    private void mergeGeneRelationship(TransactionContext tx, String eventId, String geneName) {
        tx.run("""
                MATCH (s:Signal {event_id: $event_id})
                MERGE (g:GeneTarget {name: $name})
                MERGE (s)-[:TARGETS]->(g)
                """,
                Map.of("event_id", eventId, "name", geneName));
    }

    private void mergeMechanismRelationship(TransactionContext tx, String eventId, String mechanismName) {
        tx.run("""
                MATCH (s:Signal {event_id: $event_id})
                MERGE (m:Mechanism {name: $name})
                MERGE (s)-[:USES_MECHANISM]->(m)
                """,
                Map.of("event_id", eventId, "name", mechanismName));
    }

    /** `ticker` is set only when resolved; an unresolved merge keeps any ticker already on the node. */
    private void mergeCompanyRelationship(TransactionContext tx, String eventId, String companyName) {
        Map<String, Object> params = new HashMap<>();
        params.put("event_id", eventId);
        params.put("name", companyName);
        params.put("ticker", companyTickers.uniqueTicker(companyName).orElse(null));
        tx.run("""
                MATCH (s:Signal {event_id: $event_id})
                MERGE (c:Company {name: $name})
                SET c.ticker = coalesce($ticker, c.ticker)
                MERGE (s)-[:MENTIONS]->(c)
                """, params);
    }
}
