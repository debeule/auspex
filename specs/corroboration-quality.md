# Corroboration quality

**Status:** ready
**Branch:** `feature/corroboration-quality`
**Docs impact:** adds six `COR-new`, one each of `HUB-new`, `CON-new`, `RES-new`, `EVA-new`, `ING-new`, `EXT-new`, `STR-new` and `DSH-new`; retires COR-003, COR-005, COR-007, HUB-046, CON-025, RES-071, ING-011 and EXT-018; changes the IDs listed below.
- `COR-new` ([docs/core-hub/corroboration.md](../docs/core-hub/corroboration.md)), six: the entity rules file and canonical keys, called *entity rules* below; a broad entity's record, called *exclusion*; what makes two participants independent, called *independence*; the episode and its record, called *episode*; records scoped to a ticker, called *ticker record*; the rules sync at startup, called *rules sync*.
- retired and replaced in the same file: COR-003 (by *independence* and *episode*), COR-005 (by *episode*), COR-007 (by the supersession part of *episode*).
- changed in the same file: COR-004 (the key's name part is the canonical key of *entity rules*), COR-008 (the rules sync also marks signals pending), COR-009 (a scan reads only signals published by now and reconciles every entity a pending signal touches), COR-011 (a future `published_date` is the one clock gate), COR-012 (an excluded record is not published; `published_at` records the send). COR-013 keeps its text; its `distinct_source_count` input becomes the count of *independence*.
- [docs/core-hub/storage.md](../docs/core-hub/storage.md): changed HUB-030 (entity nodes carry `corroboration_key`) and HUB-032 (two indexes on it). [docs/core-hub/http-api.md](../docs/core-hub/http-api.md): HUB-046 retired and replaced by `HUB-new`, called *ticker response*.
- [docs/system/contracts.md](../docs/system/contracts.md): CON-025 retired and replaced by `CON-new`, called *record key*; changed CON-032 (four new fields), CON-033 (identity includes `ticker`), CON-034 (`divergent` to `tested`).
- [docs/research/backtesting.md](../docs/research/backtesting.md): RES-071 retired and replaced by `RES-new`, called *backtest episode*; RES-067 reworded (the event time is the episode's opening). [docs/research/evaluation-protocol.md](../docs/research/evaluation-protocol.md): `EVA-new`, called *rules lock*.
- [docs/ingestion/connectors.md](../docs/ingestion/connectors.md): ING-011 retired and replaced by `ING-new`, called *PubMed date*. [docs/ingestion/extraction.md](../docs/ingestion/extraction.md): EXT-018 retired and replaced by `EXT-new`, called *stratified review*.
- [docs/strategy/runtime.md](../docs/strategy/runtime.md): STR-024 (`divergent` to `tested`); `STR-new`, called *ticker-less event*. [docs/dashboard.md](../docs/dashboard.md): `DSH-new`, called *context list*.

---

## Context

Written against `develop` @ `0063179`. Live figures were read from the stack machine's Postgres on 2026-11-15 and will have grown; the stack-machine steps below measure them again.

**What exists.** core-hub finds corroborations in `services/core-hub/src/main/java/dev/auspex/corehub/corroboration/`: `ScheduledCorroborationService` (the only `CorroborationService`, INV-5) runs `CorroborationScanner` every `corroboration.interval-ms`. The scanner reads one batch of pending signals from Neo4j (COR-008, COR-009) and, for each pending signal and each `GeneTarget` or `Mechanism` node it links to, forms one group: that signal plus every signal on the same node from another `source_type` published within 90 days of it. Each group becomes a row of the Postgres table `corroboration`, keyed `(entity_key, participants_hash)` (CON-025), and is published to `auspex.signals.corroborated`. A row is superseded only when a later group holds all of its participants (COR-007). `EntityNormalizer` has one implementation, `IdentityEntityNormalizer`, which returns the name unchanged. `query/SignalQueryService` answers `GET /api/v1/signals/{ticker}` with every live row that lists any signal mentioning that ticker's company (HUB-046). The score is `CorroborationScorer` (COR-013). The backtest never reads that table: `services/backtesting/src/auspex_backtesting/backtest/runner.py` replays signals itself, per gene target and ticker (`_corroborations`, RES-071). The strategy runtime builds its record with an empty ticker and no source types (STR-024, `divergent`).

**Why this spec.** The question it answers is whether a corroboration can become a point-in-time, per-ticker event whose edge the evaluation protocol can falsify. Today it cannot:

| Measure, 2026-11-15 | Value |
|---|---|
| Signals / naming a company | 883 / 300 |
| Corroboration rows, all / live | 495 / 375 |
| Live rows by kind | Mechanism 320 (67 entities), GeneTarget 55 (32 entities) |
| `gene therapy:Mechanism` live rows | 101, groups of 11 to 81 signals over 107 distinct signals |
| Live rows that reach a ticker | 305, almost all through one participant |
| Live rows that are bioRxiv + PubMed only | 60 |
| Rows first detected on 2026-11-07 | 260 of 495: every source's first run with its 30-day look-back, not steady state |

1. **Generic mechanisms dominate.** `gene therapy` links any two documents that mention it. Of 14 corroborations shown for SRPT on 2026-11-07, 13 were `gene therapy:Mechanism`.
2. **A ticker attaches through one participant.** One company-naming signal in a group puts the whole group on that ticker.
3. **Rows repeat.** Every pending signal makes its own group, so groups on a busy entity overlap without nesting and are never superseded: one entity holds 101 live rows.
4. **Sources are not independent.** `distinct_source_count` counts source types, so a bioRxiv preprint and its PubMed paper are two sources.
5. **Entity names split.** `CRISPR-Cas9` (16 rows) and `CRISPR/Cas9` (15), `gene editing` (14) and `genome editing` (5) are separate entities.
6. **Dates in the future.** Three PubMed signals carry a `published_date` up to 2027-10-20 (the journal issue date), and three live rows a `corroborated_at` after today.

The degree cap (COR-009, 500) is not a cause and is not changed: the busiest entity has 107 signals.

The hand review of 2026-09-13 (`## 2026-09-13 — Step 3.2 — VERIFIED — Corroboration quality review complete`, 26 of 30 on gene targets) looked at none of this, so it does not contradict it.

**No backtest has read a corroboration yet.** `config/hypotheses/trials/`, where every reserved cell is recorded (EVA-011), does not exist on `develop`; `config/hypotheses/registry.jsonl` holds one line per hypothesis, all dated 2026-10-09; `h1`, `h4` and `h6` are `suspended` and refused before any return is read (EVA-009). The hypotheses defined on corroboration events are `h1` to `h7` (each has `signal_definition.join_field: corroborated_at`); `h8` uses typed company events and `h9` to `h12` use panels. This spec changes what a corroboration event is for `h1` to `h7`. It edits none of their files, so no hash changes and nothing is registered again; it is not a new hypothesis version (EVA-003 keeps one version until the first evaluation) and it spends no trial (no cell has been reserved). The stack-machine steps check the ledger again before the rules are signed off.

## What this builds

Definitions used below. The *window* is 90 days, both ends included, between two `published_date`s (the constant of today's COR-003). *Now* is the service clock at the start of a scan. A signal is *eligible* when its `published_date` is not after now.

### 1. Entity rules, one file

`config/corroboration/entity-rules.yaml` is the single definition of which entity names are one entity, which entities are too broad to corroborate, and which signals are one finding:

```yaml
synonyms:            # canonical key: [variant keys], per node label
  Mechanism:
    gene editing: [genome editing]
  GeneTarget: {}
excluded:            # canonical keys, per node label
  Mechanism:
    - gene therapy
    - aav gene therapy
    - aav
    - gene editing
    - crispr cas9
    - crispr cas12a
    - crispr
    - cell therapy
    - gene replacement therapy
    - viral vector
    - lentiviral vector
    - lipid nanoparticle
    - mrna
    - sirna
    - rnai
    - antisense oligonucleotide
    - immunotherapy
    - car t
    - monoclonal antibody
    - small molecule
  GeneTarget: []
same_finding:
  source_type_pairs: [[biorxiv, pubmed]]
  title_token_jaccard_min: 0.8
```

The first six excluded names are the ones the live data showed (Context); the rest are modality and delivery classes listed by judgment. The owner approved the list as written. A name is *broad* when, and only when, its canonical key is in `excluded` for its label.

- **Canonical key.** For a `GeneTarget`: Unicode NFKC, upper-cased, every character that is not a letter or digit removed (`IL-2`, `il2` and `IL 2` are `IL2`). For a `Mechanism`: NFKC, lower-cased, every run of characters that are not letters or digits turned into one space, trimmed (`CRISPR-Cas9` and `CRISPR/Cas9` are `crispr cas9`). A key listed as a variant is then replaced by its canonical key. `entity_key` is the canonical key, a colon and the label; existing examples keep their form (`BCL11A:GeneTarget`, `base editing:Mechanism`).
- **Loading.** core-hub reads the file at start from `corroboration.rules-file` in `application.yml` (compose mounts `config/corroboration` read-only and sets the path) and refuses to start when the file is missing or invalid. Invalid means: a name not already in canonical form, a variant listed under two canonical keys, a canonical key that is also a variant, an excluded name that is a variant, a `source_type_pairs` value outside the source types of CON-017, or a threshold outside (0, 1].
- **Rules hash.** The SHA-256 of the file's bytes. It is the one version of the rules: core-hub stores the hash it last applied (part 6) and the evaluation protocol locks it (part 8).
- **Where the key lives.** Entity nodes keep the `name` the extractor wrote and are still merged on it (HUB-023, CON-027). Each `GeneTarget` and `Mechanism` node also carries `corroboration_key`, set by the rules sync (part 6) and, for a node that has none yet, by the scan before it groups. Two nodes with one key and one label are one entity to the scan. `IdentityEntityNormalizer` is deleted; `EntityNormalizer` is implemented by the rules.

### 2. Independent sources

Two participants are *the same finding* when their `source_type`s form a pair listed in `same_finding.source_type_pairs`, both have a title, and the Jaccard overlap of their title token sets (titles through the Mechanism normalisation, split on spaces) is at least `title_token_jaccard_min`. Two participants are *independent* when their `source_type`s differ and they are not the same finding. `distinct_source_count` is the largest number of participants that can be chosen so that every two are independent. A set corroborates when that number is at least 2.

So a preprint and its paper alone count once; a preprint, its paper and an unrelated paper count twice; members of one patent family count once, as today, because they share a source type. COR-013 is not changed, but its diversity term now reads this count, so a row that was bioRxiv + PubMed for one finding scores as nothing instead of two sources.

### 3. Episodes

An *episode* is defined on a *scope*: all eligible signals of one entity (the entity scope), or those of them that mention a company carrying one ticker (a ticker scope, part 4). `EpisodeBuilder`, a pure function, replays a scope's signals in order of `(published_date, event_id)`:

1. While an episode is open and the signal is published no later than the window after the episode's opening, the signal joins it.
2. Otherwise the open episode is closed, candidates published more than the window before this signal are dropped, and the signal becomes a candidate.
3. When the candidates hold two independent participants, they open an episode: its `episode_opened_at` is this signal's `published_date`, and the candidate list is emptied.

Consequences the tests pin: every signal is in at most one episode of a scope; every participant lies within the window of the opening signal; an episode accepts joiners for one window and then closes, so a continuous flow of signals opens a new episode only from two fresh independent sources after the previous one closed; and the result depends only on the scope's signals, never on arrival order, so a late-arriving earlier signal can move an opening earlier.

**The record.** One live row of `corroboration` per episode: `entity_key`, `ticker` (empty for the entity scope), `participants_hash`, `participant_event_ids`, `distinct_source_count` (part 2, over all participants), `corroborated_at` (the latest participant's `published_date`, as today), `episode_opened_at`, `first_detected_at` (now, from the service clock, diagnostic only as in COR-006), `excluded_reason` (null or `broad_entity`), `published_at` and `superseded_by`. The natural key is `(entity_key, ticker, participants_hash)` (*record key*, INV-10). The table enforces `episode_opened_at <= corroborated_at` and `corroborated_at <= first_detected_at` with `CHECK` constraints.

**Reconciling.** A scan no longer inserts one group per pending signal. For every entity a pending signal touches (the entities it links to now, and the `entity_key` of every live row that lists it, so an entity dropped by a re-extraction is reconciled too), the scan loads the entity's eligible signals, skips the entity when they exceed the degree cap, builds the episodes of the entity scope and of each ticker scope, and makes the table agree:
- an episode with no row is inserted;
- an episode whose row exists but is superseded is made live again;
- a live row of that entity that no episode produces is superseded: `superseded_by` is the `participants_hash` of the episode in its scope that shares a participant with it, or the literal `rules` when none does;
- `excluded_reason` on a live row is set to what the rules say now.

Superseded rows are kept, as today.

**Publishing.** Each live row with no `excluded_reason` and no `published_at` is sent to `auspex.signals.corroborated`, keyed by `entity_key`, and its `published_at` is set in the scan's transaction. A joining signal therefore publishes the episode's new record once, as today; an excluded row is never sent; a row that stops being excluded after a rules change is sent then. The event gains `ticker`, `source_types` (the participants' distinct `source_type`s, sorted), `episode_opened_at` and `schema_version`. A consumer tells an opening from an extension by `corroborated_at = episode_opened_at`, and treats `(entity_key, ticker, participants_hash)` as the event's identity (CON-033).

**Atomicity.** One scan is one Postgres transaction, as today (COR-010): every insert, supersession and `published_at` commits together, only after every send is acknowledged; the pending flags are cleared after the commit and only where the write token is unchanged. A failed send, commit or clear leaves the signals pending, increments the failure counter (COR-014), and the next scan reconciles the same entities again, which sends again (at least once). A signal written while a scan runs has a new token, stays pending, and is reconciled by the next scan. Setting a missing `corroboration_key` is idempotent and outside that transaction. One core-hub instance runs the scan; the record key makes a repeated insert harmless.

### 4. Ticker records

For each ticker carried by a company that an entity's eligible signals mention, the scan builds the episodes of that ticker scope and stores them as rows with that `ticker`. A ticker record therefore exists only when two independent sources on the same entity both name the company, within the window, and its `episode_opened_at` is the publication of the second of them, which can be later than the entity record's. A broad entity gets no ticker record. A company named by one participant gets none.

`GET /api/v1/signals/{ticker}` (*ticker response*) returns:
- `corroborated_signals`: the live ticker records of that ticker, each with its score (COR-013), `episode_opened_at` and source types;
- `context_corroborations`: the live entity records that list one of the ticker's direct signals and have no live ticker record of that ticker on the same `entity_key`, each with a `reason` (`broad_entity`, else `no_independent_pair_for_ticker`), without a score.

The dashboard shows the context list under the corroborations on the signals dashboard and the company detail page, each row with its reason (*context list*).

`Company.ticker` is today's SEC mapping (HUB-034), not the ticker as of the publication date; that limit is unchanged and recorded in Notes.

### 5. Future dates

- **core-hub gate.** A scan reads only pending signals that are eligible, and builds episodes only from eligible signals. A signal dated in the future stays pending, takes part in nothing, and is read by the first scan after its date has passed. With the two `CHECK` constraints, no record can carry a `corroborated_at` after the scan that wrote it or before a participant was public.
- **PubMed date.** `published_date` is the earliest of the electronic article date and the date the record entered PubMed (`PubMedPubDate` with `PubStatus` `pubmed`, else `entrez`), never the journal issue date and never later than `retrieved_at`; with neither date it is `retrieved_at`. A missing day or month is no longer filled in from an issue date. The three signals already stored with a future date are not rewritten (the archive holds the title and abstract, not the dates); the gate holds them until their date.

### 6. Rules sync, and the rebuild on deploy

`corroboration_rules_state` holds one row: the rules hash core-hub last applied and when. On every start, before any scan:
- when the stored hash equals the file's, the sync does nothing;
- otherwise it sets `corroboration_key` on every `GeneTarget` and `Mechanism` node, then marks every `Signal` pending with a fresh write token, in batches of `corroboration.rules-sync-batch-size`, then stores the new hash. It is restartable: the hash is stored last, so a sync that failed runs again in full.

A scan does nothing while the stored hash differs from the file's, so no scan ever runs on a half-keyed graph. After the sync, ordinary scans reconcile every entity, which brings every record under the new rules; no clock is involved (COR-011) and nothing is cleared before its commit (COR-010).

The Flyway migration for this spec (the next free version) empties `corroboration`, adds `ticker`, `episode_opened_at`, `excluded_reason` and `published_at`, changes the primary key to the record key, adds the two `CHECK` constraints and a GIN index on `participant_event_ids`, and creates `corroboration_rules_state`. The 495 rows written under the old definition are derived data that no backtest and no `paper` strategy has used; they are rebuilt from the graph by the first sync. There is no script (OPS-009): the migration and the sync run on `docker compose up`.

### 7. Backtest agreement

`_corroborations` in `backtest/runner.py` is replaced by a Python port of `EpisodeBuilder` and of the rules loader (`auspex_backtesting.backtest.episodes`), applied per canonical gene-target key and ticker to the events that carry that ticker, which is exactly a ticker scope. A backtest event fires at an episode's `episode_opened_at`, and the full variant's weight uses the participants published by then. `BacktestEvent` gains `title`. Both implementations read one case file, `services/core-hub/src/test/resources/corroboration/episode-cases.json` (key cases and episode cases with their expected output), so core-hub and the backtest cannot drift apart silently.

### 8. Rules lock

`config/corroboration/entity-rules.yaml` is registered in `config/hypotheses/registry.jsonl` under the id `corroboration_rules` by `scripts/register_hypothesis.py` (hash of its bytes, as EVA-001). Every event evaluation path refuses, before it reserves or reads anything, a rules file whose bytes differ from its latest registration or that was never registered, and records the rules hash in its result. Portfolio evaluations do not read the file. A change to the file is a new registry line with a `DECISIONS.md` entry (EVA-006).

### 9. Wire fixture and the strategy runtime

- A unit test generates `corroborated_event_v1.json` in `services/core-hub/src/test/resources/contract/` from the Java record and fails when the committed file differs (CON-034).
- `CorroboratedSignal.from_json` reads `ticker`, `source_types` and `episode_opened_at`; the runtime builds its record from them and the `ticker_for` lookup is removed (STR-024). An event with an empty ticker is skipped and counted as skipped, never as a strategy failure (*ticker-less event*). The runtime's event identity includes the ticker.

### 10. Review tooling

`sample_corroborations.py` samples live ticker records only, a given number per entity label (`--per-label`, default 50), deterministic for a seed, each with its participants' titles, snippets, sources and the ticker. `score_corroboration_review.py` judges each stratum against the bar of 0.85 on the statement "these signals report the same specific finding about the same entity, and the attached ticker is that finding's company", fails when any stratum is below it, and reports a stratum with fewer rows than the minimum as `insufficient` (a failure) (*stratified review*).

## Out of scope

- **Company-node identity** (`CRISPR Therapeutics` against `CRISPR Therapeutics AG`; HUB-034, HUB-035). It changes which ticker a company node carries, not what corroborates.
- **The score.** COR-013's formula, its clock and any new term. Its input count changes (part 2); nothing else does.
- **Extraction emitting fewer, more specific mechanisms.** 876 of 883 signals carry a mechanism, two to three per literature signal; that is a prompt change with its own gate.
- **A company-program kind, `Program` nodes, a configurable window, an `as_of` score and the degree-cap report.** They stay in `specs/company-program-corroboration.md`.
- **The degree cap** and `corroboration.scan-batch-size`.
- **The runtime's trigger policy**: whether a strategy acts on an extension record. The event carries what a strategy needs to decide.
- **Un-suspending or re-registering `h1`, `h4` or `h6`**, and any backtest of corroboration events.
- **Point-in-time tickers.** `Company.ticker` stays today's SEC mapping.
- **The other divergence on ING-008** (PubMed's canonical id declaration).

## Constraints

- INV-5, COR-001: everything stays behind `CorroborationService`, and `CorroborationServiceContractTest` passes unmodified. Its diff must be empty. Its helpers create entity nodes with no `corroboration_key` and signals with no title; the scan keys such nodes itself and a missing title is never the same finding, so every case holds under the new rules. If a case cannot pass unmodified, stop and flag.
- INV-2: core-hub is the only writer of both stores; the sync and the scan are core-hub code. INV-10: the record key. INV-12, HUB-027: every new SQL and Cypher statement binds its values, and the ArchUnit rule covers the new classes. INV-14: `event_id` is untouched. INV-16, RES-067: no processing-time field decides an episode; `first_detected_at` stays diagnostic (COR-006).
- HUB-019, HUB-020: one new migration, never an edit to an applied one. HUB-026: every transaction names its manager. HUB-023, HUB-031: no new relationship type; entity nodes are still merged on `name`.
- COR-010, COR-014: commit after acknowledged sends, clear after commit by write token, failures counted. COR-006: nothing joins or filters on `first_detected_at`; the `CHECK` constraint only bounds it.
- CON-029, CON-031: the new event fields are additive; record, fixture and Python reader change in one PR.
- ENG-005: the clock is injected (`java.time.Clock`); no test sleeps. ENG-006: one Spring context, no `@DirtiesContext`; a rules change in a test calls the sync with other rules.
- Values in files, not in constants: the rules in `config/corroboration/entity-rules.yaml`, batch sizes in `application.yml`. The docs name the keys and never copy the lists.
- Integration tests read a small rules file of their own under `src/integrationTest/resources/corroboration/`, so an edit to the production list cannot break them; one unit test pins the production file.
- `docs-check.toml` gets an ownership rule for `config/corroboration/**` (domains `core-hub` and `research`).
- No name carries this spec's title or a plan step (ENG-049): classes are `EntityRules`, `IndependentSources`, `EpisodeBuilder`, `CorroborationReconciler`, `CorroborationRulesSync`.
- Trap: Neo4j does not index nulls, so "nodes without a key" is found through the pending signals' own entity nodes, never by a label scan per scan.
- Trap: the two existing unit tests that assert one group per trigger (`CorroborationScannerTest`) describe the retired COR-005; rewrite them against the reconciler and list them in the PR body.

**Docs amendment (do this first, in the same PR as the code).** Edit the owner docs as Docs impact lists, with IDs from `python3 -m tools.docs_check --next <NS>`, retired IDs moved to `Retired requirements` (ENG-021), and verification rows naming the tests below. Each edit cites `## 2026-11-14 — Corroboration quality — CHOICE — the eight amendments approved as recommended`, which answers these `PENDING` entries:

| Amendment | `PENDING` entry |
|---|---|
| *entity rules*, *exclusion*, COR-004 | `## 2026-11-14 — Corroboration quality — PENDING — broad entities and synonyms from one rules file` |
| *independence*, COR-003, COR-013's input | `## 2026-11-14 — Corroboration quality — PENDING — independent sources, not source types` |
| *episode*, *record key*, *backtest episode*, COR-005, COR-007, COR-009, COR-012, CON-025, CON-032 to CON-034, RES-067, RES-071 | `## 2026-11-14 — Corroboration quality — PENDING — one record per episode` |
| *ticker record*, *ticker response*, *context list*, *ticker-less event*, HUB-046, STR-024 | `## 2026-11-14 — Corroboration quality — PENDING — a ticker attaches through two independent sources` |
| COR-011, *PubMed date*, ING-011 | `## 2026-11-14 — Corroboration quality — PENDING — no corroboration dated in the future` |
| *rules sync*, COR-008, HUB-030, HUB-032, the emptied table | `## 2026-11-14 — Corroboration quality — PENDING — records rebuilt when the rules change` |
| *rules lock* | `## 2026-11-14 — Corroboration quality — PENDING — rules file locked for event evaluations` |
| *stratified review*, EXT-018 | `## 2026-11-14 — Corroboration quality — PENDING — stratified hand review of ticker records` |

The approved episode rule supersedes `## 2026-10-07 — Backtest look-ahead fix — CHOICE — one backtest event per corroboration, not per superseding record`; the approving `CHOICE` says so, and the old entry is not edited (ENG-033).

## Required tests

Write these first and see each fail for the right reason (ENG-001). Names are claims; the requirement each verifies follows the dash.

### core-hub, unit (`./gradlew test`), 34

`corroboration/EntityRulesTest`:
- `geneTargetKeyIsUpperCasedWithSeparatorsRemoved` — *entity rules*
- `mechanismKeyIsLowerCasedWithPunctuationAsOneSpace` — *entity rules*
- `synonymVariantResolvesToItsCanonicalKey` — *entity rules*
- `everySharedKeyCaseProducesItsExpectedKey` — *entity rules* (reads `episode-cases.json`)
- `excludedEntityIsReportedWithTheBroadEntityReason` — *exclusion*
- `rulesFileWithAVariantUnderTwoCanonicalKeysIsRefused` — *entity rules*
- `rulesFileWithANameNotInCanonicalFormIsRefused` — *entity rules*
- `rulesFileNamingAnUnknownSourceTypeIsRefused` — *entity rules*
- `committedRulesFileLoadsAndExcludesTheSixMechanismsSeenInLiveData` — *exclusion*
- `rulesHashIsTheSha256OfTheFileBytes` — *entity rules*

`corroboration/IndependentSourcesTest`:
- `twoSignalsOfOneSourceTypeCountAsOneSource` — *independence*
- `preprintAndItsPaperWithMatchingTitlesCountAsOneSource` — *independence*
- `preprintAndAnUnrelatedPaperCountAsTwoSources` — *independence*
- `secondUnrelatedPaperBesideAPreprintAndItsPaperRestoresTheSecondSource` — *independence*
- `matchingTitlesAcrossAPairTheRulesDoNotListStayTwoSources` — *independence*
- `signalWithoutATitleIsNeverTheSameFinding` — *independence*
- `titleOverlapJustBelowTheThresholdIsNotTheSameFinding` — *independence*

`corroboration/EpisodeBuilderTest`:
- `everySharedEpisodeCaseProducesItsExpectedEpisodes` — *episode* (reads `episode-cases.json`)
- `signalWithinTheWindowAfterTheOpeningJoinsTheEpisode` — *episode*
- `signalExactlyOneWindowAfterTheOpeningStillJoins` — *episode*
- `signalAfterTheWindowOpensNothingWithoutTwoFreshSources` — *episode*
- `everySignalBelongsToAtMostOneEpisode` — *episode*
- `candidateOlderThanTheWindowIsDroppedBeforeAnOpening` — *episode*
- `openingTimeIsThePublicationOfTheSignalThatCompletedTheFirstIndependentPair` — *episode*
- `arrivalOrderDoesNotChangeTheEpisodes` — *episode*, COR-011

`corroboration/CorroborationReconcilerTest`:
- `excludedEntityRecordIsWrittenWithItsReasonAndNotSent` — *exclusion*, COR-012
- `excludedEntityProducesNoTickerRecord` — *ticker record*
- `tickerRecordNeedsTwoIndependentSourcesNamingThatTicker` — *ticker record*
- `recordAlreadyPublishedIsNotSentAgain` — COR-012
- `scanReadsOnlyPendingSignalsPublishedByNow` — COR-009, COR-011
- `scanDoesNothingWhileTheAppliedRulesHashDiffersFromTheFile` — *rules sync*

`corroboration/CorroborationRulesSyncTest`:
- `syncDoesNothingWhenTheAppliedHashMatches` — *rules sync*
- `syncKeysEntitiesThenMarksSignalsPendingThenStoresTheHash` — *rules sync*, COR-008

`config/CorroboratedWireFormatTest`:
- `committedCorroboratedFixtureEqualsTheGeneratedOne` — CON-032, CON-034 (asserts `ticker`, `source_types`, `episode_opened_at`, `schema_version`)

### core-hub, integration (`./gradlew integrationTest`), 17, plus the contract test unmodified

`CorroborationEpisodeIT`:
- `overlappingGroupsOnOneEntityLeaveOneLiveRecord` — *episode* (five signals in one window, written across three scans)
- `joiningSignalSupersedesTheRecordAndIsPublishedOnce` — *episode*, COR-012
- `signalAfterTheEpisodeWindowOpensASecondRecordOnlyWithTwoFreshSources` — *episode*
- `spellingVariantsOfOneMechanismCorroborateUnderOneEntityKey` — *entity rules*, COR-004
- `broadMechanismRecordIsStoredExcludedAndNeverPublished` — *exclusion*, COR-012
- `preprintAndItsPaperAloneProduceNoRecord` — *independence*
- `futureDatedSignalIsHeldUntilItsDateThenCorroborates` — COR-011 (the test clock is moved, nothing sleeps)
- `recordDatedAfterItsDetectionIsRefusedByTheTable` — *episode* (`CHECK` constraints)
- `reExtractionThatDropsTheEntitySupersedesItsRecord` — COR-009, HUB-037
- `commitFailingAfterAnAcknowledgedSendPublishesAgainOnTheNextScan` — COR-012, CON-033

`TickerCorroborationIT`:
- `twoIndependentSourcesNamingOneCompanyProduceATickerRecord` — *ticker record*
- `companyNamedByOneParticipantGetsNoTickerRecord` — *ticker record*
- `tickerRecordOpensWhenTheSecondSourceNamingTheCompanyIsPublished` — *ticker record*
- `tickerEndpointReturnsOnlyThatTickersRecords` — *ticker response*
- `tickerEndpointListsContextCorroborationsWithTheirReason` — *ticker response*

`CorroborationRulesSyncIT`:
- `syncWithChangedRulesRekeysEntitiesAndRebuildsRecords` — *rules sync*
- `entityNewlyExcludedKeepsItsRecordExcludedAndSupersedesItsTickerRecords` — *rules sync*, *exclusion*

`CorroborationServiceIT` (which extends `CorroborationServiceContractTest`) passes with the contract file unchanged — COR-001.

### backtesting, unit, 10

`tests/unit/test_backtest_episodes.py`:
- `test_shared_key_cases_produce_their_expected_keys` — *entity rules*
- `test_shared_episode_cases_produce_their_expected_episodes` — *backtest episode*
- `test_backtest_event_fires_at_the_episode_opening_not_at_a_later_joiner` — *backtest episode*, RES-067
- `test_joiner_evidence_is_not_reused_to_open_the_next_event` — *backtest episode*
- `test_excluded_entity_produces_no_backtest_event` — *backtest episode*
- `test_preprint_and_its_paper_alone_produce_no_backtest_event` — *backtest episode*

`tests/unit/test_corroboration_rules_lock.py`:
- `test_event_evaluation_refuses_an_unregistered_corroboration_rules_file` — *rules lock*
- `test_event_evaluation_refuses_corroboration_rules_changed_since_registration` — *rules lock*
- `test_event_result_records_the_corroboration_rules_hash` — *rules lock*
- `test_portfolio_evaluation_never_reads_the_corroboration_rules` — *rules lock*

### ingestion-scraper, unit, 7

`tests/unit/test_academic_papers.py`:
- `test_pubmed_published_date_is_never_the_journal_issue_date` — *PubMed date*
- `test_pubmed_without_an_electronic_date_uses_the_date_it_entered_pubmed` — *PubMed date*
- `test_pubmed_published_date_is_never_after_retrieval` — *PubMed date*, ING-009

`tests/unit/test_sampling.py`:
- `test_sample_draws_the_requested_count_per_entity_label_from_ticker_records` — *stratified review*
- `test_sample_is_identical_for_the_same_seed` — *stratified review*
- `test_review_fails_when_one_stratum_is_below_the_bar_though_the_pooled_precision_passes` — *stratified review*
- `test_review_reports_a_stratum_below_the_minimum_row_count_as_insufficient` — *stratified review*

### strategy, unit, 3

`tests/unit/test_runtime_components.py`:
- `test_runtime_reads_ticker_and_source_types_from_the_corroborated_fixture` — STR-024, CON-034 (reads `corroborated_event_v1.json` by path)
- `test_runtime_skips_a_ticker_less_event_without_counting_a_strategy_failure` — *ticker-less event*
- `test_same_participants_under_two_tickers_are_two_events` — CON-033

### dashboard, 2

`src/__tests__/SignalsDashboard.test.tsx` and `src/__tests__/CompanyDetail.test.tsx`:
- `lists context corroborations with their reason` — *context list* (one in each file)

### Mutation checks (ENG-011)

Each on a local copy, each turning a named test red: count source types instead of independent participants; let a signal join after the window; reuse a closed episode's participant as a candidate; send an excluded record; build a ticker scope from every signal of the entity; read pending signals without the eligibility filter; store the rules hash before marking signals pending; drop the ticker from the record key; take the PubMed issue date; score the review pooled.

## Definition of done

Part 1, code (CI proves the Gradle lines; cloud sessions have no Maven Central or Docker):

```bash
cd services/core-hub && ./gradlew test --rerun-tasks && ./gradlew integrationTest --rerun-tasks
git diff --exit-code origin/develop -- src/integrationTest/java/dev/auspex/corehub/CorroborationServiceContractTest.java
cd ../backtesting && uv run ruff check . && uv run mypy src && uv run pytest tests/unit -q
cd ../ingestion-scraper && uv run ruff check . && uv run mypy src && uv run pytest tests/unit -q
cd ../strategy && uv run pytest tests/unit -q
cd ../dashboard && npm ci && npm run lint && npx tsc --noEmit && npm run test:ci
cd ../.. && python3 -m tools.docs_check --base origin/develop
```

Expected: 34 new unit and 17 new integration tests pass in core-hub beside the existing suites, with a non-zero count in `build/reports/tests/` for both tasks; the contract test's diff is empty; 10 new tests pass in backtesting, 7 in ingestion-scraper, 3 in strategy, 2 in the dashboard; `docs_check: clean`. The owner docs carry the amendments, `COR-012`, `CON-033`, `CON-034` and `STR-024` read `tested`, and `services/core-hub/README.md` describes the new record. Then the spec's status is `blocked` on part 2.

Part 2, on the stack machine, by a session the owner starts there. Query Postgres with `docker exec auspex-postgres psql -U "$POSTGRES_USER" -d auspex -c '…'` and Neo4j through its HTTP API on `localhost:7474` (`POST /db/neo4j/tx/commit`). Never run `cypher-shell` inside the Neo4j container: its JVM shares Neo4j's 768 MB limit and it OOM-killed Neo4j on 2026-11-07. The rebuild is the migration and the sync on `docker compose up`, never a script.

1. Rebuild and start core-hub. Expected: the migration applies, the log shows one rules sync, `corroboration_rules_state` holds the file's SHA-256, and within a few scans no eligible signal is pending.
2. Structural gates, each with its expected value:

| Gate | Query | Expected |
|---|---|---|
| No counted record on a broad entity | live rows with `excluded_reason IS NULL` whose `entity_key` is in the file's `excluded` list | 0 |
| No ticker record on a broad entity | live rows with `ticker <> ''` and `excluded_reason IS NOT NULL` | 0 |
| No excluded record was sent | rows with `excluded_reason IS NOT NULL` and `published_at IS NOT NULL` | 0 |
| No split entity | live rows whose `entity_key` name part is not its own canonical key (the six pairs of Context by name, and `split_part(entity_key, ':', 1) ~ '[^[:alnum:] ]'`); entity nodes linked to a signal with no `corroboration_key` | 0 and 0 |
| One live record per episode | pairs of live rows with equal `(entity_key, ticker)` that share a participant (`&&`), or whose `episode_opened_at` lie within 90 days | 0 |
| Nothing dated in the future | live rows with `corroborated_at > first_detected_at` or `corroborated_at > now()`; live rows with a participant whose `published_date` is after `corroborated_at` | 0 and 0 |
| Every ticker is earned | live ticker records where fewer than two participants of different `source_type` mention a company carrying that ticker, or where any participant does not | 0 |
| Independent sources | live rows with `distinct_source_count < 2` | 0 |
| Nothing read yet | `config/hypotheses/trials/` in the repository at the deployed commit | absent |

3. Reported, not gated, in the `VERIFIED` entry: live rows by label, by scope and by `excluded_reason`; how many of the former bioRxiv + PubMed-only rows survive; signals held for a future date; and live ticker records per month of `episode_opened_at` with the number of distinct tickers, which is what a backtest would see.
4. Candidate report, not a rule: every entity whose eligible signals mention companies carrying five or more distinct tickers, or that is on 2% or more of all signals, and is not excluded. The owner decides additions; an addition is a PR that edits the rules file and registers it again, and the sync rebuilds on the next start. Run the report again after the historical backfill.
5. Hand review. `sample_corroborations.py --seed <seed> --per-label 50` on the live ticker records; the session labels each row against its participants' text on the statement of part 10 and scores it with `score_corroboration_review.py`. Passes at 0.85 or more in each stratum, the bar of the protocol's `mapping_quality` criterion. A stratum with fewer than 50 rows is `insufficient`: the spec stays `blocked` until the stratum fills or the owner decides.
6. `DECISIONS.md`: one `VERIFIED` entry with the gate values, the report, the seed, the per-stratum result and the rules hash, and the owner's sign-off as a `CHOICE`. Then the spec is `done` (ENG-016).

## Compatibility

- Every existing corroboration row is replaced on the first start, and the rebuilt records are published as new events. The strategy runtime has no `paper` strategy and its strategies are `draft` or suspended, so nothing trades on them; its stored history keeps the old events, which no strategy reads.
- `GET /api/v1/signals/{ticker}` keeps `corroborated_signals` but with fewer rows, and adds `context_corroborations`. Additive for the dashboard, which this spec updates.
- Event consumers that ignore unknown fields keep working (CON-029); the runtime is updated in the same PR.
- Backtests run before this change replayed with the old rule. None has been recorded (Context), so no result changes meaning.
- `specs/company-program-corroboration.md` is edited in this spec's scoping PR: the `tickers` array and the `mechanism_only` flag it proposed are replaced by this spec's ticker records and exclusion, and it is blocked by this spec.

## Rollback

Revert the PR and add one migration that restores the old table shape (an applied migration is never edited, HUB-020). The old scanner marks nothing pending by itself, so the old rows come back only as signals are written again; restoring `corroboration` from the nightly backup (`docs/backup-restore.md`) brings them back at once. `corroboration_key` on entity nodes is ignored by the old code. The rules file's registry line stays (the registry is append-only).

## Notes

- **Why one spec.** The rules file, the independence count, the episode and the ticker scope define one thing, the event. Landing them apart would leave core-hub and the backtest disagreeing between merges. A session that cannot finish in one sitting stops after a build part and writes a Handoff (ENG-028); the order is: docs amendment, rules and keys, independence, episodes and reconcile, ticker records and REST, sync and migration, backtest port and lock, PubMed date, wire fixture and runtime, review tooling, dashboard.
- **Why this episode rule and not a chain.** A chain (each signal within the window of the next) never closes on a busy entity: `DMD` would be one episode for years and one backtest event ever. Tiling by an anchor at the first signal splits pairs that are days apart. Opening on the completing signal and closing one window later keeps every participant within the window of the opening signal, re-opens only on fresh evidence, and is a function of publication dates alone.
- **Why ticker scopes and not a ticker list on the entity record.** A list would date the ticker by the entity's opening, before the second company-naming source was public. A ticker scope gives each ticker its own opening time and makes "every record that names a ticker satisfies the rule" true by construction. It is also what the backtest already did per gene target and ticker.
- **STR-024 is carried here**, against the earlier plan to leave it to company-program corroboration, because the ticker is now part of the record key and the event identity; adding the source types is one more field.
- **Thresholds were set from data quality alone**: the window is today's, the title overlap of 0.8 and the list are not tuned on returns, and no return has been read. The candidate report can only add to the list, by an owner decision.
- **Known limits kept**: a ticker is today's SEC mapping; a same-finding match needs titles and catches only the pairs the file lists; authors and bioRxiv's own link to the published paper are not on the event (a wire change, left for later).
- **Extraction specificity** deserves its own spec: fewer, more specific mechanisms would shrink the excluded list.
- `specs/core-hub-input-health.md` is not affected.
