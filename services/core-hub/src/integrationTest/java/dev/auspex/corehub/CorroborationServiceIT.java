package dev.auspex.corehub;

import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import dev.auspex.corehub.corroboration.CorroborationScanner;
import dev.auspex.corehub.persistence.Neo4jWriteService;
import dev.auspex.corehub.signal.ResearchSignalEvent;
import org.junit.jupiter.api.Test;
import org.neo4j.driver.Session;
import org.neo4j.driver.Transaction;
import org.springframework.beans.factory.annotation.Autowired;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import static java.util.concurrent.TimeUnit.SECONDS;
import static org.assertj.core.api.Assertions.assertThat;
import static org.awaitility.Awaitility.await;

/**
 * Runs the full CorroborationServiceContractTest suite against the current implementation.
 * Any replacement implementation re-runs the abstract class unmodified.
 *
 * <p>The cases below are specific to the scheduled scan: signals are written through
 * {@link Neo4jWriteService}, which marks each write pending for the next scan.
 */
class CorroborationServiceIT extends CorroborationServiceContractTest {

    @Autowired
    Neo4jWriteService neo4jWriteService;

    @Autowired
    CorroborationScanner scanner;

    @Test
    void signalWrittenAfterNewerSignalsWereScannedIsCorroborated() {
        ResearchSignalEvent partner = event(UUID.randomUUID(), "sec_edgar", "2024-06-01T10:00:00Z",
                List.of("NTRK2"), List.of());
        neo4jWriteService.upsert(partner);
        corroborationService.runCorroboration();
        neo4jWriteService.upsert(event(UUID.randomUUID(), "clinicaltrials", "2024-06-05T10:00:00Z",
                List.of("UNRELATED"), List.of()));
        corroborationService.runCorroboration();

        ResearchSignalEvent late = event(UUID.randomUUID(), "biorxiv", "2024-06-02T10:00:00Z",
                List.of("NTRK2"), List.of());
        neo4jWriteService.upsert(late);
        corroborationService.runCorroboration();

        assertThat(liveParticipants()).containsExactlyInAnyOrder(partner.eventId(), late.eventId());
    }

    @Test
    void writeCommittingLongAfterItStartedIsCorroborated() throws Exception {
        ResearchSignalEvent partner = event(UUID.randomUUID(), "sec_edgar", "2024-06-01T10:00:00Z",
                List.of(), List.of("locked mechanism"));
        neo4jWriteService.upsert(partner);
        corroborationService.runCorroboration();

        ResearchSignalEvent late = event(UUID.randomUUID(), "biorxiv", "2024-06-01T09:00:00Z",
                List.of(), List.of("locked mechanism"));
        ExecutorService writer = Executors.newSingleThreadExecutor();
        try (Session lockSession = neo4jDriver.session()) {
            Transaction lock = lockSession.beginTransaction();
            CompletableFuture<Void> lateWrite;
            try {
                // Holding a write lock on the shared Mechanism keeps the late write's transaction
                // open: it creates its Signal, then waits to link it to the locked node.
                lock.run("MATCH (m:Mechanism {name: $name}) SET m.held = true",
                        Map.of("name", "locked mechanism")).consume();
                lateWrite = CompletableFuture.runAsync(() -> neo4jWriteService.upsert(late), writer);
                await().atMost(20, SECONDS).until(this::aTransactionIsBlocked);

                for (int i = 0; i < 3; i++) {
                    neo4jWriteService.upsert(event(UUID.randomUUID(), "fda", "2024-06-0" + (3 + i) + "T10:00:00Z",
                            List.of("UNRELATED_" + i), List.of()));
                    corroborationService.runCorroboration();
                }
                assertThat(totalCorroborationCount()).isZero();
                assertThat(signalCount(late.eventId())).isZero();

                lock.commit();
            } finally {
                if (lock.isOpen()) {
                    lock.rollback();
                }
            }
            lateWrite.get(20, SECONDS);
        } finally {
            writer.shutdownNow();
        }

        corroborationService.runCorroboration();

        assertThat(liveParticipants()).containsExactlyInAnyOrder(partner.eventId(), late.eventId());
    }

