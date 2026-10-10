package dev.auspex.corehub.corroboration;

import org.neo4j.driver.Driver;
import org.neo4j.driver.Session;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.sql.Array;
import java.sql.PreparedStatement;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;

/**
 * Finds corroborations triggered by pending signals. Every graph write marks its signal pending
 * with a fresh write token in the write's own transaction, so a signal becomes a trigger exactly
 * when its write commits, however late. A scanned signal is cleared only by {@link #clearPending},
 * and only if its token is still the one the scan read.
 */
@Service
public class CorroborationScanner {

    // 90 days in seconds (inclusive boundary — verified in CorroborationServiceContractTest)
    private static final long WINDOW_SECONDS = 90L * 24 * 60 * 60;

    @Value("${corroboration.degree-cap:500}")
    private int degreeCap;

    private final Driver neo4jDriver;
    private final JdbcTemplate jdbcTemplate;
    private final EntityNormalizer entityNormalizer;
    private final int scanBatchSize;

    public CorroborationScanner(Driver neo4jDriver, JdbcTemplate jdbcTemplate, EntityNormalizer entityNormalizer,
                                @Value("${corroboration.scan-batch-size}") int scanBatchSize) {
        this.neo4jDriver = neo4jDriver;
        this.jdbcTemplate = jdbcTemplate;
        this.entityNormalizer = entityNormalizer;
        this.scanBatchSize = scanBatchSize;
    }

    /**
     * Inserts the corroborations triggered by up to one batch of pending signals and returns the
     * events to publish with the signals read. Nothing is cleared here.
     */
    public ScanResult scan() {
        List<PendingSignal> pending = readPending();
        if (pending.isEmpty()) {
            return new ScanResult(List.of(), List.of());
        }

        List<CorroboratedSignalEvent> toPublish = new ArrayList<>();
        for (EntityGroup group : findGroups(pending.stream().map(PendingSignal::eventId).toList())) {
            CorroboratedSignalEvent event = processGroup(group);
            if (event != null) {
                toPublish.add(event);
            }
        }
        return new ScanResult(toPublish, pending);
    }

    /** Clears the pending flag on each signal whose write token is still the one the scan read. */
    public void clearPending(List<PendingSignal> handled) {
        if (handled.isEmpty()) {
            return;
        }
        List<Map<String, Object>> signals = handled.stream()
                .map(p -> Map.<String, Object>of("eventId", p.eventId().toString(), "writeToken", p.writeToken()))
                .toList();
        try (Session session = neo4jDriver.session()) {
            session.run("""
                    UNWIND $signals AS read
                    MATCH (s:Signal {event_id: read.eventId})
                    WHERE s.write_token = read.writeToken
                    SET s.corroboration_pending = false
                    """,
                    Map.of("signals", signals)).consume();
        }
    }

    protected List<PendingSignal> readPending() {
        try (Session session = neo4jDriver.session()) {
            return session.run("""
                    MATCH (s:Signal)
                    WHERE s.corroboration_pending = true
                    RETURN s.event_id AS eventId, s.write_token AS writeToken
                    LIMIT $batchSize
                    """,
                    Map.of("batchSize", scanBatchSize))
                    .list(record -> new PendingSignal(
                            UUID.fromString(record.get("eventId").asString()),
                            record.get("writeToken").asString()));
        }
    }

    protected List<EntityGroup> findGroups(List<UUID> triggerIds) {
        try (Session session = neo4jDriver.session()) {
            return session.run("""
                    UNWIND $triggerIds AS triggerId
                    MATCH (s:Signal {event_id: triggerId})
                    MATCH (s)-[:TARGETS|USES_MECHANISM]->(e)
                    WITH s, e,
                         count { (:Signal)-[:TARGETS|USES_MECHANISM]->(e) } AS degree
                    WHERE degree <= $degreeCap
                    MATCH (partner:Signal)-[:TARGETS|USES_MECHANISM]->(e)
                    WHERE partner.event_id <> s.event_id
                      AND partner.source_type <> s.source_type
                      AND abs(s.published_date.epochSeconds - partner.published_date.epochSeconds)
                              <= $windowSeconds
                    RETURN s.event_id AS triggerEventId,
                           s.source_type AS triggerSourceType,
                           s.published_date.epochSeconds AS triggerPublishedDateEpoch,
                           e.name AS entityName,
                           labels(e)[0] AS entityLabel,
                           collect(DISTINCT {
                               eventId: partner.event_id,
                               sourceType: partner.source_type,
                               publishedDateEpoch: partner.published_date.epochSeconds
                           }) AS partners
                    """,
                    Map.of(
                            "triggerIds", triggerIds.stream().map(UUID::toString).toList(),
                            "degreeCap", degreeCap,
                            "windowSeconds", WINDOW_SECONDS
                    ))
                    .list(record -> new EntityGroup(
                            UUID.fromString(record.get("triggerEventId").asString()),
                            record.get("triggerSourceType").asString(),
                            Instant.ofEpochSecond(record.get("triggerPublishedDateEpoch").asLong()),
                            record.get("entityName").asString(),
                            record.get("entityLabel").asString(),
                            record.get("partners").asList(v -> {
                                Map<String, Object> m = v.asMap();
                                return new Partner(
                                        UUID.fromString((String) m.get("eventId")),
                                        (String) m.get("sourceType"),
                                        Instant.ofEpochSecond((long) m.get("publishedDateEpoch"))
                                );
                            })
                    ));
        }
    }

