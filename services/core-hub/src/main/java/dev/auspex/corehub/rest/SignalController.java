package dev.auspex.corehub.rest;

import dev.auspex.corehub.rest.dto.TickerSignalsResponse;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.regex.Pattern;

@RestController
@RequestMapping("/api/v1")
class SignalController {

    // §11: allowlist — 1-10 chars, starts with A-Z, remaining A-Z0-9.-
    private static final Pattern TICKER_PATTERN = Pattern.compile("^[A-Z][A-Z0-9.\\-]{0,9}$");

    private final SignalQueryService queryService;

    SignalController(SignalQueryService queryService) {
        this.queryService = queryService;
    }

    @GetMapping("/signals/{ticker}")
    TickerSignalsResponse getSignals(@PathVariable String ticker) {
        if (!TICKER_PATTERN.matcher(ticker).matches()) {
            throw new TickerValidationException("Invalid ticker: " + ticker);
        }
        return queryService.query(ticker);
    }
}
