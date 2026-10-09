package dev.auspex.corehub.watchlist;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

/** SEC filer tickers and their registered titles, loaded once from `company_tickers.json`. */
@Component
public class SecTickerCache {

    private static final Logger log = LoggerFactory.getLogger(SecTickerCache.class);

    private volatile Map<String, String> tickerToTitle = Map.of();
    private final String tickersUrl;
    private final ObjectMapper objectMapper;

    SecTickerCache(
            @Value("${auspex.sec.tickers-url:https://www.sec.gov/files/company_tickers.json}") String tickersUrl,
            ObjectMapper objectMapper
    ) {
        this.tickersUrl = tickersUrl;
        this.objectMapper = objectMapper;
    }

    @PostConstruct
    void load() {
        try {
            RestClient client = RestClient.builder()
                    .defaultHeader("User-Agent", "auspex-corehub/1.0 matthiasdebeule02@gmail.com")
                    .build();
            String json = client.get().uri(tickersUrl).retrieve().body(String.class);
            JsonNode root = objectMapper.readTree(json);
            Map<String, String> loaded = new HashMap<>();
            root.fields().forEachRemaining(e -> {
                JsonNode company = e.getValue();
                String ticker = company.path("ticker").asText("").toUpperCase();
                String name = company.path("title").asText("");
                if (!ticker.isEmpty() && !name.isEmpty()) {
                    loaded.put(ticker, name);
                }
            });
            replaceEntries(loaded);
            log.info("SEC ticker cache loaded: {} entries", loaded.size());
        } catch (Exception ex) {
            log.warn("SEC ticker cache unavailable; company name resolution disabled until restart: {}", ex.getMessage());
        }
    }

    public Optional<String> getName(String ticker) {
        return Optional.ofNullable(tickerToTitle.get(ticker.toUpperCase()));
    }

    /**
     * Ticker to SEC title. The same instance is returned until the entries are replaced, so a
     * caller may cache anything derived from it by identity.
     */
    public Map<String, String> entries() {
        return tickerToTitle;
    }

    public void replaceEntries(Map<String, String> tickerToTitle) {
        this.tickerToTitle = Map.copyOf(tickerToTitle);
    }
}
