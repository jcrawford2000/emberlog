# Emberlog Contracts

This package is the long-term home for **machine-readable platform contracts**.

Emberlog is contract-first:
- `docs/EVENT_MODEL.md` defines the canonical event envelope and domain payload expectations.
- `docs/API_CONTRACT.md` defines REST/SSE transport conventions and ingest requirements.

In v0.x, the docs are the primary source of truth.
Over time, this package will grow to include:
- JSON Schemas for event envelopes and event payloads
- OpenAPI definitions for Emberlog API endpoints
- Generated types for TypeScript (web) and Python (api/modules)

## Directory layout

```
packages/contracts/
  README.md
  versioning.md
  schemas/
```

## Current contract sources

- `docs/PLATFORM_VISION.md`
- `docs/EVENT_MODEL.md`
- `docs/API_CONTRACT.md`
- `docs/WEB_ARCHITECTURE.md`
- `docs/DEPLOYMENT_MODEL.md`

## Important note

This package does **not** introduce runtime coupling.
It exists to keep services aligned on shared structure, while preserving a distributed deployment model.
