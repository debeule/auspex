package dev.auspex.corehub.corroboration;

import org.neo4j.driver.Driver;
import org.neo4j.driver.Session;
import org.springframework.stereotype.Component;

import java.time.Instant;
import java.util.ArrayList;
import java.util.Collection;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * Neo4j side of the corroboration scan. A node label cannot be a query parameter, so each
 * label-specific statement is one of two constant texts; every value is bound.
 */
@Component
class Neo4jCorroborationGraph implements CorroborationGraph {

    private static final Map<String, String> SET_KEYS = Map.of(
            EntityRules.GENE_TARGET, """
                    UNWIND $rows AS row
                    MATCH (e:GeneTarget {name: row.name})
                    SET e.corroboration_key = row.key
                    """,
            EntityRules.MECHANISM, """
                    UNWIND $rows AS row
                    MATCH (e:Mechanism {name: row.name})
                    SET e.corroboration_key = row.key
                    """);

    private static final Map<String, String> ELIGIBLE_SIGNALS = Map.of(
            EntityRules.GENE_TARGET, """
                    UNWIND $keys AS key
                    MATCH (e:GeneTarget {corroboration_key: key})<-[:TARGETS]-(s:Signal)
                    WHERE s.published_date <= datetime($now)
                    WITH DISTINCT key, s
                    OPTIONAL MATCH (s)-[:MENTIONS]->(c:Company)
                    WHERE c.ticker IS NOT NULL AND c.ticker <> ''
                    RETURN key, s.event_id AS eventId, s.source_type AS sourceType,
                           s.published_date.epochMillis AS publishedMillis, s.title AS title,
                           collect(DISTINCT c.ticker) AS tickers
                    """,
            EntityRules.MECHANISM, """
                    UNWIND $keys AS key
                    MATCH (e:Mechanism {corroboration_key: key})<-[:USES_MECHANISM]-(s:Signal)
                    WHERE s.published_date <= datetime($now)
                    WITH DISTINCT key, s
                    OPTIONAL MATCH (s)-[:MENTIONS]->(c:Company)
                    WHERE c.ticker IS NOT NULL AND c.ticker <> ''
                    RETURN key, s.event_id AS eventId, s.source_type AS sourceType,
                           s.published_date.epochMillis AS publishedMillis, s.title AS title,
                           collect(DISTINCT c.ticker) AS tickers
                    """);

    private final Driver driver;

    Neo4jCorroborationGraph(Driver driver) {
        this.driver = driver;
    }

    @Override
    public List<CorroborationScanner.PendingSignal> readPending(Instant now, int limit) {
        try (Session session = driver.session()) {
            return session.run("""
                    MATCH (s:Signal)
                    WHERE s.corroboration_pending = true
                      AND s.published_date <= datetime($now)
                    RETURN s.event_id AS eventId, s.write_token AS writeToken
                    LIMIT $batchSize
                    """,
                    Map.of("now", now.toString(), "batchSize", limit))
                    .list(r -> new CorroborationScanner.PendingSignal(
                            UUID.fromString(r.get("eventId").asString()), r.get("writeToken").asString()));
        }
    }

    @Override
    public List<EntityNode> unkeyedEntitiesOf(List<String> eventIds) {
        try (Session session = driver.session()) {
            return session.run("""
                    UNWIND $ids AS id
                    MATCH (:Signal {event_id: id})-[:TARGETS|USES_MECHANISM]->(e)
                    WHERE e.corroboration_key IS NULL AND (e:GeneTarget OR e:Mechanism)
                    RETURN DISTINCT CASE WHEN e:GeneTarget THEN 'GeneTarget' ELSE 'Mechanism' END AS label, e.name AS name
                    """,
                    Map.of("ids", eventIds))
                    .list(r -> new EntityNode(r.get("label").asString(), r.get("name").asString()));
        }
    }

    @Override
    public List<EntityNode> allEntities() {
        try (Session session = driver.session()) {
            return session.run("""
                    MATCH (e)
                    WHERE e:GeneTarget OR e:Mechanism
                    RETURN CASE WHEN e:GeneTarget THEN 'GeneTarget' ELSE 'Mechanism' END AS label, e.name AS name
                    """)
                    .list(r -> new EntityNode(r.get("label").asString(), r.get("name").asString()));
        }
    }

