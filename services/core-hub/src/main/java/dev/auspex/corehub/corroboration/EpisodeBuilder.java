package dev.auspex.corehub.corroboration;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Comparator;
import java.util.List;

/**
 * Builds the episodes of one scope from its signals. A pure function of the signals' publication
 * dates, source types and titles: arrival order never changes the result.
 *
 * <p>Signals are replayed in {@code (published_date, event_id)} order. A signal published no later
 * than the window after an open episode's opening joins it. Otherwise the open episode closes,
 * candidates published more than the window before the signal are dropped, and the signal becomes
 * a candidate; when the candidates hold two independent participants they open an episode at this
 * signal's publication, and the candidate list is emptied. So every participant lies within the
 * window of the opening signal, and an episode accepts joiners for one window and then closes.
 * The window is in {@code backtesting}'s port too and in the shared case file.
 */
public final class EpisodeBuilder {

    /** 90 days, both ends included, between two publication dates. */
    public static final Duration WINDOW = Duration.ofDays(90);

    private static final Comparator<CorroborationSignal> REPLAY_ORDER =
            Comparator.comparing(CorroborationSignal::publishedDate).thenComparing(CorroborationSignal::eventId);

    private final IndependentSources independence;

    public EpisodeBuilder(IndependentSources independence) {
        this.independence = independence;
    }

    public List<Episode> build(Collection<CorroborationSignal> signals) {
        List<CorroborationSignal> ordered = new ArrayList<>(signals);
        ordered.sort(REPLAY_ORDER);

        List<Episode> episodes = new ArrayList<>();
        Instant openedAt = null;
        List<CorroborationSignal> open = new ArrayList<>();
        List<CorroborationSignal> candidates = new ArrayList<>();
        for (CorroborationSignal signal : ordered) {
            if (openedAt != null && !signal.publishedDate().isAfter(openedAt.plus(WINDOW))) {
                open.add(signal);
                continue;
            }
            if (openedAt != null) {
                episodes.add(new Episode(openedAt, open));
                openedAt = null;
                open = new ArrayList<>();
            }
            Instant oldest = signal.publishedDate().minus(WINDOW);
            candidates.removeIf(c -> c.publishedDate().isBefore(oldest));
            candidates.add(signal);
            if (independence.count(candidates) >= 2) {
                openedAt = signal.publishedDate();
                open = new ArrayList<>(candidates);
                candidates.clear();
            }
        }
        if (openedAt != null) {
            episodes.add(new Episode(openedAt, open));
        }
        return episodes;
    }

    public int distinctSourceCount(Episode episode) {
        return independence.count(episode.participants());
    }
}
