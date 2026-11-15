package dev.auspex.corehub.corroboration;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Comparator;
import java.util.List;
import java.util.stream.Collectors;

/**
 * One episode of a scope: opened at the publication of the signal that completed its first
 * independent pair, with every signal that joined it, in replay order.
 */
public record Episode(Instant openedAt, List<CorroborationSignal> participants) {
    public Episode {
        participants = List.copyOf(participants);
    }

    /** The latest participant's publication. */
    public Instant corroboratedAt() {
        return participants.stream().map(CorroborationSignal::publishedDate)
                .max(Comparator.naturalOrder()).orElseThrow();
    }

    /** Participant event ids, sorted as text. */
    public List<String> sortedEventIds() {
        return participants.stream().map(CorroborationSignal::eventId).sorted().toList();
    }

    /** SHA-256 of the sorted participant event ids joined by colons. */
    public String participantsHash() {
        return EntityRules.sha256(String.join(":", sortedEventIds()).getBytes(StandardCharsets.UTF_8));
    }

    /** The participants' distinct source types, sorted. */
    public List<String> sourceTypes() {
        return participants.stream().map(CorroborationSignal::sourceType).distinct().sorted()
                .collect(Collectors.toList());
    }
}
