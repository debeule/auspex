package dev.auspex.corehub.rest.dto;

import java.time.Instant;
import java.util.List;

/**
 * A live entity record that lists one of the ticker's direct signals but has no ticker record of
 * that ticker; {@code reason} is {@code broad_entity} or {@code no_independent_pair_for_ticker}.
 * It carries no score.
 */
public record ContextCorroborationDto(
        String entityKey,
        String reason,
        List<String> distinctSourceTypes,
        Instant episodeOpenedAt,
        Instant corroboratedAt,
        List<String> participantEventIds
) {}
