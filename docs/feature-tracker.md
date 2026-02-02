# Feature Tracker

Seeded from code TODOs and `docs/CURRENT_STATE.md`, `docs/REQUIREMENTS.md`, `docs/DESIGN.md`.

## [In Progress] Align sink contracts (worker -> JSON/API/Ledger)
- Summary: Normalize payload types between `worker.consumer` and sink interfaces to avoid missing/incorrect fields.
- Acceptance criteria: `JsonFileSink` and `LedgerSink` receive consistent typed payloads; integration test verifies non-null transcript + expected ledger fields.
- Components touched: `emberlog/worker/consumer.py`, `emberlog/io/json_sink.py`, `emberlog/io/ledger_sink.py`, `emberlog/io/base.py`.
- Notes / risks: Backward compatibility with existing output JSON shape may break.

## [Planned] Reorder sink execution for local-first durability
- Summary: Persist locally before external API call so API outages do not drop local records.
- Acceptance criteria: With API down, JSON + ledger still persist; failed API status is observable/retryable.
- Components touched: `emberlog/io/composite.py`, `emberlog/worker/consumer.py`, `emberlog/io/api_sink.py`.
- Notes / risks: May change operational semantics if API-first was intentional.

## [Planned] Respect dated output paths in JSON sink
- Summary: Ensure worker-provided `out_dir` (dated tree) is actually used when writing JSON.
- Acceptance criteria: Output files land under expected dated path (`YYYY/M/D/...`) in outbox.
- Components touched: `emberlog/io/json_sink.py`, `emberlog/worker/consumer.py`.
- Notes / risks: Migration/lookup for previously flat output filenames.

## [Planned] Replace hardcoded processed paths with settings
- Summary: Remove `/data/emberlog/*` path coupling in processed file move logic.
- Acceptance criteria: Processed moves use configured inbox/processed paths in all environments.
- Components touched: `emberlog/state/processed_index.py`, `emberlog/config/config.py`.
- Notes / risks: Existing deployments may rely on current hardcoded path behavior.

## [Planned] Resolve Whisper env naming inconsistency
- Summary: Align `.env.example` (`WHISPER_*`) and settings loader (`EMBERLOG_WHISPER_*`).
- Acceptance criteria: Single documented convention works for app and utility script; docs updated.
- Components touched: `.env.example`, `emberlog/config/config.py`, `emberlog/transcriber/whisper_fast.py`, `emberlog/utils/transcribe.py`, `docs/CURRENT_STATE.md`.
- Notes / risks: Breaking existing local env files if renamed without fallback aliases.

## [Blocked] End-to-end integration with live API/SSE/UI
- Summary: Validate full system path including notify/UI behavior.
- Acceptance criteria: `emberlog` -> `emberlog-api` persistence + SSE -> `emberlog-web` verified in integration environment.
- Components touched: cross-repo (`emberlog`, `emberlog-api`, `emberlog-web`).
- Notes / risks: Blocked because API and web runtimes are separate repos/environments.

## [On Hold] Production observability (metrics/tracing/alerts)
- Summary: Add non-log observability for latency, error rate, queue depth, and sink outcomes.
- Acceptance criteria: Metrics emitted and alerting thresholds defined for worker failures and backlog growth.
- Components touched: `emberlog/app/main.py`, `emberlog/worker/consumer.py`, deployment/infra (external).
- Notes / risks: Depends on platform-standard telemetry stack selection.

## [Done] Core worker pipeline baseline
- Summary: Watcher -> queue -> worker -> transcribe -> parse -> sink flow is implemented and documented.
- Acceptance criteria: Existing smoke test passes for dummy backend path.
- Components touched: `emberlog/watch/*`, `emberlog/queue/*`, `emberlog/worker/*`, `emberlog/transcriber/*`, `tests/test_smoke_pipeline.py`.
- Notes / risks: Smoke coverage is narrow; real backend/API paths still need broader integration tests.
