# emberlog-web

Frontend shell for Emberlog.

This package provides the web UI that consumes Emberlog API REST and SSE endpoints. The current implemented domains are Traffic Monitor and Dispatch Intelligence.

## Current Scope

- App shell and routing (`/traffic`, `/dispatch`)
- Traffic summary and live calls views
- Dispatch incident feed, filtering, and detail view
- SSE live event stream integration (`/api/v1/sse`)
- Shared API and realtime clients under `src/core`

## Architecture

This package follows the domain/core split defined in the root canon docs:

- `src/core/` for shell, routing, shared API client, shared realtime client
- `src/domains/` for domain-specific UI and hooks

Current domain implementation:

- `src/domains/traffic`
- `src/domains/dispatch`

Dispatch reads its REST snapshot from `GET /api/v1/incidents` and subscribes to canonical live events from `GET /api/v1/sse` with `dispatch.incident.created` / `dispatch.incident.updated` filters.

## API Integration

The app reads API base URL from:

- `VITE_API_BASE_URL` (preferred)
- `VITE_API_BASE` (legacy fallback)

Default fallback is `http://localhost:8000` when env vars are not set.

## Local Development

From repo root:

```bash
cd packages/web
cp .env.example .env
npm install
npm run dev
```

Default dev server host is enabled via `vite --host`.

## Build and Lint

```bash
npm run build
npm run lint
```

## Package Docs

- Operational assets and screenshots live under `docs/`
- Platform architecture and contracts are canonical in root `/docs`

## License

This package uses the repository canonical license at [LICENSE.md](/home/justin/Development/emberlog/LICENSE.md).
