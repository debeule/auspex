package dev.auspex.corehub.corroboration;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

/**
 * Payload published to auspex.signals.corroborated for non-superseded corroboration records.
 * Serialized as snake_case JSON with ISO-8601 timestamps and no type header.
 */
public record CorroboratedSignalEvent(
        String entityKey,
        String participantsHash,
        List<UUID> participantEventIds,
        int distinctSourceCount,
        Instant corroboratedAt,
        Instant firstDetectedAt
) {}
