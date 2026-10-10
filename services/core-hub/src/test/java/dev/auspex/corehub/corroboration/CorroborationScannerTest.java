package dev.auspex.corehub.corroboration;

import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.mockito.InOrder;
import org.neo4j.driver.Driver;
import org.neo4j.driver.Result;
import org.neo4j.driver.Session;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.PreparedStatementCreator;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.TransactionStatus;
import org.springframework.transaction.support.SimpleTransactionStatus;

import java.time.Instant;
import java.time.temporal.TemporalAccessor;
import java.util.ArrayList;
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
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

class CorroborationScannerTest {

    private static final Instant NOW = Instant.parse("2024-06-15T12:00:00Z");
    private static final int BATCH_SIZE = 500;

    /** A scanner whose graph reads are stubbed; the clears it would send are recorded. */
    private static class StubScanner extends CorroborationScanner {
        private final List<PendingSignal> pending;
        private final List<EntityGroup> groups;
        final List<List<PendingSignal>> clears = new ArrayList<>();

        StubScanner(JdbcTemplate jdbc, List<PendingSignal> pending, List<EntityGroup> groups) {
            super(mock(Driver.class), jdbc, s -> s, BATCH_SIZE);
            this.pending = pending;
            this.groups = groups;
        }

        @Override
        protected List<PendingSignal> readPending() { return pending; }

        @Override
        protected List<EntityGroup> findGroups(List<UUID> triggerIds) { return groups; }

        @Override
        public void clearPending(List<PendingSignal> handled) { clears.add(List.copyOf(handled)); }
    }

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

    private static CorroborationScanner.PendingSignal pending(UUID eventId) {
        return new CorroborationScanner.PendingSignal(eventId, UUID.randomUUID().toString());
    }

    private static CorroborationScanner.EntityGroup group(UUID trigger, String triggerSource, String entity,
                                                          UUID partner, String partnerSource) {
        return new CorroborationScanner.EntityGroup(
                trigger, triggerSource, NOW.minusSeconds(3600), entity, "GeneTarget",
                List.of(new CorroborationScanner.Partner(partner, partnerSource, NOW.minusSeconds(7200))));
    }

    @SuppressWarnings("unchecked")
    @Test
    void scanReadsPendingSignalsAsTriggers() {
        Driver driver = mock(Driver.class);
        Session session = mock(Session.class);
        Result result = mock(Result.class);
        when(driver.session()).thenReturn(session);
        when(session.run(anyString(), anyMap())).thenReturn(result);
        when(result.list(any())).thenReturn(List.of());
        JdbcTemplate jdbc = mock(JdbcTemplate.class);

        CorroborationScanner.ScanResult scan =
                new CorroborationScanner(driver, jdbc, s -> s, BATCH_SIZE).scan();

        ArgumentCaptor<String> query = ArgumentCaptor.forClass(String.class);
        ArgumentCaptor<Map<String, Object>> params = ArgumentCaptor.forClass(Map.class);
        verify(session).run(query.capture(), params.capture());
        assertThat(query.getValue())
                .contains("s.corroboration_pending = true")
                .contains("s.write_token")
                .contains("LIMIT $batchSize")
                .doesNotContain("ingested_at");
        assertThat(params.getValue()).containsExactly(Map.entry("batchSize", BATCH_SIZE));
        assertThat(params.getValue().values()).noneMatch(v -> v instanceof TemporalAccessor);
        assertThat(scan.events()).isEmpty();
        assertThat(scan.handled()).isEmpty();
        verifyNoInteractions(jdbc);
    }

    @SuppressWarnings("unchecked")
    @Test
    void pendingFlagIsClearedOnlyAfterEverySendIsAcknowledged() {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        when(jdbc.update(any(PreparedStatementCreator.class))).thenReturn(1);
        UUID a = UUID.randomUUID();
        UUID b = UUID.randomUUID();
        UUID c = UUID.randomUUID();
        List<CorroborationScanner.PendingSignal> read = List.of(pending(a), pending(b), pending(c));
        StubScanner scanner = new StubScanner(jdbc, read, List.of(
                group(a, "biorxiv", "BCL11A", c, "sec_edgar"),
                group(b, "biorxiv", "HBB", c, "clinicaltrials")));

        KafkaTemplate<Object, Object> failing = mock(KafkaTemplate.class);
        when(failing.send(any(), any(), any()))
                .thenReturn(CompletableFuture.completedFuture(null))
                .thenReturn(CompletableFuture.failedFuture(new IllegalStateException("broker unavailable")));
        ScheduledCorroborationService failingRun = new ScheduledCorroborationService(
                scanner, failing, new RecordingTransactionManager(), 1000L, new SimpleMeterRegistry());

        assertThatThrownBy(failingRun::runCorroboration).isInstanceOf(IllegalStateException.class);
        assertThat(scanner.clears).isEmpty();

        KafkaTemplate<Object, Object> kafka = mock(KafkaTemplate.class);
        when(kafka.send(any(), any(), any())).thenReturn(CompletableFuture.completedFuture(null));
        StubScanner spied = spy(new StubScanner(jdbc, read, List.of(
                group(a, "biorxiv", "BCL11A", c, "sec_edgar"),
                group(b, "biorxiv", "HBB", c, "clinicaltrials"))));
        new ScheduledCorroborationService(
                spied, kafka, new RecordingTransactionManager(), 1000L, new SimpleMeterRegistry())
                .runCorroboration();

        InOrder order = inOrder(kafka, spied);
        order.verify(kafka, times(2)).send(any(), any(), any());
        order.verify(spied).clearPending(read);
    }

