# REQUIREMENTS.md

## Scope

These requirements describe Emberlog based on current implementation in this repo (`emberlog`) plus known system context from `docs/CURRENT_STATE.md`.

- In-scope repo: `emberlog` worker pipeline only.
- Related external repos: `emberlog-api` (REST/Postgres/SSE), `emberlog-web` (UI).

## Functional Requirements

### 1) Ingest

- **FR-INGEST-1 (Current):** System shall watch a configured inbox directory recursively for new audio files.
- **FR-INGEST-2 (Current):** System shall accept configured audio extensions and only process files under dated paths (`YYYY/M/D/...`).
- **FR-INGEST-3 (Current):** System shall optionally scan existing files at startup.
- **FR-INGEST-4 (Current):** System shall de-duplicate already processed files using a local processed-index database.

### 2) Transcribe

- **FR-TRANSCRIBE-1 (Current):** System shall transcribe queued audio using a configured backend (`dummy`, `stub`, or `faster_whisper`).
- **FR-TRANSCRIBE-2 (Current):** System shall support Whisper-related runtime settings via environment-backed configuration.
- **FR-TRANSCRIBE-3 (Current):** System shall allow concurrent worker execution based on configured concurrency.

### 3) Parse / Normalize

- **FR-PARSE-1 (Current):** System shall split transcript content into dispatch units using implemented segmentation rules.
- **FR-PARSE-2 (Current):** System shall normalize/clean transcript text and attempt extraction of channel, units, incident type, and address.
- **FR-PARSE-3 (Current):** If fields cannot be extracted, system behavior shall remain best-effort (no strict schema rejection in worker flow).

### 4) Store / Persist

- **FR-STORE-1 (Current):** System shall write per-dispatch JSON output files to local outbox storage.
- **FR-STORE-2 (Current):** System shall append/insert dispatch metadata into local SQLite ledger storage with hash-based idempotency.
- **FR-STORE-3 (Current):** System shall move processed source audio to processed storage path after marking processed.
- **FR-STORE-4 (Current):** Standard worker flow shall attempt to post incident payloads to configured external API endpoint via API sink.
- **FR-STORE-5 (Current):** Demo flow shall run without API sink by default; API sink is optional (`demo --with-api`).

### 4a) Deterministic Demo Mode

- **FR-DEMO-1 (Current):** System shall provide `poetry run emberlog demo` that runs once and exits with local-only outputs.
- **FR-DEMO-2 (Current):** Demo mode shall not require CUDA/GPU, `ffmpeg`, or external API by default.

### 5) Notify

- **FR-NOTIFY-1 (Aspirational/External):** Real-time notifications/streaming are expected via `emberlog-api` SSE, not implemented in this repo.
- **FR-NOTIFY-2 (Current in this repo):** `emberlog` provides outbound incident submission to API (a prerequisite integration point), but no direct notifier subsystem exists here.

### 6) UI

- **FR-UI-1 (Out of scope for this repo):** User interface is implemented in separate `emberlog-web` repo.
- **FR-UI-2 (Aspirational/External):** UI behavior depends on API/SSE contracts provided by `emberlog-api`.

## Non-Functional Requirements

### Latency / Throughput

- **NFR-LAT-1 (Current):** Processing is asynchronous (watcher + queue + workers) and intended for near-real-time ingestion.
- **NFR-LAT-2 (Current):** No explicit end-to-end latency SLA is defined in this repo.
- **NFR-LAT-3 (Aspirational):** Formal latency targets should be defined at system level across `emberlog` + `emberlog-api` + `emberlog-web`.

### Reliability / Resilience

- **NFR-REL-1 (Current):** Worker shall retry failed jobs up to configured/max modeled attempts with backoff.
- **NFR-REL-2 (Current):** System shall support graceful shutdown with queue drain semantics.
- **NFR-REL-3 (Current):** Local deduplication is provided via processed index and ledger hash uniqueness.
- **NFR-REL-4 (Constraint):** Queue is in-memory and process-local; no durable/distributed queue is implemented.

### Observability

- **NFR-OBS-1 (Current):** System shall emit structured logs with module-level logger names.
- **NFR-OBS-2 (Current):** Console and file handlers are configured; file path defaults to `/var/log/emberlog/emberlog.log`.
- **NFR-OBS-3 (Aspirational):** Metrics/tracing/alerting are not implemented in this repo and require external observability stack.

### Security

- **NFR-SEC-1 (Current):** API client supports `X-API-Key` header usage for outbound requests.
- **NFR-SEC-2 (Current constraint):** No comprehensive authn/authz, secret management, or transport policy enforcement is implemented in this repo.
- **NFR-SEC-3 (Aspirational):** Production security controls are expected to be enforced in deployment/infrastructure and `emberlog-api` boundary.

## Out of Scope (This Repo)

- API server runtime (FastAPI/REST/SSE implementation).
- Frontend/UI implementation.
- Notification service implementation beyond API submission.
- Kubernetes manifests, systemd units, and full deployment orchestration artifacts.
- Distributed message broker/queue implementation.

## Notes / Verification Needed

- Current sink behavior under partial downstream failure should be validated in integration tests.
- `emberlog/db/schema.sql` appears draft/in-progress and should not be treated as authoritative runtime behavior for this repo.
