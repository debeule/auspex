package dev.auspex.corehub.rest.dto;

import java.time.Instant;
import java.util.List;

public record CorroboratedSignalDto(
        String entityKey,
        List<String> distinctSourceTypes,
        Instant corroboratedAt,
        double confidence,
        List<String> participantEventIds
) {}
