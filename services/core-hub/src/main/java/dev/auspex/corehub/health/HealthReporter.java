package dev.auspex.corehub.health;

import io.micrometer.core.instrument.Gauge;
import io.micrometer.core.instrument.MeterRegistry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Logs and exports dead-letter depth per topic and the age of each source's latest stored signal
 * (requirements §12): a connector that silently returns nothing shows up as a growing age. A
 * reader that fails leaves the previous values in place and is logged; the next report retries.
 */
@Component
public class HealthReporter {

    private static final Logger log = LoggerFactory.getLogger(HealthReporter.class);

    private final DltDepthReader dltDepthReader;
    private final SignalAgeReader signalAgeReader;
    private final MeterRegistry meterRegistry;
    private final Clock clock;
    private final Map<String, AtomicLong> depthByTopic = new ConcurrentHashMap<>();
    private final Map<String, Instant> latestBySource = new ConcurrentHashMap<>();

    public HealthReporter(
            DltDepthReader dltDepthReader,
            SignalAgeReader signalAgeReader,
            MeterRegistry meterRegistry,
            Clock clock
    ) {
        this.dltDepthReader = dltDepthReader;
        this.signalAgeReader = signalAgeReader;
        this.meterRegistry = meterRegistry;
        this.clock = clock;
    }

    @Scheduled(fixedDelayString = "${auspex.health.report-interval-ms:300000}")
    public void report() {
        try {
            dltDepthReader.depthByTopic().forEach((topic, depth) -> {
                depthByTopic.computeIfAbsent(topic, this::registerDepthGauge).set(depth);
                log.info("health dlt_depth topic={} depth={}", topic, depth);
            });
        } catch (RuntimeException e) {
            log.error("health report could not read dead-letter depth", e);
        }
        try {
            signalAgeReader.latestIngestedAtBySource().forEach((source, latest) -> {
                if (latestBySource.put(source, latest) == null) {
                    registerAgeGauge(source);
                }
                log.info("health source_latest_signal source_type={} ingested_at={} age_seconds={}",
                        source, latest, ageSeconds(source));
            });
        } catch (RuntimeException e) {
            log.error("health report could not read the latest signal per source", e);
        }
    }

    private AtomicLong registerDepthGauge(String topic) {
        AtomicLong depth = new AtomicLong();
        Gauge.builder("auspex.dlt.depth", depth, AtomicLong::get)
                .description("Dead-lettered records not yet replayed")
                .tag("topic", topic)
                .register(meterRegistry);
        return depth;
    }

    private void registerAgeGauge(String source) {
        Gauge.builder("auspex.source.latest.signal.age", this, reporter -> reporter.ageSeconds(source))
                .description("Seconds since the source's most recent signal was stored")
                .baseUnit("seconds")
                .tag("source_type", source)
                .register(meterRegistry);
    }

    private double ageSeconds(String source) {
        return Duration.between(latestBySource.get(source), clock.instant()).toMillis() / 1000.0;
    }
}
