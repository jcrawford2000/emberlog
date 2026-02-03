# Feature Tracker

Seeded from code TODOs and `docs/CURRENT_STATE.md`, `docs/REQUIREMENTS.md`, `docs/DESIGN.md`.

## [Done] Align sink contracts (worker -> JSON/API/Ledger)
- Summary: Normalized worker payloads and hardened `LedgerSink` field extraction for dict incidents.
- Acceptance criteria: `JsonFileSink` and `LedgerSink` receive consistent typed payloads; tests verify non-null transcript + expected ledger fields.
- Components touched: `emberlog/worker/consumer.py`, `emberlog/io/ledger_sink.py`, `tests/test_json_sink_contract.py`, `tests/test_ledger_sink_contract.py`.
- Notes / risks: Future sink additions should follow the same payload contract to avoid regression.

## [Planned] Reorder sink execution for local-first durability
- Summary: Persist locally before external API call so API outages do not drop local records.
- Acceptance criteria: With API down, JSON + ledger still persist; failed API status is observable/retryable.
- Components touched: `emberlog/io/composite.py`, `emberlog/worker/consumer.py`, `emberlog/io/api_sink.py`.
- Notes / risks: May change operational semantics if API-first was intentional.

## [Done] Respect dated output paths in JSON sink
- Summary: `JsonFileSink` now honors `out_dir` to write JSON to the expected dated path.
- Acceptance criteria: Output files land under expected dated path (`YYYY/M/D/...`) in outbox; test added.
- Components touched: `emberlog/io/json_sink.py`, `tests/test_json_sink_contract.py`.
- Notes / risks: Existing flat paths remain supported when `out_dir` is not provided.

## [In Progress] Replace hardcoded processed paths with settings
- Summary: Remove `/data/emberlog/*` path coupling in processed file move logic.
- Acceptance criteria: Processed moves use configurable inbox/processed paths in all environments.
- Components touched: `emberlog/state/processed_index.py`, `emberlog/config/config.py`.
- Notes / risks: In progress - demo uses injected paths, but standard defaults still point at `/data/...`.

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

## [Done] Deterministic demo mode (no GPU/API by default)
- Summary: Added `poetry run emberlog demo` using fixture WAVs + stub transcript backend with local-only outputs.
- Acceptance criteria: Demo creates JSON + ledger outputs locally, is idempotent across runs, and does not construct API sink by default.
- Components touched: `emberlog/app/main.py`, `emberlog/transcriber/stub.py`, `emberlog/transcriber/factory.py`, `emberlog/state/processed_index.py`, `tests/test_demo_mode.py`, `samples/*`, `docs/DEV_QUICKSTART.md`.
- Notes / risks: API integration in demo is opt-in (`--with-api`) and still depends on external service availability.
