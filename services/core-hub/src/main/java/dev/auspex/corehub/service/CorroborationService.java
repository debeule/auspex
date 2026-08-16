package dev.auspex.corehub.service;

/**
 * Drives the pairwise corroboration scan (§4.2).
 * The interface is kept so Step 6.4's Streams implementation is a substitution, not an insertion.
 * CorroborationServiceContractTest runs unmodified against any implementation.
 */
public interface CorroborationService {
    void runCorroboration();
}
