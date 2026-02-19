# AGENTS.md
### Guidelines for AI Agents Contributing to Emberlog-Web

This document defines how automated agents (e.g., Codex) should work in this repository.

Emberlog-Web is a frontend for the Emberlog platform. It consumes:
- `GET /api/v1/incidents` (REST) for historical incidents and filtering
- `GET /api/v1/sse/incidents` (SSE) for live updates

---

## 1. Tech Stack & Structure

- Use **React** with **functional components** and **hooks**.
- Use **TypeScript** everywhere (no `any` unless truly necessary).
- Use **Vite** conventions for project structure.
- Use **TailwindCSS** (and DaisyUI if present) for styling; avoid inline styles except for very small cases.

Match existing directory structure. Typical locations:
- `src/components` – reusable components
- `src/pages` or `src/views` – route-level components
- `src/api` – API/HTTP helper functions
- `src/hooks` – custom hooks

If you need to introduce new modules, place them in the most consistent existing folder.

---

## 2. API & Config

- All HTTP calls to Emberlog-API must go through a small API helper module (e.g., `src/api/emberlogApi.ts`).
- Do **not** hardcode URLs. Use a configurable base URL:
  - Prefer something like `VITE_EMBERLOG_API_BASE_URL` from environment/config.
- When adding new API calls:
  - Define TypeScript interfaces for request/response types.
  - Keep functions small and focused.

---

## 3. SSE (Server-Sent Events)

- SSE subscriptions should be implemented in a dedicated hook or utility (e.g., `useIncidentsSSE`) if possible.
- Keep SSE logic **separate** from generic UI logic:
  - Hooks manage subscription, reconnection, and clean-up.
  - Components consume hook state and render accordingly.
- Do **not** change SSE event schema or endpoint paths unless explicitly instructed.

---

## 4. State Management

- Prefer local component state + React hooks for now, unless a global state solution already exists.
- If a global state library is already in use (e.g., Zustand, Redux), follow existing patterns.
- When combining API data and SSE data:
  - Use incident `id` as the primary key.
  - On SSE events:
    - Update existing incidents by `id`.
    - Insert new incidents at the top if ordering by `dispatched_at` desc.

---

## 5. UI & UX Conventions

- Keep UI minimal but consistent:
  - Use existing components/patterns for tables, buttons, forms, and filters.
  - Respect existing color, spacing, and typography conventions.
- For new UI:
  - Prefer reusable components (filter bar, pagination controls, etc.).
  - Keep complex layouts in separate components instead of huge JSX blocks.

---

## 6. Error & Loading States

- Always provide:
  - A loading state for async data (spinners, skeletons, or simple text).
  - A basic error state if an API call fails.
- Do not swallow errors silently.

---

## 7. Tests

- If there is an existing test setup (Jest, Vitest, Testing Library), follow it.
- New logic in hooks or complex components should have tests where feasible.
- Prefer testing behavior over implementation details.

---

## 8. Branching & PRs

- Create feature branches using:
  - `feature/<short-description>` or `fix/<short-description>`
- PRs should:
  - Have a clear title.
  - Explain user-visible changes.
  - Note any config/env changes (e.g., new `VITE_*` vars).
- Keep PRs small and focused on a single concern (e.g., “add incidents list + filters”, not “add list + filters + new layout + refactor everything”).

---

## 9. What NOT to change without explicit instructions

- Routing configuration / top-level app layout
- SSE endpoint URL or event schema
- Global theme / Tailwind config
- Build tooling (Vite config, package.json scripts)

---

## 10. Philosophy

Emberlog-Web is:
- A **read-mostly** UI over incidents and their metadata.
- A **live dashboard** via SSE, not a complex CRUD app (yet).

Agents should:
- Keep components small and understandable.
- Respect existing patterns.
- Prioritize clarity and correctness over cleverness.
