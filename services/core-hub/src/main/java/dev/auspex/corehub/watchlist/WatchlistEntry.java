package dev.auspex.corehub.watchlist;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

public record WatchlistEntry(
        UUID id,
        String ticker,
        String companyName,
        Instant addedAt,
        List<WatchlistGeneTarget> geneTargets
) {}
