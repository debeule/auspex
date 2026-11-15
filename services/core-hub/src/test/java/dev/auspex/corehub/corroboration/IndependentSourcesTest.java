package dev.auspex.corehub.corroboration;

import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

class IndependentSourcesTest {

    private static final Instant T = Instant.parse("2024-01-01T00:00:00Z");
    private static final String PREPRINT = "CRISPR base editing restores HBB expression in mice";
    private static final String PAPER = "CRISPR Base-Editing Restores HBB Expression in Mice.";

    private final IndependentSources sources = new IndependentSources(
            new EntityRules.SameFinding(Set.of(Set.of("biorxiv", "pubmed")), 0.8));

    private static CorroborationSignal s(String id, String sourceType, String title) {
        return new CorroborationSignal(id, sourceType, T, title);
    }

    @Test
    void twoSignalsOfOneSourceTypeCountAsOneSource() {
        assertThat(sources.count(List.of(s("a", "biorxiv", "one"), s("b", "biorxiv", "two")))).isEqualTo(1);
    }

    @Test
    void preprintAndItsPaperWithMatchingTitlesCountAsOneSource() {
        assertThat(sources.count(List.of(s("a", "biorxiv", PREPRINT), s("b", "pubmed", PAPER)))).isEqualTo(1);
    }

    @Test
    void preprintAndAnUnrelatedPaperCountAsTwoSources() {
        assertThat(sources.count(List.of(s("a", "biorxiv", PREPRINT),
                s("b", "pubmed", "Phase 2 outcomes of an HBB inducer in adults")))).isEqualTo(2);
    }

    @Test
    void secondUnrelatedPaperBesideAPreprintAndItsPaperRestoresTheSecondSource() {
        assertThat(sources.count(List.of(s("a", "biorxiv", PREPRINT), s("b", "pubmed", PAPER),
                s("c", "pubmed", "Phase 2 outcomes of an HBB inducer in adults")))).isEqualTo(2);
    }

    @Test
    void matchingTitlesAcrossAPairTheRulesDoNotListStayTwoSources() {
        assertThat(sources.count(List.of(s("a", "biorxiv", PREPRINT), s("b", "edgar", PAPER)))).isEqualTo(2);
    }

    @Test
    void signalWithoutATitleIsNeverTheSameFinding() {
        assertThat(sources.count(List.of(s("a", "biorxiv", null), s("b", "pubmed", PAPER)))).isEqualTo(2);
        assertThat(sources.count(List.of(s("a", "biorxiv", "  "), s("b", "pubmed", "--")))).isEqualTo(2);
    }

    @Test
    void titleOverlapJustBelowTheThresholdIsNotTheSameFinding() {
        // 4 of 5 tokens shared: Jaccard 0.8, the same finding; 3 of 4: 0.75, not.
        assertThat(sources.sameFinding(s("a", "biorxiv", "alpha beta gamma delta epsilon"),
                s("b", "pubmed", "alpha beta gamma delta"))).isTrue();
        assertThat(sources.sameFinding(s("a", "biorxiv", "alpha beta gamma delta"),
                s("b", "pubmed", "alpha beta gamma"))).isFalse();
        assertThat(sources.count(List.of(s("a", "biorxiv", "alpha beta gamma delta"),
                s("b", "pubmed", "alpha beta gamma")))).isEqualTo(2);
    }
}
