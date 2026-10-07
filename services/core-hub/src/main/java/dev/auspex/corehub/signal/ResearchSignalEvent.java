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
 *
 * <p>The company-level fields ({@code eventType} onwards) arrived in schema 1.1 and are
 * nullable so that 1.0 events, which lack them, still validate under minor-version tolerance.
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
        @NotNull String extractionModel,
        String eventType,
        String primaryCompany,
        List<String> programIdentifiers,
        List<String> trialIds
) {}
