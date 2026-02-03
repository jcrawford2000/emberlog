# Emberlog Design

This document describes the current/target design for the `emberlog` worker service, based on `docs/CURRENT_STATE.md` and `docs/REQUIREMENTS.md`.

## 1) High-Level Architecture

```text
                    (separate repo)                  (separate repo)
+----------------+     REST/SSE     +---------------------------+     SSE/REST     +----------------+
|   emberlog     | ----------------> |       emberlog-api       | <--------------> |  emberlog-web  |
| (this repo)    |                   | (API + Postgres + SSE)   |                  |   frontend     |
+----------------+                   +---------------------------+                  +----------------+
        |
        | local pipeline
        v
+----------------+   +----------------+   +----------------+   +----------------------------+
| DirectoryWatch |-> | InMemoryQueue  |-> | Worker(s)      |-> | Sinks: API -> JSON -> SQL |
+----------------+   +----------------+   +----------------+   +----------------------------+
        |                                                            |
        | dedupe index                                                +--> external API POST
        v                                                            +--> local JSON files
+----------------------+                                             +--> local SQLite ledger
| ProcessedIndex (SQL) |
+----------------------+
```

## 2) End-to-End Data Flow (Ingest -> Persistence/Notification)

1. `emberlog.app.main` loads settings, starts `DirectoryWatcher`, creates `InMemoryJobQueue`, and starts worker tasks.
2. Watcher accepts audio files matching extension + dated path (`YYYY/M/D/...`), performs stability check, and enqueues `Job`.
3. `ProcessedIndex` is checked before enqueue to avoid re-processing known files.
4. Worker dequeues job and transcribes via configured backend (`dummy`, `stub`, or `faster_whisper`).
5. Transcript is split into dispatches (`segmentation.splitter`).
6. Each dispatch is cleaned/parsed (`cleaning.cleaner`) into normalized fields.
7. `CompositeSink` runs sinks in order:
   - `ApiSink`: POST incident payload to external API (`emberlog-api`).
   - `JsonFileSink`: write local per-dispatch JSON.
   - `LedgerSink`: write local SQLite ledger row (idempotent hash).
8. Worker marks source as processed and source audio is moved to processed storage.
9. Notification/UI path is external: downstream API (`emberlog-api`) provides SSE/REST to `emberlog-web`.

Demo mode variant (`poetry run emberlog demo`):

- Stages fixture WAVs into a local run inbox under `out/demo/inbox/...`.
- Uses `StubFixtureTranscriber` to read deterministic transcript fixtures.
- Runs JSON + ledger sinks by default (API sink only with `--with-api`).
- Writes only repo-local outputs under `out/demo/`.

## 3) Module/Service Responsibilities

- `emberlog/app/main.py`: process supervisor, startup/shutdown orchestration.
- `emberlog/watch/watcher.py`: filesystem watch + startup scan + queue enqueue.
- `emberlog/queue/*`: async queue abstraction and in-memory implementation.
- `emberlog/worker/consumer.py`: job execution loop, retry/backoff, sink invocation.
- `emberlog/transcriber/*`: backend selection and transcription engines.
- `emberlog/segmentation/splitter.py`: split transcript stream into dispatch items.
- `emberlog/cleaning/cleaner.py`: parsing/normalization (units/channel/type/address).
- `emberlog/io/*`: output adapters (API, JSON, ledger, composite sequencing).
- `emberlog/ledger/ledger.py`: local SQLite ledger schema/init + read/write helpers.
- `emberlog/state/processed_index.py`: local SQLite processed-file index + move semantics.
- `emberlog/api/client.py`: outbound API client models and transport.

## 4) Database Schema Summary

Datastores currently involved:

1. Local SQLite: processed index
- File: under outbox `.state/processed.sqlite`.
- Table: `processed(fingerprint, path, size, mtime_ns, processed_at)`.
- Purpose: dedupe and processed tracking.

2. Local SQLite: dispatch ledger
- File: `settings.ledger_path` (default `/data/emberlog/ledger.jsonl`, but runtime code uses it as SQLite DB path).
- Table: `dispatches(id, audio_path, out_path, started_s, ended_s, channel, units_json, type, address, written_at, sha256 UNIQUE)`.
- Purpose: local persistence and idempotent dispatch history.

3. External Postgres (separate repo context)
- SQL draft exists at `emberlog/db/schema.sql`.
- Intended target: `incidents` model for API-backed persistence/search.
- Status: external/system-level, not runtime-owned by this repo.

## 5) Error Handling Strategy (Current)

- Worker loop catches broad exceptions per job.
- Retry model: increment attempts, sleep with quadratic backoff, requeue until `max_attempts`.
- Queue accounting: `task_done()` called in `finally` to avoid queue deadlock.
- Watcher stability check ignores files that disappear before enqueue.
- API client raises HTTP errors on non-2xx responses; worker handles via retry path.
- Graceful shutdown: signal-triggered stop, watcher stop, `queue.join()`, worker task cancel.

## 6) Gaps / Refactors

Current implementation mismatches or design risks relative to intended behavior:

1. Sink contract/data mismatch
- Mostly resolved: worker now passes a structured `Transcript` object and explicit `cleaned_text` context.
- `LedgerSink` now reads incident fields from dicts/models and prefers `incident_type`.
- Remaining risk: ensure any future sink implementations honor the same payload conventions.

2. Sink ordering side effects
- `ApiSink` runs before local persistence. API failure can block local JSON/ledger persistence via composite short-circuit behavior.
- If local-first durability is intended, sink sequencing should be revisited.

3. Output path mismatch
- Resolved: `JsonFileSink` now respects `out_dir` when provided.

4. Processed file path coupling
- `ProcessedIndex` now supports injected inbox/processed roots (used by demo).
- Standard flow still defaults to `/data/emberlog/inbox` and `/data/emberlog/processed`.

5. Config inconsistency
- `.env.example` documents `WHISPER_*`, while main settings loader uses `EMBERLOG_` prefix for settings fields.
- This can cause unexpected runtime config behavior.

6. Local dev constraints not abstracted
- Default Whisper config assumes CUDA/float16 and `ffmpeg` availability.
- API sink requires external API availability for full path.

7. Schema/documentation drift
- `emberlog/db/schema.sql` appears draft/in-progress and may not match actual external API schema.
