# Implementation Notes

## Execution Issues Encountered

### 1. Legacy SQLite compatibility broke history search

- Symptom: history queries failed against older local databases with errors such as missing `topics_json` or even missing `digest_entries`.
- Cause: read paths assumed the new schema already existed, but older state files were created before topic/report metadata was added.
- Resolution: `DigestStorage.search_items()` now calls `initialize()` before querying, so read-time migration adds missing columns and tables.

### 2. Topic reports require topic metadata to exist in the digest input

- Symptom: `--write-topic-reports` may produce only the main digest output when the input JSON has no `topics` field on entries.
- Cause: topic reports are grouped from entry-level topic metadata rather than inferred at render time.
- Current status: expected behavior. API mode and enriched JSON inputs now populate topics, but legacy example inputs may still skip topic report generation.

### 3. Live-query enrichment has test coverage but not a live API verification in this session

- Symptom: the `--summarize-live-query` path was not exercised against a real OpenAI API response during implementation.
- Cause: avoiding unrequested external API spend and dependency on runtime credentials.
- Current status: covered by unit tests with structured fake responses. Real API validation remains a recommended manual follow-up.

### 4. Older state databases do not automatically backfill event records

- Symptom: `--event-query` can return no results against databases created before the dedicated `events` table was introduced.
- Cause: event records are now persisted during digest-entry recording, but existing historical runs are not backfilled automatically.
- Current status: expected behavior for now. Re-running a digest or explicitly rebuilding demo state populates the event layer.

## Phase 2 Progress

- Added lightweight event metadata extraction fields: `event_type`, `topics`, and `entities`.
- Added filtered history retrieval by topic, source, entity, and date range.
- Added entity timeline retrieval as the first explicit `Entity Tracking` slice.
- Added a formal `EventRecord` query path for persisted digest outputs via `--event-query`.
- Event records are now persisted into a dedicated `events` table during digest entry recording instead of being derived on every query.
- Event records now include `confidence` and `why_it_matters` for richer event-level interpretation.
- Added explicit event backfill support plus a lightweight JSON API surface for `/events`, `/entities`, and `/topics`.
- Added an event-detail endpoint plus a minimal local dashboard served from `/`.

## Remaining Phase 2 Tasks

- Expand `Event Extraction` beyond the current lightweight schema, for example with structured evidence or impact fields.
- Add deeper retrieval controls such as hybrid ranking or topic/entity co-ranking beyond `published_at` and `confidence`.
- Add more complete event fields such as structured evidence snippets, impacted scope, or confidence provenance.
- Add richer dashboard interactions such as drill-down charts, topic/entity navigation history, or report linking.

## Phase 3 Progress

- Added a first `Research Mode` slice that builds a research plan and markdown report from persisted events.
- Added optional live-search enrichment for research mode through `--research-live`.
- Added markdown export for research reports through `--research-output`.
- Research reports are now persisted and available through `/research/reports` and `/research/report`.
- The local dashboard now surfaces saved research reports alongside events, entities, and topics.
- Added `/research/run` so research generation is available through the API layer as well as the CLI.
