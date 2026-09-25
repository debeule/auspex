package dev.auspex.corehub.watchlist;

import java.time.Instant;
import java.util.List;

public record WatchlistSummary(
        String ticker,
        String companyName,
        List<WatchlistGeneTargetStat> geneTargets,
        List<Object> directSignals,
        List<CorroborationRef> corroborations,
        Stats stats
) {
    public record WatchlistGeneTargetStat(String name, String source, long signalCount, Instant lastSeen) {}
    public record CorroborationRef(String entityKey, Instant corroboratedAt, double confidence) {}
    public record Stats(
            long totalDirect,
            long totalCorroborations,
            String mostActiveGeneTarget,
            Instant lastSignalAt
    ) {}
}
