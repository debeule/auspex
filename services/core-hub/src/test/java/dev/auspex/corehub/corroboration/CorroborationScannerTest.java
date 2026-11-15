package dev.auspex.corehub.corroboration;

import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.mockito.InOrder;
import org.neo4j.driver.Driver;
import org.neo4j.driver.Result;
import org.neo4j.driver.Session;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.TransactionStatus;
import org.springframework.transaction.support.SimpleTransactionStatus;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyMap;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.spy;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class CorroborationScannerTest {

    private static final Clock CLOCK = Clock.fixed(Instant.parse("2024-06-15T12:00:00Z"), ZoneOffset.UTC);

    private static final class RecordingTransactionManager implements PlatformTransactionManager {
        @Override
        public TransactionStatus getTransaction(TransactionDefinition definition) {
            return new SimpleTransactionStatus();
        }

        @Override
        public void commit(TransactionStatus status) {}

        @Override
        public void rollback(TransactionStatus status) {}
    }

    private static CorroborationScanner scanner(CorroborationFakes.Graph graph) {
        EntityRules rules = EpisodeCases.rules();
        CorroborationFakes.Store store = new CorroborationFakes.Store();
        store.appliedHash = rules.hash();
        return new CorroborationScanner(new CorroborationReconciler(graph, store, () -> rules, 500, 500), graph, CLOCK);
    }

    /** Two entities, each with an independent pair: two records to send. */
    private static CorroborationFakes.Graph twoCorroborations() {
        CorroborationFakes.Graph graph = new CorroborationFakes.Graph();
        graph.add(1, "biorxiv", "2024-01-01", "GeneTarget", "BCL11A");
        graph.add(2, "edgar", "2024-01-10", "GeneTarget", "BCL11A");
        graph.add(3, "biorxiv", "2024-02-01", "GeneTarget", "HBB");
        graph.add(4, "clinicaltrials", "2024-02-10", "GeneTarget", "HBB");
        return graph;
    }

    @SuppressWarnings("unchecked")
    @Test
    void pendingFlagIsClearedOnlyAfterEverySendIsAcknowledged() {
        CorroborationFakes.Graph failingGraph = twoCorroborations();
        CorroborationScanner failingScanner = spy(scanner(failingGraph));
        KafkaTemplate<Object, Object> failing = mock(KafkaTemplate.class);
        when(failing.send(any(), any(), any()))
                .thenReturn(CompletableFuture.completedFuture(null))
                .thenReturn(CompletableFuture.failedFuture(new IllegalStateException("broker unavailable")));
        ScheduledCorroborationService failingRun = new ScheduledCorroborationService(
                failingScanner, failing, new RecordingTransactionManager(), 1000L, new SimpleMeterRegistry());

        assertThatThrownBy(failingRun::runCorroboration).isInstanceOf(IllegalStateException.class);
        verify(failingScanner, times(0)).clearPending(any());
        assertThat(failingGraph.pending).hasSize(4);

        CorroborationFakes.Graph graph = twoCorroborations();
        CorroborationScanner spied = spy(scanner(graph));
        KafkaTemplate<Object, Object> kafka = mock(KafkaTemplate.class);
        when(kafka.send(any(), any(), any())).thenReturn(CompletableFuture.completedFuture(null));
        new ScheduledCorroborationService(spied, kafka, new RecordingTransactionManager(), 1000L,
                new SimpleMeterRegistry()).runCorroboration();

        InOrder order = inOrder(kafka, spied);
        order.verify(kafka, times(2)).send(any(), any(), any());
        order.verify(spied).clearPending(any());
        assertThat(graph.pending).isEmpty();
    }

    @SuppressWarnings("unchecked")
    @Test
    void clearUsesTheWriteTokenTheScanRead() {
        UUID a = UUID.randomUUID();
        UUID b = UUID.randomUUID();
        List<CorroborationScanner.PendingSignal> read = List.of(
                new CorroborationScanner.PendingSignal(a, "token-a"), new CorroborationScanner.PendingSignal(b, "token-b"));
        Driver driver = mock(Driver.class);
        Session session = mock(Session.class);
        when(driver.session()).thenReturn(session);
        when(session.run(anyString(), anyMap())).thenReturn(mock(Result.class));

        new Neo4jCorroborationGraph(driver).clearPending(read);

        ArgumentCaptor<String> query = ArgumentCaptor.forClass(String.class);
        ArgumentCaptor<Map<String, Object>> params = ArgumentCaptor.forClass(Map.class);
        verify(session).run(query.capture(), params.capture());
        assertThat(query.getValue())
                .contains("s.write_token = read.writeToken")
                .contains("SET s.corroboration_pending = false");
        assertThat((List<Map<String, Object>>) params.getValue().get("signals")).containsExactly(
                Map.of("eventId", a.toString(), "writeToken", "token-a"),
                Map.of("eventId", b.toString(), "writeToken", "token-b"));
    }

    @Test
    void signalRewrittenAfterTheScanReadItStaysPending() {
        CorroborationFakes.Graph graph = twoCorroborations();
        CorroborationScanner scanner = scanner(graph);

        CorroborationScanner.ScanResult scan = scanner.scan();
        graph.markPending(List.of(CorroborationFakes.id(1)));
        scanner.clearPending(scan.handled());

        assertThat(graph.pending).containsExactly(CorroborationFakes.id(1));
    }

    @Test
    void scanReturnsNothingWhenNoSignalIsPending() {
        CorroborationFakes.Graph graph = new CorroborationFakes.Graph();

        CorroborationScanner.ScanResult result = scanner(graph).scan();

        assertThat(result.events()).isEmpty();
        assertThat(result.handled()).isEmpty();
    }

    @Test
    void scanUsesTheServiceClock() {
        CorroborationFakes.Graph graph = twoCorroborations();

        CorroborationScanner.ScanResult result = scanner(graph).scan();

        assertThat(graph.calls).contains("readPending " + CLOCK.instant());
        assertThat(result.events()).allSatisfy(e -> assertThat(e.firstDetectedAt()).isEqualTo(CLOCK.instant()));
    }
}
