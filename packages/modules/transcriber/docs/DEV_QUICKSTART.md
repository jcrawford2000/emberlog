# Dev Quickstart

Type: Operational Runbook  
Normative references: `/docs/DEVELOPMENT.md`, `/docs/DEPLOYMENT_MODEL_v0.1.md`  
Last verified: 2026-03-06

## Setup

```bash
poetry install
```

Create a local `.env` (CPU-safe defaults):

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

## Run Demo Mode (no GPU / no API required)

```bash
poetry run emberlog demo
```

Demo mode behavior:

- Uses fixture WAV files from `samples/inbox/`
- Uses deterministic transcript fixtures from `samples/transcripts/` via stub backend
- Stages runtime input under `out/demo/inbox/...`
- Runs watcher/queue/worker pipeline once and exits
- Writes outputs under `out/demo/`:
  - JSON: `out/demo/json/`
  - Ledger DB: `out/demo/ledger.sqlite`
  - Processed index DB: `out/demo/processed.sqlite`
  - Processed audio: `out/demo/processed/`

Optional API sink in demo:

```bash
poetry run emberlog demo --with-api
```

## Run Standard Worker

```bash
poetry run emberlog
```

## Test / Lint / Type Check

```bash
poetry run python -m pytest -q
poetry run ruff check .
poetry run mypy emberlog
```
