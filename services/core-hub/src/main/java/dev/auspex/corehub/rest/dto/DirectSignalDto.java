package dev.auspex.corehub.rest.dto;

import java.time.Instant;

public record DirectSignalDto(
        String eventId,
        String sourceType,
        String title,
        String summary,
        double confidenceScore,
        Instant publishedAt
) {}
