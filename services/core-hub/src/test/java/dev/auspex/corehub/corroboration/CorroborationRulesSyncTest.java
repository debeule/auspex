package dev.auspex.corehub.corroboration;

import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;

import static org.assertj.core.api.Assertions.assertThat;

class CorroborationRulesSyncTest {

    private static final Clock CLOCK = Clock.fixed(Instant.parse("2024-06-15T12:00:00Z"), ZoneOffset.UTC);

    private final EntityRules rules = EpisodeCases.rules();

    @Test
    void syncDoesNothingWhenTheAppliedHashMatches() {
        CorroborationFakes.Graph graph = new CorroborationFakes.Graph();
        graph.add(1, "biorxiv", "2024-01-01", "Mechanism", "Genome Editing");
        graph.pending.clear();
        CorroborationFakes.Store store = new CorroborationFakes.Store();
        store.appliedHash = rules.hash();

        new CorroborationRulesSync(rules, graph, store, CLOCK, 2).syncFileRules();

        assertThat(graph.calls).isEmpty();
        assertThat(store.calls).isEmpty();
        assertThat(graph.pending).isEmpty();
    }

    @Test
    void syncKeysEntitiesThenMarksSignalsPendingThenStoresTheHash() {
        CorroborationFakes.Graph graph = new CorroborationFakes.Graph();
        graph.add(1, "biorxiv", "2024-01-01", "Mechanism", "Genome Editing");
        graph.add(2, "edgar", "2024-01-02", "Mechanism", "gene editing");
        graph.add(3, "edgar", "2024-01-03", "GeneTarget", "il-2");
        graph.add(4, "pubmed", "2024-01-04", "GeneTarget", "IL2");
        graph.add(5, "pubmed", "2024-01-05", "GeneTarget", "IL2");
        graph.pending.clear();
        CorroborationFakes.Store store = new CorroborationFakes.Store(graph.calls);
        store.appliedHash = "a hash of earlier rules";
        CorroborationRulesSync sync = new CorroborationRulesSync(rules, graph, store, CLOCK, 2);

        sync.syncFileRules();

        assertThat(graph.calls).containsExactly(
                "allEntities", "setKeys 2", "setKeys 2",
                "allSignalIds", "markPending 2", "markPending 2", "markPending 1",
                "storeAppliedRulesHash");
        assertThat(graph.keys.values()).containsExactlyInAnyOrder("gene editing", "gene editing", "IL2", "IL2");
        assertThat(graph.pending).hasSize(5);
        assertThat(store.appliedHash).isEqualTo(rules.hash());
        assertThat(sync.rulesInForce()).isSameAs(rules);
    }
}