    @SuppressWarnings("unchecked")
    @Test
    void clearUsesTheWriteTokenTheScanRead() {
        UUID a = UUID.randomUUID();
        UUID b = UUID.randomUUID();
        List<CorroborationScanner.PendingSignal> read = List.of(pending(a), pending(b));
        Driver driver = mock(Driver.class);
        Session session = mock(Session.class);
        when(driver.session()).thenReturn(session);
        when(session.run(anyString(), anyMap())).thenReturn(mock(Result.class));
        CorroborationScanner scanner = new CorroborationScanner(driver, mock(JdbcTemplate.class), s -> s, BATCH_SIZE) {
            @Override
            protected List<PendingSignal> readPending() { return read; }

            @Override
            protected List<EntityGroup> findGroups(List<UUID> triggerIds) { return List.of(); }
        };

        scanner.clearPending(scanner.scan().handled());

        ArgumentCaptor<String> query = ArgumentCaptor.forClass(String.class);
        ArgumentCaptor<Map<String, Object>> params = ArgumentCaptor.forClass(Map.class);
        verify(session).run(query.capture(), params.capture());
        assertThat(query.getValue())
                .contains("s.write_token = read.writeToken")
                .contains("SET s.corroboration_pending = false");
        assertThat((List<Map<String, Object>>) params.getValue().get("signals")).containsExactly(
                Map.of("eventId", a.toString(), "writeToken", read.get(0).writeToken()),
                Map.of("eventId", b.toString(), "writeToken", read.get(1).writeToken()));
    }

    @Test
    void groupScannedTwiceIsNotRepublished() {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        // Each group runs a supersede update, then the insert: the second scan's insert conflicts.
        when(jdbc.update(any(PreparedStatementCreator.class))).thenReturn(0, 1, 0, 0);
        UUID a = UUID.randomUUID();
        UUID b = UUID.randomUUID();
        StubScanner scanner = new StubScanner(jdbc, List.of(pending(a)),
                List.of(group(a, "biorxiv", "BCL11A", b, "sec_edgar")));

        assertThat(scanner.scan().events()).hasSize(1);

        CorroborationScanner.ScanResult second = scanner.scan();
        assertThat(second.events()).isEmpty();
        assertThat(second.handled()).extracting(CorroborationScanner.PendingSignal::eventId).containsExactly(a);
    }

    @Test
    void scanReturnsNothingWhenNoSignalIsPending() {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        StubScanner scanner = new StubScanner(jdbc, List.of(), List.of());

        CorroborationScanner.ScanResult result = scanner.scan();

        assertThat(result.events()).isEmpty();
        assertThat(result.handled()).isEmpty();
        verifyNoInteractions(jdbc);
    }

    @Test
    void scanDoesNotPublishGroupWithSingleSourceType() {
        UUID a = UUID.randomUUID();
        StubScanner scanner = new StubScanner(mock(JdbcTemplate.class), List.of(pending(a)),
                List.of(group(a, "biorxiv", "BCL11A", UUID.randomUUID(), "biorxiv")));

        CorroborationScanner.ScanResult result = scanner.scan();

        assertThat(result.events()).isEmpty();
        assertThat(result.handled()).extracting(CorroborationScanner.PendingSignal::eventId).containsExactly(a);
    }

    @Test
    void scanReturnsEventForQualifyingGroup() {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        when(jdbc.update(any(PreparedStatementCreator.class))).thenReturn(1);
        UUID triggerId = UUID.randomUUID();
        UUID partnerId = UUID.randomUUID();
        StubScanner scanner = new StubScanner(jdbc, List.of(pending(triggerId)),
                List.of(group(triggerId, "biorxiv", "BCL11A", partnerId, "clinicaltrials")));

        List<CorroboratedSignalEvent> result = scanner.scan().events();

        assertThat(result).hasSize(1);
        CorroboratedSignalEvent event = result.getFirst();
        assertThat(event.entityKey()).isEqualTo("BCL11A:GeneTarget");
        assertThat(event.participantEventIds()).containsExactlyInAnyOrder(triggerId, partnerId);
        assertThat(event.distinctSourceCount()).isEqualTo(2);
    }
}
