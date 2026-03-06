# AGENTS.md

Guidelines for automated agents working in `packages/modules/transcriber`.

## Source of Truth

- Root `/docs` is canonical for platform architecture and contracts.
- Especially follow:
  - `/docs/PLATFORM_VISION_v0.2.md`
  - `/docs/DEPLOYMENT_MODEL_v0.1.md`
  - `/docs/EVENT_MODEL_v0.2.md`
  - `/docs/API_CONTRACT_v0.1.md`
  - `/docs/DEVELOPMENT.md`
- `packages/modules/transcriber/docs` is module-local operational documentation only.

If package docs and root canon differ, root `/docs` wins.

## Current Integration Boundary

This module currently posts to Emberlog API incidents endpoint (`POST /api/v1/incidents`).
Treat that as current implementation truth unless explicitly instructed to migrate.

## Scope Rules

Do:
- Keep changes inside module boundaries.
- Maintain watcher -> queue -> worker -> sinks flow.
- Keep local sinks and API sink behavior explicit and testable.

Do not:
- Add API server runtime code here.
- Add frontend code here.
- Redefine platform contracts in this package docs folder.

## Validation Commands

From `packages/modules/transcriber`:

```bash
poetry run pytest -q
poetry run ruff check .
poetry run mypy emberlog
```
