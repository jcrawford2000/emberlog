# Dev Quickstart

## Setup

```bash
poetry install
```

## Run Demo Mode (no GPU / no API required)

```bash
poetry run emberlog demo
```

What demo mode does:
- Uses fixture audio placeholders from `samples/inbox/`.
- Uses deterministic transcript text fixtures from `samples/transcripts/` (stub transcriber backend).
- Stages fixture WAVs into a run-local inbox under `out/demo/inbox/...` (source fixtures are not mutated).
- Runs the real watcher/queue/worker/segmentation/cleaning/sink pipeline once, then exits.
- Writes outputs under `out/demo/`:
  - JSON: `out/demo/json/`
  - Ledger DB: `out/demo/ledger.sqlite`
  - Processed index DB: `out/demo/processed.sqlite`
  - Processed audio: `out/demo/processed/`
- Re-running demo is idempotent at ledger level (no duplicate rows for the same fixtures).

Optional:
- Include API sink in demo (off by default):

```bash
poetry run emberlog demo --with-api
```

## Run Standard Worker

```bash
poetry run emberlog
```

## Test / Lint / Type Check

```bash
poetry run pytest
poetry run ruff check .
poetry run mypy emberlog
```
