package dev.auspex.corehub.signal;

public interface SignalRecordPort {
    void upsert(ResearchSignalEvent event);
}
