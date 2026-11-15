package dev.auspex.corehub.corroboration;

/** The corroboration rules file is missing or breaks one of its rules; core-hub does not start. */
public class InvalidEntityRulesException extends IllegalStateException {
    public InvalidEntityRulesException(String message) {
        super(message);
    }
}
