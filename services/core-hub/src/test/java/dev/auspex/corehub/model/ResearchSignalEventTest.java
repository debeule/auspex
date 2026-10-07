package dev.auspex.corehub.model;

import dev.auspex.corehub.signal.ResearchSignalEvent;
import dev.auspex.corehub.signal.SchemaVersion;

import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.json.JsonMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import jakarta.validation.ConstraintViolation;
import jakarta.validation.Validation;
import jakarta.validation.Validator;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.io.InputStream;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.List;
import java.util.Set;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Deserializes the generated contract fixture with an ObjectMapper configured like the
 * application's, without starting a Spring context.
 */
class ResearchSignalEventTest {

    private ObjectMapper mapper;
    private Validator validator;

    @BeforeEach
    void setUp() {
        mapper = JsonMapper.builder()
                .addModule(new JavaTimeModule())
                .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false)
                .propertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE)
                .build();

        try (var factory = Validation.buildDefaultValidatorFactory()) {
            validator = factory.getValidator();
        }
    }

    @Test
    void test_signal_event_json_contract_matches_generated_python_fixture() throws Exception {
        String json = loadFixture("contract/signal_event_v1.json");
        ResearchSignalEvent event = mapper.readValue(json, ResearchSignalEvent.class);

        assertThat(event.schemaVersion()).isEqualTo("1.1");
        assertThat(event.eventId()).isEqualTo(UUID.fromString("c1261cdc-1cf0-5bca-922d-7d098c8f0d6f"));
        assertThat(event.extractionId()).isEqualTo(UUID.fromString("b3bf98e4-bc23-59be-ab4e-425aa86d631d"));
        assertThat(event.externalId()).isEqualTo("ext-contract-001");
        assertThat(event.canonicalId()).isEqualTo("doi:10.1101/2024.06.01.600001");
        assertThat(event.rawObjectKey()).startsWith("raw/biorxiv/");
        assertThat(event.sourceType()).isEqualTo("biorxiv");
        assertThat(event.publishedDate()).isEqualTo(Instant.parse("2024-06-15T12:00:00Z"));
        assertThat(event.ingestedAt()).isEqualTo(Instant.parse("2024-06-15T12:00:00Z"));
        assertThat(event.geneTargets()).containsExactly("BCL11A", "HBB");
        assertThat(event.mechanisms()).containsExactlyInAnyOrder("base editing", "CRISPR");
        assertThat(event.companiesMentioned()).containsExactly("Beam Therapeutics");
        assertThat(event.confidenceScore()).isEqualByComparingTo(new BigDecimal("0.92"));
        assertThat(event.promptVersion()).isEqualTo("v1");
        assertThat(event.extractionModel()).isEqualTo("gpt-4o");
        assertThat(event.eventType()).isEqualTo("preclinical_data");
        assertThat(event.primaryCompany()).isEqualTo("Beam Therapeutics");
        assertThat(event.programIdentifiers()).containsExactly("BEAM-101");
        assertThat(event.trialIds()).containsExactly("NCT05456880");

        Set<ConstraintViolation<ResearchSignalEvent>> violations = validator.validate(event);
        assertThat(violations).isEmpty();
    }

    @Test
    void test_minor_version_bump_with_extra_field_is_accepted() throws Exception {
        String json = loadFixture("contract/signal_event_v1.json");
        // Inject an unknown field that a 1.2 schema might add
        String extended = json.replace(
                "\"schema_version\": \"1.1\"",
                "\"schema_version\": \"1.2\", \"new_field_added_in_v1_2\": \"some value\""
        );
        ResearchSignalEvent event = mapper.readValue(extended, ResearchSignalEvent.class);
        assertThat(event.schemaVersion()).isEqualTo("1.2");
        // Unknown field was silently ignored (FAIL_ON_UNKNOWN_PROPERTIES=false)
    }

    @Test
    void test_schema_one_zero_event_without_company_fields_is_valid() throws Exception {
        ObjectNode payload = (ObjectNode) mapper.readTree(loadFixture("contract/signal_event_v1.json"));
        payload.put("schema_version", "1.0");
        payload.remove(List.of("event_type", "primary_company", "program_identifiers", "trial_ids"));

        ResearchSignalEvent event = mapper.treeToValue(payload, ResearchSignalEvent.class);

        assertThat(event.eventType()).isNull();
        assertThat(event.trialIds()).isNull();
        assertThat(validator.validate(event)).isEmpty();
    }

    @Test
    void test_unknown_major_schema_version_is_classified_as_deterministic_failure() {
        SchemaVersion v2 = SchemaVersion.parse("2.0");
        assertThat(SchemaVersion.isKnownMajor(v2)).isFalse();

        SchemaVersion v1 = SchemaVersion.parse("1.0");
        assertThat(SchemaVersion.isKnownMajor(v1)).isTrue();
    }

    @Test
    void test_missing_confidence_score_is_rejected_not_defaulted_to_zero() throws Exception {
        String json = loadFixture("contract/signal_event_v1.json");
        String missing = json.replace(",\n  \"confidence_score\": 0.92", "");
        ResearchSignalEvent event = mapper.readValue(missing, ResearchSignalEvent.class);
        // confidence_score is null (BigDecimal, not a primitive double)
        assertThat(event.confidenceScore()).isNull();
        // @NotNull violation must be present
        Set<ConstraintViolation<ResearchSignalEvent>> violations = validator.validate(event);
        assertThat(violations).extracting(v -> v.getPropertyPath().toString())
                .contains("confidenceScore");
    }

    @Test
    void test_snake_case_payload_maps_to_every_record_component() throws Exception {
        String json = loadFixture("contract/signal_event_v1.json");
        ResearchSignalEvent event = mapper.readValue(json, ResearchSignalEvent.class);

        // All non-null required fields must be populated — no silent mapping failure
        assertThat(event.schemaVersion()).isNotNull();
        assertThat(event.eventId()).isNotNull();
        assertThat(event.extractionId()).isNotNull();
        assertThat(event.externalId()).isNotNull();
        assertThat(event.rawObjectKey()).isNotNull();
        assertThat(event.sourceType()).isNotNull();
        assertThat(event.sourceUrl()).isNotNull();
        assertThat(event.publishedDate()).isNotNull();
        assertThat(event.publishedDateField()).isNotNull();
        assertThat(event.ingestedAt()).isNotNull();
        assertThat(event.title()).isNotNull();
        assertThat(event.rawTextSnippet()).isNotNull();
        assertThat(event.geneTargets()).isNotNull().isNotEmpty();
        assertThat(event.mechanisms()).isNotNull().isNotEmpty();
        assertThat(event.companiesMentioned()).isNotNull().isNotEmpty();
        assertThat(event.summary()).isNotNull();
        assertThat(event.directionality()).isNotNull();
        assertThat(event.confidenceScore()).isNotNull();
        assertThat(event.promptVersion()).isNotNull();
        assertThat(event.prefilterVersion()).isNotNull();
        assertThat(event.extractionModel()).isNotNull();
        assertThat(event.eventType()).isNotNull();
        assertThat(event.primaryCompany()).isNotNull();
        assertThat(event.programIdentifiers()).isNotNull().isNotEmpty();
        assertThat(event.trialIds()).isNotNull().isNotEmpty();
    }

    @Test
    void test_schema_version_compares_as_major_minor_integers_not_strings() {
        SchemaVersion v1_9 = SchemaVersion.parse("1.9");
        SchemaVersion v1_10 = SchemaVersion.parse("1.10");

        // Text sort: "1.10" < "1.9" — this is wrong; we must compare as integers
        assertThat("1.10".compareTo("1.9")).isNegative(); // the broken comparator
        assertThat(v1_10).isGreaterThan(v1_9);            // the correct comparator
    }

    private String loadFixture(String resourcePath) throws Exception {
        try (InputStream in = getClass().getClassLoader().getResourceAsStream(resourcePath)) {
            assertThat(in).as("fixture not found on classpath: %s", resourcePath).isNotNull();
            return new String(in.readAllBytes(), StandardCharsets.UTF_8);
        }
    }
}
