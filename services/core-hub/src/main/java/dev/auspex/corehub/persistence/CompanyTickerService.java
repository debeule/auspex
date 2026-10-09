package dev.auspex.corehub.persistence;

import dev.auspex.corehub.watchlist.SecTickerCache;
import dev.auspex.corehub.watchlist.WatchlistTickerAdded;
import org.neo4j.driver.Driver;
import org.neo4j.driver.Session;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

/**
 * Resolves `Company.ticker` from SEC filer titles. A ticker is only ever taken from a single
 * unambiguous match on the normalized name: a wrong ticker would attach another company's signals
 * to a watchlist entry, which is worse than a missing one.
 */
@Service
public class CompanyTickerService {

    private static final Logger log = LoggerFactory.getLogger(CompanyTickerService.class);

    private record Index(Map<String, String> source, Map<String, String> uniqueTickerByName) {}

    private final Driver driver;
    private final SecTickerCache secTickers;
    private volatile Index index = new Index(null, Map.of());

    public CompanyTickerService(Driver driver, SecTickerCache secTickers) {
        this.driver = driver;
        this.secTickers = secTickers;
    }

    /** The ticker of the one SEC filer whose normalized title equals this name's, if exactly one does. */
    public Optional<String> uniqueTicker(String companyName) {
        String key = CompanyNameNormalizer.normalize(companyName);
        return key.isEmpty() ? Optional.empty() : Optional.ofNullable(currentIndex().uniqueTickerByName().get(key));
    }

    /** Sets the new watchlist ticker on tickerless Company nodes whose normalized name matches its SEC title. */
    @EventListener
    public void onWatchlistTickerAdded(WatchlistTickerAdded added) {
        Optional<String> title = secTickers.getName(added.ticker());
        if (title.isEmpty()) return;
        String key = CompanyNameNormalizer.normalize(title.get());
        if (key.isEmpty()) return;
        try (Session session = driver.session()) {
            List<String> names = session.run("MATCH (c:Company) WHERE c.ticker IS NULL RETURN c.name AS name")
                    .list(r -> r.get("name").asString())
                    .stream()
                    .filter(name -> CompanyNameNormalizer.normalize(name).equals(key))
                    .toList();
            if (names.isEmpty()) return;
            session.run("""
                    UNWIND $names AS name
                    MATCH (c:Company {name: name})
                    WHERE c.ticker IS NULL
                    SET c.ticker = $ticker
                    """, Map.of("names", names, "ticker", added.ticker()));
        } catch (RuntimeException ex) {
            // The watchlist row is already stored; a missed backfill only delays ticker lookups.
            log.warn("Company ticker backfill failed for {}: {}", added.ticker(), ex.getMessage());
        }
    }

    private Index currentIndex() {
        Map<String, String> source = secTickers.entries();
        Index current = index;
        if (current.source() == source) return current;
        Map<String, Set<String>> tickersByName = new HashMap<>();
        source.forEach((ticker, title) -> {
            String key = CompanyNameNormalizer.normalize(title);
            if (!key.isEmpty()) tickersByName.computeIfAbsent(key, k -> new HashSet<>()).add(ticker);
        });
        Map<String, String> unique = new HashMap<>();
        tickersByName.forEach((name, tickers) -> {
            if (tickers.size() == 1) unique.put(name, tickers.iterator().next());
        });
        current = new Index(source, Map.copyOf(unique));
        index = current;
        return current;
    }
}
