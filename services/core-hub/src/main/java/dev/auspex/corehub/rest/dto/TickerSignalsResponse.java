package dev.auspex.corehub.rest.dto;

import java.util.List;

public record TickerSignalsResponse(
        String ticker,
        List<DirectSignalDto> directSignals,
        List<CorroboratedSignalDto> corroboratedSignals
) {}
