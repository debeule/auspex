-- V1: initial signal schema
-- Natural keys per §3.7; confidence_score NUMERIC(4,3) per §10.3.

CREATE TABLE raw_fetch_audit (
    raw_object_key  TEXT        NOT NULL,
    source_type     TEXT        NOT NULL,
    external_id     TEXT        NOT NULL,
    content_sha256  TEXT        NOT NULL,
    retrieved_at    TIMESTAMPTZ NOT NULL,
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT raw_fetch_audit_pkey PRIMARY KEY (raw_object_key)
);

CREATE TABLE signal_current (
    event_id            UUID        NOT NULL,
    extraction_id       UUID        NOT NULL,
    schema_version      TEXT        NOT NULL,
    source_type         TEXT        NOT NULL,
    source_url          TEXT        NOT NULL,
    external_id         TEXT        NOT NULL,
    canonical_id        TEXT,
    raw_object_key      TEXT        NOT NULL,
    published_date      TIMESTAMPTZ NOT NULL,
    published_date_field TEXT       NOT NULL,
    ingested_at         TIMESTAMPTZ NOT NULL,
    title               TEXT        NOT NULL,
    raw_text_snippet    TEXT        NOT NULL,
    gene_targets        TEXT[]      NOT NULL,
    mechanisms          TEXT[]      NOT NULL,
    companies_mentioned TEXT[]      NOT NULL,
    summary             TEXT        NOT NULL,
    directionality      TEXT        NOT NULL,
    confidence_score    NUMERIC(4,3) NOT NULL,
    prompt_version      TEXT        NOT NULL,
    prefilter_version   TEXT        NOT NULL,
    extraction_model    TEXT        NOT NULL,
    last_updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT signal_current_pkey PRIMARY KEY (event_id)
);

CREATE TABLE signal_extraction_history (
    event_id        UUID        NOT NULL,
    extraction_id   UUID        NOT NULL,
    schema_version  TEXT        NOT NULL,
    confidence_score NUMERIC(4,3) NOT NULL,
    prompt_version  TEXT        NOT NULL,
    prefilter_version TEXT      NOT NULL,
    extraction_model TEXT       NOT NULL,
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT signal_extraction_history_pkey PRIMARY KEY (event_id, extraction_id)
);

-- First observation wins for source_type on signal_current (§10.1).
CREATE TABLE source_observation (
    event_id        UUID        NOT NULL,
    source_type     TEXT        NOT NULL,
    external_id     TEXT        NOT NULL,
    raw_object_key  TEXT        NOT NULL,
    observed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT source_observation_pkey PRIMARY KEY (event_id, source_type, external_id)
);

-- Corroboration record with explicit supersession (§4.1).
CREATE TABLE corroboration (
    entity_key           TEXT        NOT NULL,
    participants_hash    TEXT        NOT NULL,
    participant_event_ids UUID[]      NOT NULL,
    distinct_source_count INTEGER    NOT NULL,
    corroborated_at      TIMESTAMPTZ NOT NULL,
    first_detected_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    superseded_by        TEXT,
    CONSTRAINT corroboration_pkey PRIMARY KEY (entity_key, participants_hash)
);

-- Indexes for common query patterns
CREATE INDEX signal_current_published_date_idx ON signal_current (published_date);
CREATE INDEX signal_current_source_type_idx    ON signal_current (source_type);
CREATE INDEX signal_current_ingested_at_idx    ON signal_current (ingested_at);
CREATE INDEX source_observation_event_id_idx   ON source_observation (event_id);
