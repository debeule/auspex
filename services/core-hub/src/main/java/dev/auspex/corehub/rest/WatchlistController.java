package dev.auspex.corehub.rest;

import dev.auspex.corehub.watchlist.WatchlistAddRequest;
import dev.auspex.corehub.watchlist.WatchlistEntry;
import dev.auspex.corehub.watchlist.WatchlistGeneTarget;
import dev.auspex.corehub.watchlist.WatchlistPatchRequest;
import dev.auspex.corehub.watchlist.WatchlistPreview;
import dev.auspex.corehub.watchlist.WatchlistService;
import dev.auspex.corehub.watchlist.WatchlistSummary;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/v1/watchlist")
class WatchlistController {

    private final WatchlistService watchlistService;

    WatchlistController(WatchlistService watchlistService) {
        this.watchlistService = watchlistService;
    }

    @GetMapping
    List<WatchlistEntry> list() {
        return watchlistService.list();
    }

    @GetMapping("/preview")
    WatchlistPreview preview(@RequestParam String ticker) {
        return watchlistService.preview(ticker.toUpperCase());
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    WatchlistEntry add(@RequestBody WatchlistAddRequest request) {
        return watchlistService.add(request);
    }

    @DeleteMapping("/{ticker}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    void delete(@PathVariable String ticker) {
        watchlistService.delete(ticker);
    }

    @PatchMapping("/{ticker}/gene-targets")
    List<WatchlistGeneTarget> patchGeneTargets(
            @PathVariable String ticker,
            @RequestBody WatchlistPatchRequest request) {
        return watchlistService.patchGeneTargets(ticker, request);
    }

    @GetMapping("/{ticker}/summary")
    WatchlistSummary summary(@PathVariable String ticker) {
        return watchlistService.summary(ticker);
    }
}
