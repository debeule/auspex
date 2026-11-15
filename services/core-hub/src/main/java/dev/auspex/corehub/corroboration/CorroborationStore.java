package dev.auspex.corehub.corroboration;

import java.time.Instant;
import java.util.List;
import java.util.Set;

/** The Postgres reads and writes of the corroboration scan and the rules sync. */
public interface CorroborationStore {

    /** The rules hash last applied by the rules sync, or null when none was. */
    String appliedRulesHash();

    void storeAppliedRulesHash(String hash, Instant appliedAt);

    /** {@code entity_key}s of live rows that list any of the signals. */
    Set<String> liveEntityKeysListing(List<String> eventIds);

    /** Every row of the entity, live and superseded, in all scopes. */
    List<CorroborationRow> rows(String entityKey);

    /** Inserts a row; a repeated record key does nothing. */
    void insert(CorroborationRow row);

    void revive(String entityKey, String ticker, String participantsHash);

    void supersede(String entityKey, String ticker, String participantsHash, String supersededBy);

    void setExcludedReason(String entityKey, String ticker, String participantsHash, String excludedReason);

    void markPublished(String entityKey, String ticker, String participantsHash, Instant publishedAt);
}
