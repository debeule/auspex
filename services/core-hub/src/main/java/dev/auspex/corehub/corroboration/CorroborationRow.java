package dev.auspex.corehub.corroboration;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

/**
 * One row of {@code corroboration}, keyed by {@code (entity_key, ticker, participants_hash)}.
 * {@code ticker} is empty for an entity record; {@code excludedReason}, {@code publishedAt} and
 * {@code supersededBy} are null when unset.
 */
public record CorroborationRow(
        String entityKey,
        String ticker,
        String participantsHash,
        List<UUID> participantEventIds,
        int distinctSourceCount,
        Instant corroboratedAt,
        Instant episodeOpenedAt,
        Instant firstDetectedAt,
        String excludedReason,
        Instant publishedAt,
        String supersededBy
) {
    public CorroborationRow {
        participantEventIds = List.copyOf(participantEventIds);
    }

    public boolean live() {
        return supersededBy == null;
    }
}
