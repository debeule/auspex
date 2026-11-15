package dev.auspex.corehub.corroboration;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;

/** Reads {@code corroboration/episode-cases.json}, the case file the backtest's port reads too. */
final class EpisodeCases {

    static final Set<String> SOURCE_TYPES =
            Set.of("mock", "biorxiv", "clinicaltrials", "pubmed", "edgar", "epo_ops");

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private EpisodeCases() {}

    static JsonNode root() {
        try (InputStream in = EpisodeCases.class.getResourceAsStream("/corroboration/episode-cases.json")) {
            return MAPPER.readTree(in);
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }

    static EntityRules rules() {
        try {
            byte[] json = MAPPER.writeValueAsString(root().get("rules")).getBytes(StandardCharsets.UTF_8);
            return EntityRules.load(json, SOURCE_TYPES);
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }

    static List<CorroborationSignal> signals(JsonNode episodeCase) {
        List<CorroborationSignal> signals = new ArrayList<>();
        for (JsonNode s : episodeCase.get("signals")) {
            signals.add(new CorroborationSignal(
                    s.get("event_id").asText(),
                    s.get("source_type").asText(),
                    Instant.parse(s.get("published_date").asText()),
                    s.get("title").isNull() ? null : s.get("title").asText()));
        }
        return signals;
    }

    /** Each episode as "opened_at participants... count", for comparison with the expected list. */
    static List<String> expected(JsonNode episodeCase) {
        List<String> out = new ArrayList<>();
        for (JsonNode e : episodeCase.get("episodes")) {
            List<String> ids = new ArrayList<>();
            e.get("participants").forEach(p -> ids.add(p.asText()));
            out.add(e.get("episode_opened_at").asText() + " " + ids + " " + e.get("distinct_source_count").asInt());
        }
        return out;
    }

    static List<String> describe(EpisodeBuilder builder, List<Episode> episodes) {
        return episodes.stream()
                .map(e -> e.openedAt() + " " + e.sortedEventIds() + " " + builder.distinctSourceCount(e))
                .toList();
    }
}
