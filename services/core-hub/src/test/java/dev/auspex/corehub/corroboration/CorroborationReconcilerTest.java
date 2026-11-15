package dev.auspex.corehub.corroboration;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.neo4j.driver.Driver;
import org.neo4j.driver.Result;
import org.neo4j.driver.Session;

import java.time.Instant;
import java.util.List;
import java.util.Map;

import static dev.auspex.corehub.corroboration.CorroborationFakes.id;
import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyMap;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class CorroborationReconcilerTest {

    private static final Instant NOW = Instant.parse("2024-06-15T12:00:00Z");

    private final EntityRules rules = EpisodeCases.rules();
    private CorroborationFakes.Graph graph;
    private CorroborationFakes.Store store;
    private CorroborationReconciler reconciler;

    @BeforeEach
    void setUp() {
        graph = new CorroborationFakes.Graph();
        store = new CorroborationFakes.Store();
        store.appliedHash = rules.hash();
        reconciler = new CorroborationReconciler(graph, store, () -> rules, 500, 500);
    }

    private CorroborationScanner.ScanResult scan(Instant now) {
        CorroborationScanner.ScanResult result = reconciler.scan(now);
        graph.clearPending(result.handled());
        return result;
    }

    @Test
    void excludedEntityRecordIsWrittenWithItsReasonAndNotSent() {
        graph.add(1, "biorxiv", "2024-01-01", "Mechanism", "Gene Therapy");
        graph.add(2, "edgar", "2024-01-10", "Mechanism", "gene-therapy");

        CorroborationScanner.ScanResult result = scan(NOW);

        assertThat(result.events()).isEmpty();
        assertThat(store.live()).singleElement().satisfies(row -> {
            assertThat(row.entityKey()).isEqualTo("gene therapy:Mechanism");
            assertThat(row.excludedReason()).isEqualTo("broad_entity");
            assertThat(row.publishedAt()).isNull();
            assertThat(row.participantEventIds()).hasSize(2);
        });
    }

    @Test
    void excludedEntityProducesNoTickerRecord() {
        graph.add(1, "biorxiv", "2024-01-01", "Mechanism", "gene therapy", "SRPT");
        graph.add(2, "edgar", "2024-01-10", "Mechanism", "gene therapy", "SRPT");

        scan(NOW);

        assertThat(store.rows).extracting(CorroborationRow::ticker).containsExactly("");
    }

    @Test
    void tickerRecordNeedsTwoIndependentSourcesNamingThatTicker() {
        graph.add(1, "biorxiv", "2024-01-01", "GeneTarget", "BCL11A", "BEAM", "CRSP");
        graph.add(2, "edgar", "2024-01-10", "GeneTarget", "BCL11A");
        graph.add(3, "clinicaltrials", "2024-02-01", "GeneTarget", "bcl-11a", "BEAM");

        CorroborationScanner.ScanResult result = scan(NOW);

        assertThat(store.live()).extracting(CorroborationRow::ticker).containsExactlyInAnyOrder("", "BEAM");
        CorroborationRow beam = store.live().stream().filter(r -> r.ticker().equals("BEAM")).findFirst().orElseThrow();
        assertThat(beam.episodeOpenedAt()).isEqualTo(Instant.parse("2024-02-01T00:00:00Z"));
        assertThat(beam.participantEventIds()).extracting(Object::toString).containsExactly(id(1), id(3));
        CorroborationRow entity = store.live().stream().filter(r -> r.ticker().isEmpty()).findFirst().orElseThrow();
        assertThat(entity.episodeOpenedAt()).isEqualTo(Instant.parse("2024-01-10T00:00:00Z"));
        assertThat(result.events()).extracting(CorroboratedSignalEvent::ticker).containsExactlyInAnyOrder("", "BEAM");
        assertThat(result.events()).filteredOn(e -> e.ticker().equals("BEAM")).singleElement()
                .satisfies(e -> assertThat(e.sourceTypes()).containsExactly("biorxiv", "clinicaltrials"));
    }

    @Test
    void tickerRecordWithTheEntityRecordsParticipantsIsARecordOfItsOwn() {
        graph.add(1, "biorxiv", "2024-01-01", "GeneTarget", "BCL11A");
        graph.add(2, "edgar", "2024-01-10", "GeneTarget", "BCL11A");
        assertThat(scan(NOW).events()).extracting(CorroboratedSignalEvent::ticker).containsExactly("");

        // The company both signals name resolves to a ticker later; the participants are the same.
        graph.add(1, "biorxiv", "2024-01-01", "GeneTarget", "BCL11A", "BEAM");
        graph.add(2, "edgar", "2024-01-10", "GeneTarget", "BCL11A", "BEAM");
        CorroborationScanner.ScanResult later = scan(NOW.plusSeconds(60));

        assertThat(later.events()).extracting(CorroboratedSignalEvent::ticker).containsExactly("BEAM");
        assertThat(store.live()).extracting(CorroborationRow::ticker).containsExactlyInAnyOrder("", "BEAM");
        assertThat(store.live()).extracting(CorroborationRow::participantsHash).hasSize(2).containsOnly(
                store.live().getFirst().participantsHash());
    }

    @Test
    void recordAlreadyPublishedIsNotSentAgain() {
        graph.add(1, "biorxiv", "2024-01-01", "GeneTarget", "BCL11A");
        graph.add(2, "edgar", "2024-01-10", "GeneTarget", "BCL11A");
        assertThat(scan(NOW).events()).hasSize(1);
        assertThat(store.live().getFirst().publishedAt()).isEqualTo(NOW);

        graph.markPending(List.of(id(1), id(2)));
        CorroborationScanner.ScanResult again = scan(NOW.plusSeconds(60));

        assertThat(again.events()).isEmpty();
        assertThat(again.handled()).hasSize(2);
        assertThat(store.rows).hasSize(1);
        assertThat(store.live().getFirst().publishedAt()).isEqualTo(NOW);
    }

    @SuppressWarnings("unchecked")
    @Test
    void scanReadsOnlyPendingSignalsPublishedByNow() {
        graph.add(1, "biorxiv", "2024-06-01", "GeneTarget", "BCL11A");
        graph.add(2, "edgar", "2024-07-01", "GeneTarget", "BCL11A");

        CorroborationScanner.ScanResult early = scan(NOW);
        assertThat(early.handled()).extracting(p -> p.eventId().toString()).containsExactly(id(1));
        assertThat(store.rows).isEmpty();
        assertThat(graph.pending).containsExactly(id(2));
        assertThat(graph.calls).contains("readPending " + NOW, "eligibleSignals " + NOW);

        Instant later = Instant.parse("2024-07-02T00:00:00Z");
        assertThat(scan(later).events()).singleElement()
                .satisfies(e -> assertThat(e.corroboratedAt()).isEqualTo(Instant.parse("2024-07-01T00:00:00Z")));

        Driver driver = mock(Driver.class);
        Session session = mock(Session.class);
        Result result = mock(Result.class);
        when(driver.session()).thenReturn(session);
        when(session.run(anyString(), anyMap())).thenReturn(result);
        when(result.list(any())).thenReturn(List.of());
        new Neo4jCorroborationGraph(driver).readPending(NOW, 500);
        ArgumentCaptor<String> query = ArgumentCaptor.forClass(String.class);
        ArgumentCaptor<Map<String, Object>> params = ArgumentCaptor.forClass(Map.class);
        verify(session).run(query.capture(), params.capture());
        assertThat(query.getValue())
                .contains("s.corroboration_pending = true")
                .contains("s.published_date <= datetime($now)")
                .contains("LIMIT $batchSize")
                .doesNotContain("ingested_at");
        assertThat(params.getValue()).containsEntry("now", NOW.toString()).containsEntry("batchSize", 500);
    }

    @Test
    void scanDoesNothingWhileTheAppliedRulesHashDiffersFromTheFile() {
        graph.add(1, "biorxiv", "2024-01-01", "GeneTarget", "BCL11A");
        graph.add(2, "edgar", "2024-01-10", "GeneTarget", "BCL11A");
        store.appliedHash = "a hash of other rules";

        CorroborationScanner.ScanResult result = scan(NOW);

        assertThat(result.events()).isEmpty();
        assertThat(result.handled()).isEmpty();
        assertThat(graph.calls).isEmpty();
        assertThat(graph.pending).hasSize(2);
        assertThat(store.rows).isEmpty();

        store.appliedHash = null;
        assertThat(scan(NOW).handled()).isEmpty();
    }
}
