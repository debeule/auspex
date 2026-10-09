package dev.auspex.corehub.config;

import org.neo4j.driver.Driver;
import org.neo4j.driver.Session;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

/**
 * Creates the uniqueness constraints that the MERGE-based graph writes rely on. Safe to run on
 * every startup; records a (:GraphSchema {version}) node so the applied schema is traceable.
 */
@Component
class Neo4jSchemaInitializer {

    private static final int SCHEMA_VERSION = 1;

    private final Driver driver;

    Neo4jSchemaInitializer(Driver driver) {
        this.driver = driver;
    }

    @EventListener(ApplicationReadyEvent.class)
    void initSchema() {
        try (Session session = driver.session()) {
            session.run("CREATE CONSTRAINT signal_event_id IF NOT EXISTS " +
                    "FOR (s:Signal) REQUIRE s.event_id IS UNIQUE");
            session.run("CREATE CONSTRAINT gene_target_name IF NOT EXISTS " +
                    "FOR (g:GeneTarget) REQUIRE g.name IS UNIQUE");
            session.run("CREATE CONSTRAINT mechanism_name IF NOT EXISTS " +
                    "FOR (m:Mechanism) REQUIRE m.name IS UNIQUE");
            session.run("CREATE CONSTRAINT company_name IF NOT EXISTS " +
                    "FOR (c:Company) REQUIRE c.name IS UNIQUE");
            session.run("CREATE INDEX signal_published_date IF NOT EXISTS " +
                    "FOR (s:Signal) ON (s.published_date)");
            session.run("CREATE INDEX signal_source_type IF NOT EXISTS " +
                    "FOR (s:Signal) ON (s.source_type)");
            session.run("CREATE INDEX company_ticker IF NOT EXISTS " +
                    "FOR (c:Company) ON (c.ticker)");
            session.run("""
                    MERGE (gs:GraphSchema {version: $version})
                    ON CREATE SET gs.created_at = datetime()
                    """, org.neo4j.driver.Values.parameters("version", SCHEMA_VERSION));
        }
    }
}
