package dev.auspex.corehub.kafka;

/** Deterministic failure — routes to DLT immediately without retries. */
public class UnknownMajorVersionException extends RuntimeException {
    public UnknownMajorVersionException(String message) {
        super(message);
    }
}