    @Test
    void signalRewrittenDuringAScanStaysPending() {
        ResearchSignalEvent signal = event(UUID.randomUUID(), "biorxiv", "2024-06-01T10:00:00Z",
                List.of("KRAS"), List.of());
        neo4jWriteService.upsert(signal);

        CorroborationScanner.ScanResult scan = scanner.scan();
        neo4jWriteService.upsert(signal);
        scanner.clearPending(scan.handled());

        assertThat(scan.handled()).extracting(CorroborationScanner.PendingSignal::eventId)
                .containsExactly(signal.eventId());
        assertThat(isPending(signal.eventId())).isTrue();
    }

    @Test
    void reExtractedSignalIsScannedAgain() {
        ResearchSignalEvent older = event(UUID.randomUUID(), "sec_edgar", "2024-06-01T10:00:00Z",
                List.of(), List.of("prime editing"));
        UUID eventId = UUID.randomUUID();
        neo4jWriteService.upsert(older);
        neo4jWriteService.upsert(event(eventId, "biorxiv", "2024-06-02T10:00:00Z",
                List.of(), List.of("base editing")));
        corroborationService.runCorroboration();
        assertThat(totalCorroborationCount()).isZero();

        neo4jWriteService.upsert(event(eventId, "biorxiv", "2024-06-03T10:00:00Z",
                List.of(), List.of("base editing", "prime editing")));
        corroborationService.runCorroboration();

        assertThat(liveParticipants()).containsExactlyInAnyOrder(older.eventId(), eventId);
    }

    @Test
    void pendingSignalWithoutPartnersIsCleared() {
        ResearchSignalEvent signal = event(UUID.randomUUID(), "biorxiv", "2024-06-01T10:00:00Z",
                List.of("LONELY"), List.of());
        neo4jWriteService.upsert(signal);
        assertThat(isPending(signal.eventId())).isTrue();

        corroborationService.runCorroboration();

        assertThat(isPending(signal.eventId())).isFalse();
    }

    @Test
    void corroborationStateTableIsGone() {
        Object table = jdbcTemplate.queryForObject(
                "SELECT to_regclass('public.corroboration_state')", Object.class);
        assertThat(table).isNull();
    }

    private ResearchSignalEvent event(UUID eventId, String sourceType, String ingestedAt,
                                      List<String> geneTargets, List<String> mechanisms) {
        try {
            ObjectNode node = (ObjectNode) objectMapper.readTree(TestFixtures.validSignalJson());
            node.put("event_id", eventId.toString());
            node.put("extraction_id", UUID.randomUUID().toString());
            node.put("external_id", "ext-" + eventId);
            node.put("source_type", sourceType);
            node.put("raw_object_key", "raw/" + sourceType + "/ext-" + eventId + "/20240615T120000Z-abcdef12.json");
            node.put("published_date", "2024-05-20T00:00:00Z");
            node.put("ingested_at", ingestedAt);
            node.set("gene_targets", array(geneTargets));
            node.set("mechanisms", array(mechanisms));
            node.set("companies_mentioned", array(List.of()));
            return objectMapper.treeToValue(node, ResearchSignalEvent.class);
        } catch (Exception ex) {
            throw new IllegalStateException(ex);
        }
    }

    private ArrayNode array(List<String> values) {
        ArrayNode array = objectMapper.createArrayNode();
        values.forEach(array::add);
        return array;
    }

    private List<UUID> liveParticipants() {
        List<UUID> rows = jdbcTemplate.query(
                "SELECT participant_event_ids FROM corroboration WHERE superseded_by IS NULL",
                (rs, n) -> List.of((UUID[]) rs.getArray("participant_event_ids").getArray()))
                .stream().flatMap(List::stream).toList();
        assertThat(liveCorroborationCount()).isEqualTo(1);
        return rows;
    }

    private boolean isPending(UUID eventId) {
        try (Session session = neo4jDriver.session()) {
            return session.run("MATCH (s:Signal {event_id: $id}) RETURN s.corroboration_pending AS p",
                    Map.of("id", eventId.toString())).single().get("p").asBoolean();
        }
    }

    private long signalCount(UUID eventId) {
        try (Session session = neo4jDriver.session()) {
            return session.run("MATCH (s:Signal {event_id: $id}) RETURN count(s) AS n",
                    Map.of("id", eventId.toString())).single().get("n").asLong();
        }
    }

    private boolean aTransactionIsBlocked() {
        try (Session session = neo4jDriver.session()) {
            return session.run("SHOW TRANSACTIONS YIELD status RETURN status").list().stream()
                    .anyMatch(r -> r.get("status").asString().startsWith("Blocked"));
        }
    }
}
