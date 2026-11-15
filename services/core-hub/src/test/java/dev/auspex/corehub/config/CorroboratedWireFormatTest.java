package dev.auspex.corehub.config;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import dev.auspex.corehub.corroboration.CorroboratedSignalEvent;
import org.apache.kafka.common.header.internals.RecordHeaders;
import org.apache.kafka.common.serialization.Serializer;
import org.junit.jupiter.api.Test;
import org.springframework.kafka.core.DefaultKafkaProducerFactory;
import org.springframework.test.util.ReflectionTestUtils;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

/** The corroborated topic is read by the Python strategy runtime, so it follows Invariant 7. */
class CorroboratedWireFormatTest {

    private final ObjectMapper mapper = new JacksonConfig().objectMapper();

    @SuppressWarnings("unchecked")
    private Serializer<Object> corroboratedValueSerializer() {
        KafkaConfig config = new KafkaConfig();
        ReflectionTestUtils.setField(config, "bootstrapServers", "localhost:9092");
        var factory = (DefaultKafkaProducerFactory<Object, Object>)
                config.corroboratedKafkaTemplate(mapper).getProducerFactory();
        return (Serializer<Object>) factory.getValueSerializerSupplier().get();
    }

    @Test
    void test_corroborated_event_is_snake_case_json_with_iso_timestamps_and_no_type_header() throws Exception {
        var event = fixtureEvent();
        var headers = new RecordHeaders();

        JsonNode json = mapper.readTree(corroboratedValueSerializer().serialize("auspex.signals.corroborated", headers, event));

        List<String> names = new ArrayList<>();
        json.fieldNames().forEachRemaining(names::add);
        assertThat(names).containsExactlyInAnyOrder(
                "entity_key", "ticker", "participants_hash", "participant_event_ids",
                "distinct_source_count", "source_types", "corroborated_at", "episode_opened_at",
                "first_detected_at", "schema_version");
        assertThat(json.get("corroborated_at").asText()).isEqualTo("2026-03-05T14:00:00Z");
        assertThat(json.get("first_detected_at").asText()).isEqualTo("2026-03-05T20:00:00.250Z");
        assertThat(headers.toArray()).isEmpty();
    }

    /**
     * Generates {@code corroborated_event_v1.json}, which the strategy runtime's tests read. When the
     * committed file differs, the generated one is written in its place and the test fails until it
     * is committed.
     */
    @Test
    void committedCorroboratedFixtureEqualsTheGeneratedOne() throws Exception {
        byte[] serialized = corroboratedValueSerializer().serialize("auspex.signals.corroborated", new RecordHeaders(),
                fixtureEvent());
        String generated = mapper.writerWithDefaultPrettyPrinter().writeValueAsString(mapper.readTree(serialized)) + "\n";
        JsonNode json = mapper.readTree(generated);
        assertThat(json.get("ticker").asText()).isEqualTo("SRPT");
        assertThat(json.get("source_types")).extracting(JsonNode::asText).containsExactly("biorxiv", "edgar");
        assertThat(json.get("episode_opened_at").asText()).isEqualTo("2026-03-01T09:30:00Z");
        assertThat(json.get("schema_version").asText()).isEqualTo(CorroboratedSignalEvent.SCHEMA_VERSION);

        String committed = Files.exists(FIXTURE) ? Files.readString(FIXTURE, StandardCharsets.UTF_8) : null;
        if (!generated.equals(committed)) {
            Files.writeString(FIXTURE, generated, StandardCharsets.UTF_8);
        }
        assertThat(committed).as("%s was regenerated; commit it", FIXTURE).isEqualTo(generated);
    }

    private static final Path FIXTURE = Path.of("src/test/resources/contract/corroborated_event_v1.json");

    private static CorroboratedSignalEvent fixtureEvent() {
        return new CorroboratedSignalEvent(
                "SMN1:GeneTarget",
                "SRPT",
                "abc",
                List.of(UUID.fromString("00000000-0000-0000-0000-000000000001"),
                        UUID.fromString("00000000-0000-0000-0000-000000000002")),
                2,
                List.of("biorxiv", "edgar"),
                Instant.parse("2026-03-05T14:00:00Z"),
                Instant.parse("2026-03-01T09:30:00Z"),
                Instant.parse("2026-03-05T20:00:00.250Z"),
                CorroboratedSignalEvent.SCHEMA_VERSION);
    }
}
