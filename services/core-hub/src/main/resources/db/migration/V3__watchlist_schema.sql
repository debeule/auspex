CREATE TABLE watchlist (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker       VARCHAR(10) NOT NULL,
    company_name TEXT        NOT NULL,
    added_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes        TEXT,
    -- Single-user installation.
    -- Multi-user: add user_id UUID NOT NULL REFERENCES users(id),
    -- drop watchlist_ticker_unique, add CONSTRAINT UNIQUE (user_id, ticker).
    CONSTRAINT watchlist_ticker_unique UNIQUE (ticker)
);

CREATE TABLE watchlist_gene_target (
    watchlist_id UUID        NOT NULL REFERENCES watchlist(id) ON DELETE CASCADE,
    gene_target  TEXT        NOT NULL,
    source       TEXT        NOT NULL CHECK (source IN ('graph', 'clinicaltrials', 'manual')),
    added_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (watchlist_id, gene_target)
);

CREATE INDEX ON watchlist_gene_target (gene_target);
