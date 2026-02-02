# Current State (Repository Inventory)

Last verified from repository contents on February 1, 2026.

## System Context (External Repos)

This repository is one part of a 3-repo system:

- `emberlog` (this repo): watcher/worker/transcriber pipeline plus sinks and local state/ledger handling.
- `emberlog-api`: REST API + Postgres persistence + SSE stream endpoints.
- `emberlog-web`: frontend that consumes REST and SSE from `emberlog-api`.

Important boundary:

- The API server is intentionally not implemented in this repository.
- This repo contains API client/integration code (`emberlog/api/client.py`) and SQL artifacts (`emberlog/db/schema.sql`), but not the API runtime/service itself.

## 1) Repository structure (what exists today)

Top-level:

- `emberlog/` - main Python package (all runtime code currently lives here)
- `tests/` - test(s) and sample media/text fixtures
- `logs/` - local log directory in repo
- `.env.example` - example runtime environment configuration
- `pyproject.toml` - packaging, dependencies, CLI script entry
- `README.md` - project overview (contains some planned/outdated structure notes)

Key subfolders under `emberlog/`:

- `emberlog/app/` - process entrypoint/supervisor (`main.py`)
- `emberlog/watch/` - watchdog-based inbox filesystem watcher
- `emberlog/queue/` - in-memory async queue interface + implementation
- `emberlog/worker/` - async consumer that transcribes/processes jobs
- `emberlog/transcriber/` - transcriber backends (`dummy`, `faster_whisper`) + factory
- `emberlog/segmentation/` - transcript splitting into dispatch chunks
- `emberlog/cleaning/` - transcript cleanup/parsing heuristics
- `emberlog/io/` - output sinks (API, JSON file, ledger, composite)
- `emberlog/ledger/` - SQLite ledger wrapper and schema bootstrap
- `emberlog/state/` - processed-file index (SQLite)
- `emberlog/api/` - HTTP client models/client for downstream API
- `emberlog/config/` - pydantic settings and env loading
- `emberlog/models/` - pydantic domain models (`Job`, `Transcript`, `Incident`)
- `emberlog/db/` - SQL schema file for a Postgres `incidents` store
- `emberlog/utils/` - logging setup + standalone transcription utility script

Not found in this repo (as separate components):

- No separate `backend/`, `web/`, `notifier/`, or frontend app directory
- No FastAPI service implementation in this repo
- No `systemd` unit files in-repo
- No Kubernetes manifests/Helm chart in-repo

## 2) Components present and where

Runtime pipeline component (single Python service):

- Watcher: `emberlog/watch/watcher.py`
- Queue: `emberlog/queue/memory.py`
- Worker: `emberlog/worker/consumer.py`
- Transcription backends:
  - `emberlog/transcriber/dummy.py`
  - `emberlog/transcriber/whisper_fast.py`
- Transcript splitting: `emberlog/segmentation/splitter.py`
- Cleaning/parsing: `emberlog/cleaning/cleaner.py`
- Outputs:
  - API sink: `emberlog/io/api_sink.py`
  - JSON file sink: `emberlog/io/json_sink.py`
  - Ledger sink: `emberlog/io/ledger_sink.py`
  - Orchestration: `emberlog/io/composite.py`
- Local ledger DB wrapper: `emberlog/ledger/ledger.py` (SQLite)
- Processed-file state DB: `emberlog/state/processed_index.py` (SQLite)

External/downstream integration code (client-only in this repo):

- API client for incidents endpoint: `emberlog/api/client.py`
- Postgres DDL (schema file, not an app server): `emberlog/db/schema.sql`

## 3) Configuration items and where they are sourced

Primary runtime settings source:

- `emberlog/config/config.py` defines `Settings(BaseSettings)`.
- Settings load from `BASE_DIR/.env` with prefix `EMBERLOG_`.
- `model_config`: `env_file=.../.env`, `env_prefix="EMBERLOG_"`, `extra="ignore"`.
- Defaults are embedded in code if env vars are absent.

Documented env examples:

- `.env.example` includes `EMBERLOG_*` paths/concurrency/backend/log settings.
- `.env.example` also includes `WHISPER_*` variables.

Important detail about whisper vars:

- In `config.py`, whisper fields are inside `Settings`, so they resolve from `EMBERLOG_WHISPER_*` by default (due to `env_prefix="EMBERLOG_"`).
- `transcriber/whisper_fast.py` reads whisper values from `Settings` (therefore effectively `EMBERLOG_WHISPER_*` unless aliases are added).
- `utils/transcribe.py` (standalone CLI utility) reads `WHISPER_*` directly via `os.getenv`.

Other config sources:

