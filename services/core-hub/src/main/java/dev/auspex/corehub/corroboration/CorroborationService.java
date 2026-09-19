package dev.auspex.corehub.corroboration;

/**
 * Drives the pairwise corroboration scan.
 * The interface is kept so a future Streams implementation is a substitution, not an insertion.
 * CorroborationServiceContractTest runs unmodified against any implementation.
 */
public interface CorroborationService {
    void runCorroboration();
}