    @Override
    public void setKeys(List<KeyedEntity> keyed) {
        Map<String, List<Map<String, Object>>> byLabel = new LinkedHashMap<>();
        for (KeyedEntity k : keyed) {
            byLabel.computeIfAbsent(k.label(), l -> new ArrayList<>()).add(Map.of("name", k.name(), "key", k.key()));
        }
        try (Session session = driver.session()) {
            for (Map.Entry<String, List<Map<String, Object>>> e : byLabel.entrySet()) {
                session.executeWrite(tx -> tx.run(statement(SET_KEYS, e.getKey()), Map.of("rows", e.getValue())).consume());
            }
        }
    }

    @Override
    public Set<EntityRef> entitiesOf(List<String> eventIds) {
        try (Session session = driver.session()) {
            return new HashSet<>(session.run("""
                    UNWIND $ids AS id
                    MATCH (:Signal {event_id: id})-[:TARGETS|USES_MECHANISM]->(e)
                    WHERE e.corroboration_key IS NOT NULL AND (e:GeneTarget OR e:Mechanism)
                    RETURN DISTINCT CASE WHEN e:GeneTarget THEN 'GeneTarget' ELSE 'Mechanism' END AS label, e.corroboration_key AS key
                    """,
                    Map.of("ids", eventIds))
                    .list(r -> new EntityRef(r.get("label").asString(), r.get("key").asString())));
        }
    }

    @Override
    public Map<EntityRef, List<CorroborationSignal>> eligibleSignals(Collection<EntityRef> entities, Instant now) {
        Map<String, List<String>> keysByLabel = new LinkedHashMap<>();
        entities.forEach(e -> keysByLabel.computeIfAbsent(e.label(), l -> new ArrayList<>()).add(e.key()));
        Map<EntityRef, List<CorroborationSignal>> out = new LinkedHashMap<>();
        try (Session session = driver.session()) {
            for (Map.Entry<String, List<String>> e : keysByLabel.entrySet()) {
                String label = e.getKey();
                session.run(statement(ELIGIBLE_SIGNALS, label), Map.of("keys", e.getValue(), "now", now.toString()))
                        .forEachRemaining(r -> out.computeIfAbsent(new EntityRef(label, r.get("key").asString()),
                                k -> new ArrayList<>()).add(new CorroborationSignal(
                                r.get("eventId").asString(),
                                r.get("sourceType").asString(),
                                Instant.ofEpochMilli(r.get("publishedMillis").asLong()),
                                r.get("title").isNull() ? null : r.get("title").asString(),
                                Set.copyOf(r.get("tickers").asList(v -> v.asString())))));
            }
        }
        return out;
    }

    @Override
    public List<String> allSignalIds() {
        try (Session session = driver.session()) {
            return session.run("MATCH (s:Signal) RETURN s.event_id AS eventId ORDER BY eventId")
                    .list(r -> r.get("eventId").asString());
        }
    }

    @Override
    public void markPending(List<String> eventIds) {
        try (Session session = driver.session()) {
            session.executeWrite(tx -> tx.run("""
                    UNWIND $ids AS id
                    MATCH (s:Signal {event_id: id})
                    SET s.corroboration_pending = true, s.write_token = randomUUID()
                    """, Map.of("ids", eventIds)).consume());
        }
    }

    @Override
    public void clearPending(List<CorroborationScanner.PendingSignal> handled) {
        List<Map<String, Object>> signals = handled.stream()
                .map(p -> Map.<String, Object>of("eventId", p.eventId().toString(), "writeToken", p.writeToken()))
                .toList();
        try (Session session = driver.session()) {
            session.run("""
                    UNWIND $signals AS read
                    MATCH (s:Signal {event_id: read.eventId})
                    WHERE s.write_token = read.writeToken
                    SET s.corroboration_pending = false
                    """,
                    Map.of("signals", signals)).consume();
        }
    }

    private static String statement(Map<String, String> byLabel, String label) {
        String statement = byLabel.get(label);
        if (statement == null) {
            throw new IllegalArgumentException("not a corroborating label: " + label);
        }
        return statement;
    }
}
