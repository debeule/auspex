package dev.auspex.corehub;

import com.fasterxml.jackson.databind.JsonNode;
import dev.auspex.corehub.corroboration.CorroboratedSignalEvent;
import dev.auspex.corehub.corroboration.CorroborationScanner;
import dev.auspex.corehub.corroboration.CorroborationService;
import dev.auspex.corehub.persistence.Neo4jWriteService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

import static java.util.concurrent.TimeUnit.SECONDS;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.awaitility.Awaitility.await;

class CorroborationEpisodeIT extends AbstractIT {

    private static final String PREPRINT = "CRISPR base editing restores HBB expression in mice";
    private static final String PAPER = "CRISPR Base-Editing Restores HBB Expression in Mice.";

    @Autowired
    Neo4jWriteService graph;

    @Autowired
    CorroborationService corroborationService;

    @Autowired
    CorroborationScanner scanner;

    @Autowired
    @Qualifier("corroboratedKafkaTemplate")
    KafkaTemplate<Object, Object> corroboratedKafkaTemplate;

    @Autowired
    @Qualifier("jpaTransactionManager")
    PlatformTransactionManager transactionManager;

    CorroborationSignals signals;

    @BeforeEach
    void setUpSignals() {
        signals = new CorroborationSignals(objectMapper, jdbcTemplate, neo4jDriver);
    }

    private UUID write(String sourceType, String date, String title, List<String> genes, List<String> mechanisms) {
        UUID id = UUID.randomUUID();
        graph.upsert(signals.event(id, sourceType, date, title, genes, mechanisms, List.of()));
        return id;
    }

    @Test
    void overlappingGroupsOnOneEntityLeaveOneLiveRecord() {
        // Four signals: the test profile's degree cap skips an entity with more.
        UUID a = write("biorxiv", "2024-01-01", "a", List.of("SOD1"), List.of());
        UUID b = write("edgar", "2024-01-10", "b", List.of("SOD1"), List.of());
        corroborationService.runCorroboration();
        UUID c = write("clinicaltrials", "2024-01-20", "c", List.of("SOD1"), List.of());
        corroborationService.runCorroboration();
        UUID d = write("pubmed", "2024-02-01", "d", List.of("SOD1"), List.of());
        corroborationService.runCorroboration();

        assertThat(signals.live()).singleElement().satisfies(row -> {
            assertThat(row.participants()).containsExactlyInAnyOrderElementsOf(List.of(a, b, c, d));
            assertThat(row.episodeOpenedAt()).isEqualTo(Instant.parse("2024-01-10T00:00:00Z"));
            assertThat(row.distinctSourceCount()).isEqualTo(4);
        });
        assertThat(signals.all()).hasSize(3);
    }

    @Test
    void joiningSignalSupersedesTheRecordAndIsPublishedOnce() throws Exception {
        write("biorxiv", "2024-01-01", "a", List.of("TTR"), List.of());
        write("edgar", "2024-01-10", "b", List.of("TTR"), List.of());
        corroborationService.runCorroboration();
        write("clinicaltrials", "2024-02-01", "c", List.of("TTR"), List.of());
        corroborationService.runCorroboration();
        corroborationService.runCorroboration();

        await().atMost(5, SECONDS).untilAsserted(() ->
                assertThat(testCorroboratedListener.records()).hasSize(2));
        JsonNode opening = objectMapper.readTree(testCorroboratedListener.records().get(0).value());
        JsonNode extension = objectMapper.readTree(testCorroboratedListener.records().get(1).value());
        assertThat(opening.get("corroborated_at").asText()).isEqualTo(opening.get("episode_opened_at").asText());
        assertThat(extension.get("corroborated_at").asText()).isEqualTo("2024-02-01T00:00:00Z");
        assertThat(extension.get("episode_opened_at").asText()).isEqualTo("2024-01-10T00:00:00Z");
        assertThat(extension.get("participant_event_ids")).hasSize(3);
        assertThat(signals.all()).hasSize(2);
        assertThat(signals.live()).singleElement().satisfies(r -> assertThat(r.participants()).hasSize(3));
        String successor = jdbcTemplate.queryForObject(
                "SELECT participants_hash FROM corroboration WHERE superseded_by IS NULL", String.class);
        assertThat(jdbcTemplate.queryForObject(
                "SELECT superseded_by FROM corroboration WHERE superseded_by IS NOT NULL", String.class))
                .isEqualTo(successor);
    }

