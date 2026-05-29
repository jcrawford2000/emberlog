# Emberlog Web Console — UI Kit

A high-fidelity, click-through recreation of the **Emberlog operations console**.
The app shell (red header + domain nav) hosts two working domains — **Traffic
Monitor** (recreated from `jcrawford2000/emberlog → packages/web` and
`emberlog-web`) and **Dispatch Intelligence** (the reference design for the
implemented `dispatch` domain, grounded in `docs/EVENT_MODEL_v0.2`).

Open `index.html` — use the **nav to switch between Traffic and Dispatch**
(Systems / Scanner / Command remain stubbed). It defaults to Dispatch.

## Traffic Monitor

- **Live filtering** — click a gauge (or a system chip in a row) to filter
  Recent Calls to that system; click again to clear.
- **Search** across talkgroup / category / tag / system, **Hide encrypted**, and
  **Clear filters**.
- **System details modal** — click *Details* under any gauge.
- Live rows are tinted + pulse; `ENC` / `REC` / `Emergency` / `TDMA` flags inline.

## Dispatch Intelligence

Renders `dispatch.incident.created` events from `emberlog-transcriber`: a live,
**color-coded incident feed** (by category) with a master–detail layout.

- **Full filter system** — free-text search, **Time** (live / 1h / 4h), **City**,
  **Units**, **Type**, **Category** quick-chips, and **Channel**; active filters
  show as removable chips with a live result count.
- **City filter keys off unit-number ranges** using the official **Phoenix
  Regional Dispatch** agency blocks (58 agencies, Rev. 2012), including the
  4-digit overflow rule (e.g. Glendale 151–159 → 1510, 1511…). An incident
  surfaces under every city whose units are assigned, so mutual-aid shows
  correctly. See `cityOfUnit()` / `AGENCIES` in `data.jsx`.
- **Detail pane** — type badge, address, dispatched time, city/channel/units,
  a **map pin** (placeholder), an **audio waveform** scrubbed to the segment, a
  **Cleaned ↔ Raw STT** transcript toggle, and a **correlation chip** that links
  back to the originating Traffic call.

## Components

| File | Component(s) | Mirrors / basis |
|---|---|---|
| `AppHeader.jsx` | `AppHeader` | `core/app/AppShell.tsx` header + nav (tabbed) |
| `TrafficPage.jsx` | `TrafficPage` | composes the Traffic domain |
| `FilterBar.jsx` | `PageHead`, `FilterBar` | `TrafficHeader.tsx` + filter row |
| `SystemGauge.jsx` | `SystemGauge`, `SystemGaugeStrip` | `SystemHealthCard/Strip.tsx` |
| `CallsTable.jsx` | `CallsTable`, `CallRow` | `CallsTable.tsx` + table |
| `SystemDetailModal.jsx` | `SystemDetailModal` | `SystemHealthCard` modal |
| `DispatchPage.jsx` | `DispatchPage`, `DispatchDetail` | reference `dispatch` domain |
| `DispatchFilters.jsx` | `DispatchFilterBar` | filter toolbar + popovers |
| `data.jsx` | `Icon`, formatters, `SYSTEMS`, `CALLS`, `INCIDENTS`, `AGENCIES`, `cityOfUnit` | `recentCalls.ts` helpers, `EVENT_MODEL`, Phoenix Regional numbering |
| `kit.css` | styles + inlined tokens (Dispatch rules namespaced under `.dispatch`) | `index.css` `@theme` |

## Stack notes

The real app is React 19 + Vite + **Tailwind v4 / daisyUI 5** with `lucide-react`.
This kit uses React 18 (UMD) + Babel + plain CSS as a single static file. **Icons
are inline SVG** built from the Lucide CDN data (`window.lucide.icons`) and owned
by React — this avoids the DOM-mutation crash that `lucide.createIcons()` causes
when components re-render on filter changes. It's a cosmetic recreation — no real
REST/SSE — so swap `data.jsx` for live data when wiring to `emberlog-api`.

## Caveats

- **Dispatch is implemented in the codebase**, but this UI kit remains a
  prototype/reference artifact. The map is a styled placeholder (the event schema
  carries a text `address`, not lat/long), and the incident-type color scale
  (Fire / EMS / MVC / Alarm / Service) is an addition.
- **Systems / Scanner / Command** remain stubbed (disabled nav) — don't invent
  them until the codebase defines them.
