package dev.auspex.corehub.watchlist;

import java.util.List;

public record WatchlistPatchRequest(List<String> add, List<String> remove) {}
