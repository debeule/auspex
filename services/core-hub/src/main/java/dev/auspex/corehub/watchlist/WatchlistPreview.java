package dev.auspex.corehub.watchlist;

import java.util.List;

public record WatchlistPreview(
        String ticker,
        String companyName,
        List<GeneTargetWithCount> graphGeneTargets,
        List<CtSuggestion> ctSuggestions
) {}
