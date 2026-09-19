package dev.auspex.corehub.signal;

import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotNull;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.UUID;

/**
 * Wire contract for the auspex.signals.extracted Kafka topic.
 * Snake_case mapping is applied by the application Jackson ObjectMapper.
 * Every @Transactional use site must qualify the transaction manager.
 */
public record ResearchSignalEvent(
        @NotNull String schemaVersion,
        @NotNull UUID eventId,
        @NotNull UUID extractionId,
        @NotNull String externalId,
        String canonicalId,
        @NotNull String rawObjectKey,
        @NotNull String sourceType,
        @NotNull String sourceUrl,
        @NotNull Instant publishedDate,
        @NotNull String publishedDateField,
        @NotNull Instant ingestedAt,
        @NotNull String title,
        @NotNull String rawTextSnippet,
        @NotNull List<String> geneTargets,
        @NotNull List<String> mechanisms,
        @NotNull List<String> companiesMentioned,
        @NotNull String summary,
        @NotNull String directionality,
        @NotNull @DecimalMin("0.0") @DecimalMax("1.0") BigDecimal confidenceScore,
        @NotNull String promptVersion,
        @NotNull String prefilterVersion,
        @NotNull String extractionModel
) {}
