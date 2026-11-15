package dev.auspex.corehub.corroboration;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

/**
 * Payload published to auspex.signals.corroborated for live, non-excluded corroboration records.
 * Serialized as snake_case JSON with ISO-8601 timestamps and no type header. A consumer treats
 * {@code (entity_key, ticker, participants_hash)} as the event's identity and tells an opening from
 * an extension by {@code corroborated_at = episode_opened_at}. {@code ticker} is empty for an
 * entity record.
 */
public record CorroboratedSignalEvent(
        String entityKey,
        String ticker,
        String participantsHash,
        List<UUID> participantEventIds,
        int distinctSourceCount,
        List<String> sourceTypes,
        Instant corroboratedAt,
        Instant episodeOpenedAt,
        Instant firstDetectedAt,
        String schemaVersion
) {
    public static final String SCHEMA_VERSION = "1.0";
}
