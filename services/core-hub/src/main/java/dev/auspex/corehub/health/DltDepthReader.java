package dev.auspex.corehub.health;

import java.util.Map;

/** Records waiting on each dead-letter topic that no replay has taken yet. */
@FunctionalInterface
public interface DltDepthReader {

    Map<String, Long> depthByTopic();
}
