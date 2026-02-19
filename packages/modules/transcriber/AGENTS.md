# AGENTS.md

## What Emberlog Is

Emberlog (this repo) is the Python backend worker pipeline that:

- watches for incoming dispatch audio files,
- queues and transcribes audio,
- cleans/splits parsed dispatch data,
- writes outputs to local sinks and downstream API integrations.

## What Emberlog Is Not (Non-Goals)

- Not the REST API server.
- Not the web frontend.
- Not a monorepo for full-stack deployment.

## Repo Scope

This repository's scope is **emberlog backend worker only**.

Related but separate repositories:

- `emberlog-api`: API server + Postgres + SSE
- `emberlog-web`: frontend consuming REST/SSE

## Hard Boundaries / Rules

- Do **not** add API server runtime code to this repo.
- Do **not** add frontend/UI code to this repo.
- For local development, prefer mocks/stubs/fakes over pulling in cross-repo runtime dependencies.
- Keep integration points explicit (client/sink interfaces), not tightly embedded.

## Run / Lint / Test (Known)

From repo root:

- Install deps: `poetry install`
- Run worker pipeline: `poetry run emberlog`
  - Alternate: `poetry run python -m emberlog.app.main`
- Run tests: `poetry run pytest`
- Lint: `poetry run ruff check .`
- Type-check: `poetry run mypy emberlog`

## Coding Conventions

- Use type hints on public functions, methods, and models.
- Add concise docstrings for modules/classes/functions with non-obvious behavior.
- Use structured logging via the existing logging setup; include useful context fields.
- Prefer minimal coupling:
  - depend on interfaces/protocols where practical,
  - isolate external integrations behind sinks/clients,
  - avoid cross-module side effects unless required.