    private CorroboratedSignalEvent processGroup(EntityGroup group) {
        String entityKey = entityNormalizer.normalize(group.entityName()) + ":" + group.entityLabel();

        List<UUID> allIds = new ArrayList<>();
        allIds.add(group.triggerEventId());
        group.partners().forEach(p -> allIds.add(p.eventId()));
        allIds.sort(Comparator.naturalOrder());

        List<String> allSourceTypes = new ArrayList<>();
        allSourceTypes.add(group.triggerSourceType());
        group.partners().forEach(p -> allSourceTypes.add(p.sourceType()));
        long distinctSourceCount = allSourceTypes.stream().distinct().count();

        if (distinctSourceCount < 2) {
            return null;
        }

        Instant corroboratedAt = group.partners().stream()
                .map(Partner::publishedDate)
                .reduce(group.triggerPublishedDate(), (a, b) -> a.isAfter(b) ? a : b);

        String participantsHash = computeHash(allIds);

        supersedeSubsets(entityKey, participantsHash, allIds);

        int inserted = insertCorroboration(entityKey, participantsHash, allIds,
                (int) distinctSourceCount, corroboratedAt);

        if (inserted == 0) {
            return null;
        }

        return new CorroboratedSignalEvent(
                entityKey, participantsHash, allIds,
                (int) distinctSourceCount, corroboratedAt, Instant.now());
    }

    private void supersedeSubsets(String entityKey, String newHash, List<UUID> newParticipants) {
        jdbcTemplate.update(con -> {
            PreparedStatement ps = con.prepareStatement("""
                    UPDATE corroboration
                    SET superseded_by = ?
                    WHERE entity_key = ?
                      AND participants_hash <> ?
                      AND superseded_by IS NULL
                      AND participant_event_ids <@ ?
                    """);
            ps.setString(1, newHash);
            ps.setString(2, entityKey);
            ps.setString(3, newHash);
            Array arr = con.createArrayOf("uuid",
                    newParticipants.stream().map(UUID::toString).toArray(String[]::new));
            ps.setArray(4, arr);
            return ps;
        });
    }

    private int insertCorroboration(String entityKey, String participantsHash, List<UUID> participantIds,
                                    int distinctSourceCount, Instant corroboratedAt) {
        return jdbcTemplate.update(con -> {
            PreparedStatement ps = con.prepareStatement("""
                    INSERT INTO corroboration
                        (entity_key, participants_hash, participant_event_ids,
                         distinct_source_count, corroborated_at, first_detected_at)
                    VALUES (?, ?, ?, ?, ?, now())
                    ON CONFLICT (entity_key, participants_hash) DO NOTHING
                    """);
            ps.setString(1, entityKey);
            ps.setString(2, participantsHash);
            Array arr = con.createArrayOf("uuid",
                    participantIds.stream().map(UUID::toString).toArray(String[]::new));
            ps.setArray(3, arr);
            ps.setInt(4, distinctSourceCount);
            ps.setTimestamp(5, Timestamp.from(corroboratedAt));
            return ps;
        });
    }

    private String computeHash(List<UUID> sortedIds) {
        String joined = sortedIds.stream().map(UUID::toString).collect(Collectors.joining(":"));
        try {
            byte[] hash = MessageDigest.getInstance("SHA-256")
                    .digest(joined.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(hash);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 not available", e);
        }
    }

    record EntityGroup(
            UUID triggerEventId,
            String triggerSourceType,
            Instant triggerPublishedDate,
            String entityName,
            String entityLabel,
            List<Partner> partners
    ) {}

    record Partner(UUID eventId, String sourceType, Instant publishedDate) {}

    /** A signal read by a scan, with the write token it carried when read. */
    public record PendingSignal(UUID eventId, String writeToken) {}

    public record ScanResult(List<CorroboratedSignalEvent> events, List<PendingSignal> handled) {}
}
