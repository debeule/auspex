package dev.auspex.corehub.rest.dto;

import java.time.Instant;
import java.util.List;

/** A live ticker record (COR-019) with its score. */
public record CorroboratedSignalDto(
        String entityKey,
        String ticker,
        List<String> distinctSourceTypes,
        Instant episodeOpenedAt,
        Instant corroboratedAt,
        double confidence,
        List<String> participantEventIds
) {}
