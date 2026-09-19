package dev.auspex.corehub.signal;

public interface SignalGraphPort {
    void upsert(ResearchSignalEvent event);
}
