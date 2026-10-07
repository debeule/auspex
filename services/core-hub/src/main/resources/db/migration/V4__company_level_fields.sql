-- Company-level extraction fields from schema 1.1. Schema 1.0 events carry none of them,
-- so event_type and primary_company are nullable and the arrays default to empty.
ALTER TABLE signal_current
    ADD COLUMN event_type          TEXT,
    ADD COLUMN primary_company     TEXT,
    ADD COLUMN program_identifiers TEXT[] NOT NULL DEFAULT '{}',
    ADD COLUMN trial_ids           TEXT[] NOT NULL DEFAULT '{}';
