-- One record per episode and scope. Rows written under the earlier definition are derived data;
-- the rules sync on the next start rebuilds them from the graph.
TRUNCATE corroboration;

ALTER TABLE corroboration
    ADD COLUMN ticker            TEXT        NOT NULL,
    ADD COLUMN episode_opened_at TIMESTAMPTZ NOT NULL,
    ADD COLUMN excluded_reason   TEXT,
    ADD COLUMN published_at      TIMESTAMPTZ;

ALTER TABLE corroboration DROP CONSTRAINT corroboration_pkey;
ALTER TABLE corroboration
    ADD CONSTRAINT corroboration_pkey PRIMARY KEY (entity_key, ticker, participants_hash),
    ADD CONSTRAINT corroboration_opened_before_corroborated CHECK (episode_opened_at <= corroborated_at),
    ADD CONSTRAINT corroboration_corroborated_before_detected CHECK (corroborated_at <= first_detected_at),
    ADD CONSTRAINT corroboration_excluded_reason CHECK (excluded_reason IN ('broad_entity'));

CREATE INDEX corroboration_participants ON corroboration USING GIN (participant_event_ids);

CREATE TABLE corroboration_rules_state (
    singleton  BOOLEAN     PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    rules_hash TEXT        NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL
);
