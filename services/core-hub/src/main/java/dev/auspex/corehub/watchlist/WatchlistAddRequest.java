package dev.auspex.corehub.watchlist;

import java.util.List;

public record WatchlistAddRequest(
        String ticker,
        String companyName,
        List<WatchlistGeneTarget> geneTargets
) {}
