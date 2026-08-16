package dev.auspex.corehub.service;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

/**
 * Payload published to auspex.signals.corroborated for non-superseded corroboration records.
 * Serialized as JSON (snake_case via application.yml).
 */
record CorroboratedSignalEvent(
        String entityKey,
        String participantsHash,
        List<UUID> participantEventIds,
        int distinctSourceCount,
        Instant corroboratedAt,
        Instant firstDetectedAt
) {}