- `pyproject.toml`
  - CLI script: `emberlog = "emberlog.app.main:main"`
  - Runtime deps include `faster-whisper`, `ctranslate2`, `watchdog`, etc.
- `emberlog/versioning.py`
  - app version from `git describe`, then package metadata, then `EMBERLOG_VERSION` env var fallback.
- `emberlog/utils/loggersetup.py`
  - logging dict config hardcodes a file handler path: `/var/log/emberlog/emberlog.log`.

Runtime side effects at import time:

- `config.py` creates inbox/outbox/ledger parent directories immediately when imported.

## 4) Local Development Constraints

Why this does not run end-to-end on a typical workstation today:

1. Missing downstream pipeline in this repo (API/service side)

- Worker sink chain includes API posting (`ApiSink`) to `settings.api_base_url` (default `http://localhost:8080/api/v1`).
- This repo contains an API client (`emberlog/api/client.py`) and SQL schema (`emberlog/db/schema.sql`) but no API server runtime (this split is intentional; API server lives in `emberlog-api`).
- So the full ingestion -> API persistence path depends on external services not provided here.

2. GPU Whisper dependency in default configuration

- Default whisper device in `config.py` is `cuda` and compute type `float16`.
- `faster-whisper`/`ctranslate2` are runtime dependencies.
- Typical workstation setups without CUDA GPU/runtime will not run the default faster-whisper path as configured.

Additional local friction observed in current code:

- `transcriber_backend` default in settings is `dummy`, but `.env.example` sets `EMBERLOG_TRANSCRIBER_BACKEND="faster_whisper"`.
- Watcher/state logic uses hardcoded processed destination `/data/emberlog/processed` when moving files.
- Logging config writes to `/var/log/emberlog/...`, which may require permissions not present on a normal user workstation.
- `whisper_fast.py` shells out to `ffmpeg` for pre-trim; `ffmpeg` must be installed on PATH.

## 5) Key entry points and deploy artifacts

CLI / process entry:

- Poetry script entry: `pyproject.toml` -> `emberlog = "emberlog.app.main:main"`
- Main module: `emberlog/app/main.py` (`main()` and async `_run()`).
- Alternate utility CLI: `emberlog/utils/transcribe.py` (`main()` standalone tool).

FastAPI app object:

- Unknown/Needs verification: no `FastAPI(...)` app object found in this repository.

systemd units:

- Unknown/Needs verification: none found in this repository.

Kubernetes manifests:

- Unknown/Needs verification: none found in this repository.

## 6) Data flow as implemented (current code path)

Implemented flow in `emberlog/app/main.py` + dependent modules:

1. Startup:

- Build in-memory queue (`InMemoryJobQueue`).
- Build watcher config (`WatchConfig`) using inbox path, audio extensions, scan-existing flag.
- Start `DirectoryWatcher`.
- Start N async workers (`Worker`) based on `settings.concurrency`.

2. File discovery:

- Watcher monitors inbox recursively via watchdog.
- Only files with allowed extensions and under dated tree pattern `YYYY/M/D/...` are accepted.
- Existing files can be scanned at startup if enabled.
- Files are de-duplicated via `ProcessedIndex` fingerprint DB before enqueue.

3. Queue + transcription:

- Worker consumes `Job(path=...)` from queue.
- Worker picks backend from settings using `transcriber.factory.from_settings(...)`.
- Transcriber returns transcript text/timing/language.

4. Post-processing:

- Transcript segments are split into dispatch chunks (`split_transcript`).
- Each chunk is cleaned/parsed (`clean_transcript`) to derive units/channel/type/address.
- Worker builds a dispatch document payload.

5. Sink pipeline (in order):

- `ApiSink`: POST incident payload to configured external API.
- `JsonFileSink`: write per-dispatch JSON via atomic local write.
- `LedgerSink`: insert ledger row into SQLite (`ledger_path`) using hash-based idempotency.

6. State update and file movement:

- Worker marks source file as processed in `ProcessedIndex` SQLite.
- `ProcessedIndex.mark_processed(...)` moves processed audio from inbox to `/data/emberlog/processed/...`.

Behavioral notes (current implementation details):

- Queue is process-local only (no Redis/rabbit/etc. in repo).
- Graceful shutdown waits for stop signal, stops watcher, drains queue, cancels workers.
- Some sink interactions and test expectations appear inconsistent with intended behavior.
  - Unknown/Needs verification: exact success/failure behavior across API/JSON/Ledger sinks under real runs.

## 7) Known gaps / verification-needed areas

- API server implementation is not in this repository (client-only integration present).
- `emberlog/db/schema.sql` appears to be draft/in-progress and should be verified before production use.
- Current `README.md` includes a planned structure that does not fully match current code layout.
