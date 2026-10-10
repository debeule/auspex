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
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;

@Service
public class CorroborationScanner {

    // 90 days in seconds (inclusive boundary — verified in CorroborationServiceContractTest)
    private static final long WINDOW_SECONDS = 90L * 24 * 60 * 60;

    @Value("${corroboration.degree-cap:500}")
    private int degreeCap;

    private final Driver neo4jDriver;
    private final JdbcTemplate jdbcTemplate;
    private final EntityNormalizer entityNormalizer;

    public CorroborationScanner(Driver neo4jDriver, JdbcTemplate jdbcTemplate, EntityNormalizer entityNormalizer) {
        this.neo4jDriver = neo4jDriver;
        this.jdbcTemplate = jdbcTemplate;
        this.entityNormalizer = entityNormalizer;
    }

    public List<CorroboratedSignalEvent> scan() {
        Instant watermark = readWatermark();
        List<EntityGroup> groups = findGroups(watermark);
        if (groups.isEmpty()) {
            return List.of();
        }

        Instant maxIngestedAt = Instant.EPOCH;
        List<CorroboratedSignalEvent> toPublish = new ArrayList<>();

        for (EntityGroup group : groups) {
            CorroboratedSignalEvent event = processGroup(group);
            if (event != null) {
                toPublish.add(event);
            }
            if (group.triggerIngestedAt().isAfter(maxIngestedAt)) {
                maxIngestedAt = group.triggerIngestedAt();
            }
        }

        writeWatermark(maxIngestedAt);
        return toPublish;
    }

    protected Instant readWatermark() {
        List<Instant> rows = jdbcTemplate.query(
                "SELECT watermark FROM corroboration_state",
                (rs, n) -> rs.getTimestamp("watermark").toInstant());
        return rows.isEmpty() ? Instant.EPOCH : rows.get(0);
    }

    protected List<EntityGroup> findGroups(Instant watermark) {
        try (Session session = neo4jDriver.session()) {
            return session.run("""
                    MATCH (s:Signal)
                    WHERE s.ingested_at > $watermark
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
                           s.ingested_at AS triggerIngestedAt,
                           e.name AS entityName,
                           labels(e)[0] AS entityLabel,
                           collect(DISTINCT {
                               eventId: partner.event_id,
                               sourceType: partner.source_type,
                               publishedDateEpoch: partner.published_date.epochSeconds
                           }) AS partners
                    """,
                    Map.of(
                            "watermark", watermark.atZone(ZoneOffset.UTC),
                            "degreeCap", degreeCap,
                            "windowSeconds", WINDOW_SECONDS
                    ))
                    .list(record -> new EntityGroup(
                            UUID.fromString(record.get("triggerEventId").asString()),
                            record.get("triggerSourceType").asString(),
                            Instant.ofEpochSecond(record.get("triggerPublishedDateEpoch").asLong()),
                            record.get("triggerIngestedAt").asZonedDateTime().toInstant(),
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

    protected void writeWatermark(Instant ts) {
        jdbcTemplate.update("""
                INSERT INTO corroboration_state (singleton, watermark) VALUES (true, ?)
                ON CONFLICT (singleton) DO UPDATE SET watermark = EXCLUDED.watermark
                """,
                Timestamp.from(ts));
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
            Instant triggerIngestedAt,
            String entityName,
            String entityLabel,
            List<Partner> partners
    ) {}

    record Partner(UUID eventId, String sourceType, Instant publishedDate) {}
}
