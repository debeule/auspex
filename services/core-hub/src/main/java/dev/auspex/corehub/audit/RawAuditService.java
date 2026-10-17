package dev.auspex.corehub.audit;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.OffsetDateTime;
import java.time.format.DateTimeParseException;

/**
 * Records every raw pointer into raw_fetch_audit.
 * Idempotent: ON CONFLICT (raw_object_key) DO NOTHING.
 * A pointer that is not JSON, lacks a required field, or has a {@code retrieved_at} without an
 * offset throws {@link InvalidRawPointerException}.
 */
@Service
public class RawAuditService {

    private static final String INSERT_AUDIT = """
            INSERT INTO raw_fetch_audit (raw_object_key, source_type, external_id, content_sha256, retrieved_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (raw_object_key) DO NOTHING
            """;

    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper;

    public RawAuditService(JdbcTemplate jdbcTemplate, ObjectMapper objectMapper) {
        this.jdbcTemplate = jdbcTemplate;
        this.objectMapper = objectMapper;
    }

    @Transactional(transactionManager = "jpaTransactionManager")
    public void record(String payload) {
        JsonNode node;
        try {
            node = objectMapper.readTree(payload);
        } catch (Exception e) {
            throw new InvalidRawPointerException("Raw pointer is not JSON", e);
        }
        if (node == null || !node.isObject()) {
            throw new InvalidRawPointerException("Raw pointer is not a JSON object");
        }
        String rawObjectKey  = required(node, "raw_object_key");
        String sourceType    = required(node, "source_type");
        String externalId    = required(node, "external_id");
        String contentSha256 = required(node, "content_sha256");
        OffsetDateTime retrievedAt;
        try {
            retrievedAt = OffsetDateTime.parse(required(node, "retrieved_at"));
        } catch (DateTimeParseException e) {
            throw new InvalidRawPointerException(
                    "Raw pointer retrieved_at is not an ISO-8601 timestamp with an offset", e);
        }

        jdbcTemplate.update(INSERT_AUDIT,
                rawObjectKey,
                sourceType,
                externalId,
                contentSha256,
                retrievedAt);
    }

    private static String required(JsonNode node, String field) {
        JsonNode value = node.get(field);
        if (value == null || !value.isTextual() || value.asText().isBlank()) {
            throw new InvalidRawPointerException("Raw pointer is missing " + field);
        }
        return value.asText();
    }
}
