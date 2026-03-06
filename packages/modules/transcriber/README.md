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
poetry run pytest -q
poetry run ruff check .
poetry run mypy emberlog
```

## Docs

- Local module runbooks: `docs/`
- Platform canon docs: root `/docs`

## License

This module uses the repository canonical license at [LICENSE.md](/home/justin/Development/emberlog/LICENSE.md).
