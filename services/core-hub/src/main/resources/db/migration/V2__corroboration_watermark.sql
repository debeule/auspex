-- V2: watermark for incremental corroboration scan (§4.2)
-- Singleton table — UPSERT on conflict; empty row treated as EPOCH by the service.
CREATE TABLE corroboration_state (
    singleton   BOOL        NOT NULL DEFAULT TRUE,
    watermark   TIMESTAMPTZ NOT NULL,
    CONSTRAINT corroboration_state_pkey PRIMARY KEY (singleton)
);
