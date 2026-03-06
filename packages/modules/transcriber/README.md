# emberlog-transcriber

Transcriber module for Emberlog.

This package watches for audio files, transcribes them, normalizes dispatch data, writes local outputs, and posts incident payloads to Emberlog API.

## Current Scope

- Directory watch + queued worker pipeline
- Pluggable transcriber backends (`dummy`, `stub`, `faster_whisper`)
- Transcript segmentation + cleaning
- Local JSON output sink
- Local SQLite ledger sink
- Outbound API sink to Emberlog API `POST /api/v1/incidents`

## Integration Status

Current production integration in this module posts incidents to:

- `POST /api/v1/incidents`

This is intentionally kept as current truth for now. Future contract alignment to canonical ingest events is a planned phase.

## Run

From repo root:

```bash
cd packages/modules/transcriber
cp .env.example .env
poetry install
```

CPU-safe local test profile (recommended for workstations without CUDA):

```bash
cat > .env <<'ENV'
EMBERLOG_TRANSCRIBER_BACKEND=stub
EMBERLOG_LOG_LEVEL=INFO
EMBERLOG_INBOX_DIR=./out/local/inbox
EMBERLOG_OUTBOX_DIR=./out/local/outbox
EMBERLOG_LEDGER_PATH=./out/local/ledger.sqlite
EMBERLOG_WHISPER_DEVICE=cpu
EMBERLOG_WHISPER_COMPUTE_TYPE=int8
EMBERLOG_WHISPER_MODEL=small.en
ENV
```

Standard worker:

```bash
poetry run emberlog
```

Deterministic demo mode (no GPU/API required by default):

```bash
poetry run emberlog demo
```

## Tests and Quality

```bash
poetry run python -m pytest -q
poetry run ruff check .
poetry run mypy emberlog
```

## Docs

- Local module runbooks: `docs/`
- Platform canon docs: root `/docs`

## License

This module uses the repository canonical license at [LICENSE.md](/home/justin/Development/emberlog/LICENSE.md).