    @Test
    void signalAfterTheEpisodeWindowOpensASecondRecordOnlyWithTwoFreshSources() {
        write("biorxiv", "2024-01-01", "a", List.of("APOE"), List.of());
        write("edgar", "2024-01-10", "b", List.of("APOE"), List.of());
        write("biorxiv", "2024-05-01", "c", List.of("APOE"), List.of());
        corroborationService.runCorroboration();
        assertThat(signals.live()).hasSize(1);

        write("edgar", "2024-05-10", "d", List.of("APOE"), List.of());
        corroborationService.runCorroboration();

        assertThat(signals.live()).extracting(CorroborationSignals.Row::episodeOpenedAt).containsExactly(
                Instant.parse("2024-01-10T00:00:00Z"), Instant.parse("2024-05-10T00:00:00Z"));
    }

    @Test
    void spellingVariantsOfOneMechanismCorroborateUnderOneEntityKey() {
        write("biorxiv", "2024-01-01", "a", List.of(), List.of("Genome-Editing"));
        write("edgar", "2024-01-10", "b", List.of(), List.of("gene editing"));
        write("clinicaltrials", "2024-01-20", "c", List.of(), List.of("Prime-Editing"));
        write("pubmed", "2024-01-25", "d", List.of(), List.of("prime editing"));

        corroborationService.runCorroboration();

        assertThat(signals.live()).extracting(CorroborationSignals.Row::entityKey)
                .containsExactlyInAnyOrder("gene editing:Mechanism", "prime editing:Mechanism");
    }

    @Test
    void broadMechanismRecordIsStoredExcludedAndNeverPublished() {
        write("biorxiv", "2024-01-01", "a", List.of(), List.of("Gene Therapy"));
        write("edgar", "2024-01-10", "b", List.of(), List.of("gene therapy"));

        corroborationService.runCorroboration();
        corroborationService.runCorroboration();

        assertThat(signals.live()).singleElement().satisfies(row -> {
            assertThat(row.entityKey()).isEqualTo("gene therapy:Mechanism");
            assertThat(row.excludedReason()).isEqualTo("broad_entity");
            assertThat(row.publishedAt()).isNull();
        });
        await().during(1, SECONDS).atMost(3, SECONDS).untilAsserted(() ->
                assertThat(testCorroboratedListener.records()).isEmpty());
    }

    @Test
    void preprintAndItsPaperAloneProduceNoRecord() {
        UUID preprint = write("biorxiv", "2024-01-01", PREPRINT, List.of("HBB"), List.of());
        write("pubmed", "2024-02-01", PAPER, List.of("HBB"), List.of());
        corroborationService.runCorroboration();
        assertThat(signals.all()).isEmpty();

        UUID unrelated = write("pubmed", "2024-02-10", "Phase 2 outcomes of an HBB inducer in adults",
                List.of("HBB"), List.of());
        corroborationService.runCorroboration();

        assertThat(signals.live()).singleElement().satisfies(row -> {
            assertThat(row.participants()).contains(preprint, unrelated).hasSize(3);
            assertThat(row.distinctSourceCount()).isEqualTo(2);
            assertThat(row.episodeOpenedAt()).isEqualTo(Instant.parse("2024-02-10T00:00:00Z"));
        });
    }

