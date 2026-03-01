# Emberlog Development

This repo is a **monorepo for source**, but Emberlog is a **distributed runtime platform**.
Components are designed to run independently (often on different machines) and communicate only over network contracts (REST/SSE/MQTT).

## Repo layout

- `docs/` — platform documentation (vision, contracts, architecture, deployment)
- `packages/api` — Emberlog API (hub)
- `packages/web` — Emberlog Web UI
- `packages/modules/transcriber` — Emberlog Transcriber (GPU-bound module)
- `packages/contracts` — contract artifacts (schemas/codegen home; may start minimal)

## Default local ports

- Emberlog API: `http://localhost:8000`
- Emberlog Web: `http://localhost:5173`
- PostgreSQL (optional local): `localhost:5432`
- MQTT broker (optional local): `localhost:1883`

## Environment files

- Real `.env` files are **not committed**
- Example files **are committed**:
  - `.env.example` (root)
  - `packages/api/.env.example`
  - `packages/web/.env.example`
  - `packages/modules/transcriber/.env.example`

Copy the relevant example(s) to `.env` in the same directory and adjust values.

## Run: Emberlog API (hub)

From the repo root:

```bash
cd packages/api
# copy config
cp .env.example .env
# run using the package's existing tooling (uv/poetry/pip/docker) as documented in packages/api
```

Smoke checks (once running):

- `GET http://localhost:8000/healthz`
- `GET http://localhost:8000/readyz`

## Run: Emberlog Web

```bash
cd packages/web
cp .env.example .env
npm install
npm run dev
```

The web app reads the API base URL from `VITE_API_BASE_URL`.

## Run: Emberlog Transcriber (module)

The transcriber is GPU-bound and is typically deployed on a GPU-capable host.
It must communicate to the API via network (no shared disk assumptions).

```bash
cd packages/modules/transcriber
cp .env.example .env
# run using the package's existing tooling as documented in packages/modules/transcriber
```

## Run: Distributed (recommended)

Typical homelab layout:

- Host A: Trunk Recorder (+ SDR) → publishes to MQTT
- Host B: Transcriber (+ GPU) → emits `dispatch.*` events to API ingest
- Host C: API + Web (K8s or containers)

Comms paths:

- Trunk Recorder → MQTT → API
- Transcriber → REST ingest → API
- Web → REST/SSE → API

## Notes

- The monorepo is for coordinated evolution of contracts + components.
- Runtime remains distributed. Avoid shortcuts that assume same-host processes or shared filesystems.
