# Emberlog Web Architecture

**Version:** 0.1  
**Status:** Foundational Frontend Architecture Definition  
**Applies To:** emberlog-web (Platform UI Shell)  

---

## 1. Purpose

This document defines the architectural structure of `emberlog-web` as the platform UI shell.

Goals:

- Support multiple independent domains (Traffic, Systems, Dispatch, Scanner, Command)
- Keep the UI live-first while supporting history views
- Prevent “App.tsx entropy” as features grow
- Make it easy to add built-in domains and (eventually) optional module UI extensions
- Ensure REST and SSE consumption stays contract-first and consistent

---

## 2. Core Principles

1. **Domain-first structure:** Domains own their UI + data access.  
2. **Thin shell:** The app shell provides layout, routing, and shared infrastructure only.  
3. **Contract-first:** Types and payloads align with `EVENT_MODEL.md` and `API_CONTRACT.md`.  
4. **Live + History:** Every live stream should have a corresponding historical query path.  
5. **Consistency:** One way to do API calls, SSE subscriptions, error states, and loading states.  

---

## 3. High-Level Architecture

`emberlog-web` is a modular SPA composed of:

- **Core Shell** (`src/core/`)
  - Routing, layout, navigation
  - Shared clients (REST + SSE)
  - Shared UI primitives (status pill, error boundary, etc.)
  - Shared state utilities (URL query state, persistence, etc.)

- **Domains** (`src/domains/*`)
  - Independent functional areas
  - Each domain owns its API adapters, hooks, components, and types
  - Domains render inside the shared shell

---

## 4. Recommended Directory Structure

```txt
src/
  core/
    app/
      AppShell.tsx
      routes.tsx
      Nav.tsx
      Layout.tsx
      ErrorBoundary.tsx
    config/
      config.ts
    api/
      client.ts              # REST client + base URL normalization
      errors.ts              # API error shapes + helpers
    realtime/
      sseClient.ts           # EventSource wrapper + reconnect policy
      useEventStream.ts      # Generic stream hook
      types.ts               # Shared realtime types
    state/
      urlState.ts            # URL query params helpers
    ui/
      ConnectionPill.tsx
      LoadingState.tsx
      EmptyState.tsx

  domains/
    traffic/
      api.ts
      hooks/
        useTrafficStream.ts
        useTrafficQuery.ts
      components/
        TrafficTable.tsx
        TrafficFilters.tsx
        CallDetailsDrawer.tsx
      pages/
        TrafficPage.tsx
      types.ts
      index.ts

    systems/
      api.ts
      hooks/
      components/
      pages/
      types.ts
      index.ts

    dispatch/
      api.ts
      hooks/
      components/
      pages/
      types.ts
      index.ts

    scanner/
      api.ts                  # (future) audio stream discovery / endpoints
      hooks/
      components/
      pages/
      types.ts
      index.ts

    command/
      api.ts                  # (future) control endpoints (auth-required later)
      hooks/
      components/
      pages/
      types.ts
      index.ts
```

Notes:
- Domains MAY omit folders that are not yet needed, but the pattern should remain consistent.
- `core/` must remain boring. If you feel tempted to put business logic in core, it probably belongs in a domain.

---

## 5. Routing Model

Use `react-router-dom` (already present in current stack) with top-level routes aligned to domains:

- `/traffic`
- `/systems`
- `/dispatch`
- `/scanner`
- `/command` (future, may be hidden/disabled initially)

Routing rules:
- The shell owns route registration (`src/core/app/routes.tsx`).
- Domain pages are imported by the shell.
- Domains should not register routes dynamically in v0.x (keep it simple).

---

## 6. Data Access Pattern

### 6.1 REST Client (Single Source of Truth)

All REST calls MUST go through `src/core/api/client.ts` to enforce:

- Base URL normalization (avoid `/api/v1/api/v1` bugs)
- Shared error handling
- Shared timeouts / retries policy (minimal by default)
- Shared headers (future auth tokens)

Domain APIs (`domains/*/api.ts`) should be thin wrappers around the core client.

### 6.2 SSE Client

All SSE subscriptions should go through `src/core/realtime/sseClient.ts` to enforce:

- A consistent reconnect strategy
- Consistent connection status reporting
- Deduplication using `event_id` (when needed)
- Optional filtering (domain / event_type / system)

Domains should use either:
- `useEventStream()` (generic hook) + domain-specific filtering, OR
- a domain-specific hook (e.g., `useTrafficStream`) that wraps `useEventStream()`

---

## 7. Live + History Policy

Every domain should support:
- **Live stream**: SSE subscription to relevant event types
- **History query**: REST query of relevant records/events

UI behavior:
- Live updates append/merge into current view without flicker
- Ordering should be stable and predictable
- Views should cap in-memory collections (e.g., last N items) for performance

If live stream disconnects:
- Show a visible status indicator
- Continue allowing history queries (if available)
- Optionally backfill on reconnect (future)

---

## 8. Event Consumption Guidelines

- `EVENT_MODEL.md` is the canonical shape.
- UI should treat unknown optional fields as forward-compatible.
- Domain-specific rendering should prefer canonical fields.
- `payload.parsed` (dispatch domain) must be treated as optional and non-canonical.

Where practical:
- Validate incoming SSE event envelopes (Zod in the web client is recommended).
- Fail gracefully (discard invalid events, log in dev mode, do not crash UI).

---

## 9. State Management

Default approach:
- Local component state + hooks
- URL query string for user-visible state (filters, time windows, selected system/site)
- Avoid global stores until proven necessary

When to add a store (Zustand/Redux/etc.):
- Only when multiple domains must share complex state.
- Only after the core domain patterns are stable.

---

## 10. UI Composition Guidelines

- Favor reusable UI primitives in `src/core/ui/`.
- Domain UI components stay in the domain.
- Keep layout consistent across domains (same header/nav/status location).
- Use progressive disclosure for detail (drawers, expandable rows) to preserve low cognitive load.

---

## 11. Testing Strategy (Frontend)

Minimum baseline:
- Unit tests for:
  - base URL normalization
  - query param builders
  - event dedupe / merge logic
  - SSE parsing
- Smoke tests:
  - Domain pages render without runtime errors
  - “No data” and “Disconnected” states render correctly

Tooling is intentionally lightweight:
- Prefer Vitest for unit tests.
- E2E (Playwright/Cypress) is optional later.

---

## 12. Future: UI Extensions for Third-Party Modules (Deferred)

In v0.x, Emberlog focuses on a stable core UI and event model.

Potential future extension models:
- **Config-driven UI:** modules declare “capabilities” and the UI shows generic panels
- **Optional UI packages:** third-party UI “plugins” loaded at build time or via registry

This is explicitly out of scope for the initial platform refactor.
The platform remains extensible through the API/event model even without UI plugins.

---

## 13. Definition of Done (Architecture Adoption)

The web architecture is considered “adopted” when:

- `App.tsx` is reduced to shell + route composition
- Domains exist as separate modules under `src/domains/`
- REST + SSE usage goes through core clients
- At least one domain (Traffic or Dispatch) follows the full pattern end-to-end
- Base URL configuration is explicit and safe

---

# End of Web Architecture v0.1
