package dev.auspex.corehub.corroboration;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.HashSet;

/**
 * Counts independent sources. Two participants are the same finding when their source types form
 * a pair the rules list, both have a title, and their title token sets overlap (Jaccard) at least
 * the rules' threshold; they are independent when their source types differ and they are not the
 * same finding. The count is the largest set of participants that are pairwise independent.
 */
public final class IndependentSources {

    private final EntityRules.SameFinding sameFinding;

    public IndependentSources(EntityRules.SameFinding sameFinding) {
        this.sameFinding = sameFinding;
    }

    public boolean sameFinding(CorroborationSignal a, CorroborationSignal b) {
        if (!sameFinding.listsPair(a.sourceType(), b.sourceType())) {
            return false;
        }
        Set<String> ta = titleTokens(a.title());
        Set<String> tb = titleTokens(b.title());
        if (ta.isEmpty() || tb.isEmpty()) {
            return false;
        }
        Set<String> union = new HashSet<>(ta);
        union.addAll(tb);
        Set<String> common = new HashSet<>(ta);
        common.retainAll(tb);
        return (double) common.size() / union.size() >= sameFinding.titleTokenJaccardMin();
    }

    public boolean independent(CorroborationSignal a, CorroborationSignal b) {
        return !a.sourceType().equals(b.sourceType()) && !sameFinding(a, b);
    }

    /** The largest number of participants that can be chosen so that every two are independent. */
    public int count(List<CorroborationSignal> participants) {
        // At most one participant per source type can be chosen, so search over source types.
        Map<String, List<CorroborationSignal>> byType = new LinkedHashMap<>();
        for (CorroborationSignal s : participants) {
            byType.computeIfAbsent(s.sourceType(), k -> new ArrayList<>()).add(s);
        }
        return best(new ArrayList<>(byType.values()), 0, new ArrayList<>());
    }

    private int best(List<List<CorroborationSignal>> types, int index, List<CorroborationSignal> chosen) {
        if (index == types.size()) {
            return chosen.size();
        }
        int upper = chosen.size() + types.size() - index;
        int best = best(types, index + 1, chosen);
        for (CorroborationSignal candidate : types.get(index)) {
            if (best == upper) {
                break;
            }
            if (chosen.stream().allMatch(c -> independent(c, candidate))) {
                chosen.add(candidate);
                best = Math.max(best, best(types, index + 1, chosen));
                chosen.removeLast();
            }
        }
        return best;
    }

    static Set<String> titleTokens(String title) {
        if (title == null) {
            return Set.of();
        }
        String tokens = EntityRules.normalForm(EntityRules.MECHANISM, title);
        return tokens.isEmpty() ? Set.of() : new HashSet<>(Arrays.asList(tokens.split(" ")));
    }
}
