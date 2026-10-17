package dev.auspex.corehub.audit;

/** A raw pointer that can never be audited as sent; dead-lettered without retries. */
public class InvalidRawPointerException extends RuntimeException {
    public InvalidRawPointerException(String message) {
        super(message);
    }

    public InvalidRawPointerException(String message, Throwable cause) {
        super(message, cause);
    }
}
