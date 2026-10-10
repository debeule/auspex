package dev.auspex.corehub.rest;

import dev.auspex.corehub.kafka.DltReplayService;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.util.Map;

@RestController
@RequestMapping("/api/dlt")
class DltController {

    private final DltReplayService replayService;

    DltController(DltReplayService replayService) {
        this.replayService = replayService;
    }

    @PostMapping("/{topic}/replay")
    Map<String, Integer> replay(@PathVariable String topic) {
        if (!DltReplayService.REPLAYABLE_TOPICS.contains(topic)) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "not a replayable dead-letter topic: " + topic);
        }
        return Map.of("replayed", replayService.replay(topic));
    }
}
