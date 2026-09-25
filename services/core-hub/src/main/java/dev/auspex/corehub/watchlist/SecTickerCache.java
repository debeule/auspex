package dev.auspex.corehub.watchlist;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

@Component
public class SecTickerCache {

    private static final Logger log = LoggerFactory.getLogger(SecTickerCache.class);

    private final Map<String, String> cache = new ConcurrentHashMap<>();
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
            root.fields().forEachRemaining(e -> {
                JsonNode company = e.getValue();
                String ticker = company.path("ticker").asText("").toUpperCase();
                String name = company.path("title").asText("");
                if (!ticker.isEmpty() && !name.isEmpty()) {
                    cache.put(ticker, name);
                }
            });
            log.info("SEC ticker cache loaded: {} entries", cache.size());
        } catch (Exception ex) {
            log.warn("SEC ticker cache unavailable; company name resolution disabled until restart: {}", ex.getMessage());
        }
    }

    public Optional<String> getName(String ticker) {
        return Optional.ofNullable(cache.get(ticker.toUpperCase()));
    }
}
