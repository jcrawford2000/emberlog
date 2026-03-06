# emberlog-api

FastAPI hub service for Emberlog.

This package ingests and serves Emberlog data over REST and SSE, persists state in PostgreSQL, consumes Trunk Recorder MQTT traffic snapshots, and forwards incident outbox events to the notifier service.

## Current Scope

Implemented in this package today:

- Incident APIs (`/api/v1/incidents`)
- Traffic monitor APIs (`/api/v1/traffic/summary`, `/api/v1/traffic/live-calls`)
- SSE streams (`/api/v1/sse`, `/api/v1/sse/incidents`)
- Liveness/readiness probes (`/healthz`, `/readyz`)
- MQTT consumer for rates/recorders/calls-active snapshots
- Outbox drain for `incident.created` notifier delivery

## API Endpoints

- `GET /healthz`
- `GET /readyz`
- `GET /api/v1/incidents`
- `GET /api/v1/incidents/{incident_id}`
- `POST /api/v1/incidents`
- `GET /api/v1/traffic/summary`
- `GET /api/v1/traffic/live-calls`
- `GET /api/v1/sse`
- `GET /api/v1/sse/incidents`

Interactive docs (FastAPI default):

- `/docs`
- `/openapi.json`

## Requirements

- Python 3.12+
- Poetry 2.x
- PostgreSQL (external)
- Optional: MQTT broker (for traffic monitor ingestion)

## Local Development

From repo root:

```bash
cd packages/api
cp .env.example .env
poetry install
poetry run uvicorn emberlog_api.app.main:app --host 0.0.0.0 --port 8080 --reload
```

Smoke checks:

```bash
curl http://localhost:8080/healthz
curl http://localhost:8080/readyz
```

`/readyz` returns:

- `200` with `{"status":"ok"}` when DB is reachable
- `503` with `{"status":"not_ready","reason":"db_unavailable"}` when DB is unavailable

## Configuration

All configuration is environment-variable based (`emberlog_api/app/core/settings.py`).

Database:

- `POSTGRES_HOST` (default: `localhost`)
- `POSTGRES_PORT` (default: `5432`)
- `POSTGRES_USER` (default: `postgres`)
- `POSTGRES_PASSWORD` (default: `password`)
- `POSTGRES_DB` (default: `emberlog`)
- `POSTGRES_POOL_MIN_SIZE` (default: `1`)
- `POSTGRES_POOL_MAX_SIZE` (default: `5`)

Logging:

- `LOG_LEVEL` (default: `INFO`)
- `ENABLE_FILE_LOGGING` (default: `false`)

Notifier:

- `NOTIFIER_BASE_URL` (default: `http://localhost:8090`)

MQTT / Traffic monitor:

- `MQTT_HOST` (default: `mosquitto.pi-rack.com`)
- `MQTT_PORT` (default: `1883`)
- `MQTT_TOPIC_PREFIX` (default: `emberlog/trunkrecorder`)
- `MQTT_USERNAME` (optional)
- `MQTT_PASSWORD` (optional)
- `MQTT_TLS` (default: `false`)
- `MAX_DECODERATE` (default: `40.0`)
- `RATES_TOPIC_SUFFIX` (default: `rates`)
- `RECORDERS_TOPIC_SUFFIX` (default: `recorders`)
- `CALLS_ACTIVE_TOPIC_SUFFIX` (default: `calls_active`)

## Database Migrations

SQL migrations live in `emberlog_api/migrations/`.

Example:

```bash
psql "$DATABASE_URL" -f emberlog_api/migrations/schema_v1.0.0.sql
```

Apply additional versioned migration files in order as needed for your target deployment.

## Tests

Run from `packages/api`:

```bash
poetry run pytest -q
```

Current tests cover:

- Health/readiness behavior
- Incident list filters/pagination
- Traffic endpoint normalization/filtering
- SSE streaming/filter validation
- MQTT consumer processing

## Container and Kubernetes

- Container build/run instructions: `docs/CONTAINER.md`
- Kubernetes manifests: `k8s/`
- ArgoCD app definition: `k8s/argocd/emberlog-api-app.yaml`

## License

This package uses the repository canonical license at [LICENSE.md](/home/justin/Development/emberlog/LICENSE.md).
