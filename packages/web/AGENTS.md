# AGENTS.md
### Guidelines for AI Agents Contributing to emberlog-web

This document defines how automated agents should work inside `packages/web`.

## Source of Truth

- Root `/docs` is normative for architecture and contracts.
- Especially follow:
  - `/docs/WEB_ARCHITECTURE_v0.1.md`
  - `/docs/API_CONTRACT_v0.1.md`
  - `/docs/EVENT_MODEL_v0.2.md`
  - `/docs/DEVELOPMENT.md`
- `packages/web/docs` is for package-local operational assets only (screenshots/runbooks), not platform contracts.

If package docs and root docs conflict, root `/docs` wins.

## Architecture Rules

- Preserve the domain/core split:
  - `src/core` for shell, routing, shared infrastructure
  - `src/domains` for domain-specific features
- Keep business/domain logic out of `src/core`.
- Do not reintroduce monolithic `App.tsx` behavior.

## API and Realtime Rules

- Use shared clients in `src/core/api` and `src/core/realtime`.
- Do not hardcode backend URLs; use `VITE_API_BASE_URL` with `VITE_API_BASE` fallback.
- Keep SSE envelope handling aligned with canonical event model.
- Do not invent alternate transport schemas in web code.

## UI and State Rules

- Prefer local state and hooks.
- Keep components small and domain-contained.
- Include explicit loading, empty, and error states for async views.

## Safe Change Boundaries

Do:
- Implement contained changes within existing domain structure.
- Add or update docs/screenshots in `packages/web/docs` when UI behavior changes.

Do not:
- Redefine API contracts in package docs.
- Introduce new architecture patterns without explicit approval.
- Change canonical endpoint semantics defined in root `/docs`.

## Validation

For frontend changes, run:

```bash
npm run build
npm run lint
```