    @Test
    void futureDatedSignalIsHeldUntilItsDateThenCorroborates() {
        clock.set(Instant.parse("2024-06-15T12:00:00Z"));
        write("biorxiv", "2024-06-01", "a", List.of("PCSK9"), List.of());
        UUID future = write("pubmed", "2024-07-01", "b", List.of("PCSK9"), List.of());

        corroborationService.runCorroboration();

        assertThat(signals.all()).isEmpty();
        assertThat(signals.isPending(future)).isTrue();

        clock.set(Instant.parse("2024-07-02T00:00:00Z"));
        corroborationService.runCorroboration();

        assertThat(signals.live()).singleElement().satisfies(row ->
                assertThat(row.corroboratedAt()).isEqualTo(Instant.parse("2024-07-01T00:00:00Z")));
        assertThat(signals.isPending(future)).isFalse();
    }

    @Test
    void recordDatedAfterItsDetectionIsRefusedByTheTable() {
        String insert = """
                INSERT INTO corroboration (entity_key, ticker, participants_hash, participant_event_ids,
                    distinct_source_count, corroborated_at, episode_opened_at, first_detected_at)
                VALUES ('X:GeneTarget', '', ?, ARRAY[gen_random_uuid()], 2, ?::timestamptz, ?::timestamptz, ?::timestamptz)
                """;

        assertThatThrownBy(() -> jdbcTemplate.update(insert, "after-detection",
                "2024-07-01T00:00:00Z", "2024-06-01T00:00:00Z", "2024-06-15T00:00:00Z"))
                .isInstanceOf(DataIntegrityViolationException.class);
        assertThatThrownBy(() -> jdbcTemplate.update(insert, "opened-after-corroborated",
                "2024-06-01T00:00:00Z", "2024-06-05T00:00:00Z", "2024-06-15T00:00:00Z"))
                .isInstanceOf(DataIntegrityViolationException.class);
        jdbcTemplate.update(insert, "valid", "2024-06-01T00:00:00Z", "2024-06-01T00:00:00Z", "2024-06-15T00:00:00Z");
        assertThat(signals.all()).hasSize(1);
    }

    @Test
    void reExtractionThatDropsTheEntitySupersedesItsRecord() {
        UUID a = write("biorxiv", "2024-01-01", "a", List.of(), List.of("exon skipping"));
        write("edgar", "2024-01-10", "b", List.of(), List.of("exon skipping"));
        corroborationService.runCorroboration();
        assertThat(signals.live()).hasSize(1);

        graph.upsert(signals.event(a, "biorxiv", "2024-01-01", "a", List.of(), List.of("base editing"), List.of()));
        corroborationService.runCorroboration();

        assertThat(signals.live()).isEmpty();
        assertThat(jdbcTemplate.queryForObject("SELECT superseded_by FROM corroboration", String.class))
                .isEqualTo("rules");
    }

    @Test
    void commitFailingAfterAnAcknowledgedSendPublishesAgainOnTheNextScan() throws Exception {
        write("biorxiv", "2024-01-01", "a", List.of("LRRK2"), List.of());
        write("edgar", "2024-01-10", "b", List.of("LRRK2"), List.of());

        // A scan whose sends are acknowledged and whose commit then fails: rolled back, nothing cleared.
        new TransactionTemplate(transactionManager).executeWithoutResult(status -> {
            for (CorroboratedSignalEvent event : scanner.scan().events()) {
                try {
                    corroboratedKafkaTemplate.send("auspex.signals.corroborated", event.entityKey(), event).get();
                } catch (Exception e) {
                    throw new IllegalStateException(e);
                }
            }
            status.setRollbackOnly();
        });
        assertThat(signals.all()).isEmpty();

        corroborationService.runCorroboration();

        await().atMost(5, SECONDS).untilAsserted(() ->
                assertThat(testCorroboratedListener.records()).hasSize(2));
        JsonNode first = objectMapper.readTree(testCorroboratedListener.records().get(0).value());
        JsonNode second = objectMapper.readTree(testCorroboratedListener.records().get(1).value());
        for (String identity : List.of("entity_key", "ticker", "participants_hash")) {
            assertThat(second.get(identity)).isEqualTo(first.get(identity));
        }
        assertThat(signals.live()).singleElement().satisfies(r -> assertThat(r.publishedAt()).isNotNull());
    }
}
