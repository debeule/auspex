package dev.auspex.corehub.rest;

import dev.auspex.corehub.query.ExtractionLineageService;
import dev.auspex.corehub.query.ExtractionLineageService.ExtractionModelCount;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.time.LocalDate;
import java.util.List;

@RestController
@RequestMapping("/api/v1/extractions")
class ExtractionController {

    private final ExtractionLineageService lineageService;

    ExtractionController(ExtractionLineageService lineageService) {
        this.lineageService = lineageService;
    }

    @GetMapping("/models")
    List<ExtractionModelCount> models(
            @RequestParam("source_type") String sourceType,
            @RequestParam("from") @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate from,
            @RequestParam("to") @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate to) {
        if (to.isBefore(from)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "'to' is before 'from'");
        }
        return lineageService.modelsInWindow(sourceType, from, to);
    }
}
