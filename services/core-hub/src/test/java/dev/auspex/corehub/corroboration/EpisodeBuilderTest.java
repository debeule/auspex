package dev.auspex.corehub.corroboration;

import com.fasterxml.jackson.databind.JsonNode;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Random;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

class EpisodeBuilderTest {

    private final EpisodeBuilder builder = new EpisodeBuilder(new IndependentSources(
            new EntityRules.SameFinding(Set.of(Set.of("biorxiv", "pubmed")), 0.8)));

    private static CorroborationSignal s(String id, String sourceType, String date) {
        return new CorroborationSignal(id, sourceType, Instant.parse(date + "T00:00:00Z"), null);
    }

    private List<String> describe(List<CorroborationSignal> signals) {
        return EpisodeCases.describe(builder, builder.build(signals));
    }

    @Test
    void everySharedEpisodeCaseProducesItsExpectedEpisodes() {
        EpisodeBuilder shared = new EpisodeBuilder(new IndependentSources(EpisodeCases.rules().sameFinding()));
        JsonNode cases = EpisodeCases.root().get("episode_cases");
        assertThat(cases.size()).isPositive();

        for (JsonNode c : cases) {
            assertThat(EpisodeCases.describe(shared, shared.build(EpisodeCases.signals(c))))
                    .as(c.get("name").asText())
                    .isEqualTo(EpisodeCases.expected(c));
        }
    }

    @Test
    void signalWithinTheWindowAfterTheOpeningJoinsTheEpisode() {
        assertThat(describe(List.of(s("a", "biorxiv", "2024-01-01"), s("b", "edgar", "2024-01-10"),
                s("c", "biorxiv", "2024-02-01"))))
                .containsExactly("2024-01-10T00:00:00Z [a, b, c] 2");
    }

    @Test
    void signalExactlyOneWindowAfterTheOpeningStillJoins() {
        // 2024-01-10 plus 90 days is 2024-04-09.
        assertThat(describe(List.of(s("a", "biorxiv", "2024-01-01"), s("b", "edgar", "2024-01-10"),
                s("c", "clinicaltrials", "2024-04-09"))))
                .containsExactly("2024-01-10T00:00:00Z [a, b, c] 3");
    }

    @Test
    void signalAfterTheWindowOpensNothingWithoutTwoFreshSources() {
        List<CorroborationSignal> signals = new ArrayList<>(List.of(s("a", "biorxiv", "2024-01-01"),
                s("b", "edgar", "2024-01-10"), s("c", "clinicaltrials", "2024-04-10"),
                s("d", "clinicaltrials", "2024-04-20")));
        assertThat(describe(signals)).containsExactly("2024-01-10T00:00:00Z [a, b] 2");

        signals.add(s("e", "edgar", "2024-04-25"));
        assertThat(describe(signals)).containsExactly(
                "2024-01-10T00:00:00Z [a, b] 2", "2024-04-25T00:00:00Z [c, d, e] 2");
    }

    @Test
    void everySignalBelongsToAtMostOneEpisode() {
        List<CorroborationSignal> signals = new ArrayList<>();
        String[] types = {"biorxiv", "edgar", "clinicaltrials", "pubmed"};
        Instant start = Instant.parse("2023-01-01T00:00:00Z");
        Random random = new Random(7);
        for (int i = 0; i < 200; i++) {
            signals.add(new CorroborationSignal("s" + i, types[random.nextInt(types.length)],
                    start.plusSeconds(86_400L * random.nextInt(700)), null));
        }

        List<Episode> episodes = builder.build(signals);

        Set<String> seen = new HashSet<>();
        assertThat(episodes).hasSizeGreaterThan(1);
        for (Episode episode : episodes) {
            for (CorroborationSignal p : episode.participants()) {
                assertThat(seen.add(p.eventId())).as(p.eventId()).isTrue();
                assertThat(p.publishedDate()).isBetween(episode.openedAt().minus(EpisodeBuilder.WINDOW),
                        episode.openedAt().plus(EpisodeBuilder.WINDOW));
            }
        }
    }

    @Test
    void candidateOlderThanTheWindowIsDroppedBeforeAnOpening() {
        assertThat(describe(List.of(s("a", "biorxiv", "2024-01-01"), s("b", "biorxiv", "2024-03-01"),
                s("c", "edgar", "2024-05-15"))))
                .containsExactly("2024-05-15T00:00:00Z [b, c] 2");
        assertThat(describe(List.of(s("a", "biorxiv", "2024-01-01"), s("c", "edgar", "2024-04-02"))))
                .isEmpty();
    }

    @Test
    void openingTimeIsThePublicationOfTheSignalThatCompletedTheFirstIndependentPair() {
        List<Episode> episodes = builder.build(List.of(s("a", "edgar", "2024-01-01"),
                s("b", "edgar", "2024-01-05"), s("c", "biorxiv", "2024-02-01"), s("d", "pubmed", "2024-02-20")));

        assertThat(episodes).hasSize(1);
        assertThat(episodes.getFirst().openedAt()).isEqualTo(Instant.parse("2024-02-01T00:00:00Z"));
        assertThat(episodes.getFirst().corroboratedAt()).isEqualTo(Instant.parse("2024-02-20T00:00:00Z"));
    }

    @Test
    void arrivalOrderDoesNotChangeTheEpisodes() {
        List<CorroborationSignal> signals = new ArrayList<>(List.of(s("a", "biorxiv", "2024-01-01"),
                s("b", "edgar", "2024-01-10"), s("c", "clinicaltrials", "2024-04-09"),
                s("d", "edgar", "2024-04-10"), s("e", "biorxiv", "2024-05-01"), s("f", "pubmed", "2024-05-01")));
        List<String> expected = describe(signals);

        Random random = new Random(11);
        for (int i = 0; i < 20; i++) {
            Collections.shuffle(signals, random);
            assertThat(describe(signals)).isEqualTo(expected);
        }
        // A late-arriving earlier signal moves the opening earlier.
        List<CorroborationSignal> withoutA = signals.stream().filter(x -> !x.eventId().equals("a")).toList();
        assertThat(describe(withoutA).getFirst()).startsWith("2024-04-09");
        assertThat(expected.getFirst()).startsWith("2024-01-10");
    }
}
