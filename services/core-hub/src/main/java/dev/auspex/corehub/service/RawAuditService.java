package dev.auspex.corehub.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.OffsetDateTime;
import java.util.HexFormat;

/**
 * Records every raw Kafka message into raw_fetch_audit.
 * Idempotent: ON CONFLICT (raw_object_key) DO NOTHING.
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
            throw new IllegalArgumentException("Malformed raw payload", e);
        }
        String rawObjectKey = node.get("raw_object_key").asText();
        String sourceType   = node.get("source_type").asText();
        String externalId   = node.get("external_id").asText();
        String ingestedAt   = node.get("ingested_at").asText();
        String sha256 = node.has("content_sha256")
                ? node.get("content_sha256").asText()
                : sha256Hex(payload);

        jdbcTemplate.update(INSERT_AUDIT,
                rawObjectKey,
                sourceType,
                externalId,
                sha256,
                OffsetDateTime.parse(ingestedAt));
    }

    private static String sha256Hex(String input) {
        try {
            byte[] hash = MessageDigest.getInstance("SHA-256")
                    .digest(input.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(hash);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 not available", e);
        }
    }
}
