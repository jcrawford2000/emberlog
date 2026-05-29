# Emberlog Design System

A working design system for **Emberlog** — an open-source, contract-first platform
for Trunk Recorder ecosystems. Emberlog turns raw trunked-radio activity into
structured, observable, and extensible intelligence: real-time traffic monitoring,
system-health telemetry (decode rates, site health), and structured intelligence
modules (e.g. dispatch transcription), all surfaced through a modular web console.

> Emberlog is **not** just a dashboard. Not just a transcript viewer. Not just a
> web frontend for Trunk Recorder. **It is a platform.**

This folder gives design agents everything needed to produce on-brand Emberlog
interfaces, mocks, and assets: colors, type, iconography, brand voice, and a
high-fidelity UI kit recreating the web console.

---

## Product context

Emberlog is a **contract-first, hub-centric** platform. Modules emit canonical
events into a central Hub (`emberlog-api`); the Hub validates schemas, persists
data, publishes live streams over **SSE**, and serves history over **REST**. The
web console (`emberlog-web`) is a thin, **live-first** SPA shell that renders
independent domains.

**Planned domains (the UI reflects this separation):**

| Domain | Route | Status | What it shows |
|---|---|---|---|
| **Traffic** | `/traffic` | ✅ Implemented | Live trunkgroup activity — recent calls, flags |
| **Systems** | `/systems` | Planned | Site health, decode rates (today shown inside Traffic) |
| **Dispatch** | `/dispatch` | ✅ Implemented | Structured incident / transcription intelligence |
| **Scanner** | `/scanner` | Planned (future) | Audio playback |
| **Command** | `/command` | Planned (future) | Control plane — configuration & management |

Traffic Monitor and Dispatch Intelligence are built into the web console. The
design language below is extracted from the implementation plus the platform
vision/architecture docs.

---

## Sources

This design system was reverse-engineered from the following repositories. The
reader is encouraged to explore them to build more accurate Emberlog designs —
the codebase is the source of truth, not this document.

- **Monorepo (current):** https://github.com/jcrawford2000/emberlog
  - Web console: `packages/web` (React 19 · Vite · Tailwind v4 · daisyUI 5)
  - Theme tokens: `packages/web/src/index.css` (`@theme` block)
  - Traffic domain: `packages/web/src/domains/traffic/` — `pages/TrafficPage.tsx`,
    `components/{CallsTable,SystemHealthCard,SystemHealthStrip,TrafficHeader}.tsx`
  - App shell: `packages/web/src/core/app/AppShell.tsx`
  - Platform docs: `docs/PLATFORM_VISION_v0.2.md`, `docs/WEB_ARCHITECTURE_v0.1.md`,
    `docs/EVENT_MODEL_v0.2.md`, `docs/API_CONTRACT_v0.1.md`
- **Standalone web (earlier monolith):** https://github.com/jcrawford2000/emberlog-web
  - `src/App.tsx` — earlier single-file dashboard with the system-card grid,
    search/filter bar, and the rich recent-calls table reproduced in the UI kit.
- **Related / ecosystem:** https://github.com/jcrawford2000/emberlog-api ·
  https://github.com/jcrawford2000/trunk-recorder

**Stack signals from `package.json`:** React 19, React Router 7, Tailwind CSS v4,
daisyUI 5, `lucide-react`, `@fortawesome/*` (free-solid), `framer-motion`, `zod`.

---

## Content fundamentals — how Emberlog writes

The voice is **operational, terse, and technically precise** — it reads like
public-safety / monitoring tooling, never marketing.

- **Tone:** factual and calm. State what is happening; don't editorialize.
  Platform docs add a quiet, almost doctrinal authority ("Contracts are the
  constitution of Emberlog.").
- **Person:** **second-person imperative or neutral system voice**, not "we".
  UI speaks *about the system* ("No systems are currently reporting decode
  rates."), not about the company.
- **Casing:** **Title Case for nav items, section headers, and buttons**
  ("Traffic Monitor", "Recent Calls", "Filter Calls", "Clear filters").
  **Sentence case for descriptions and empty/error states.**
  **ALL-CAPS only for compact status flags** — `ENC`, `REC`, `LIVE`.
- **Domain vocabulary (use precisely):** *system / site, talkgroup / trunkgroup,
  decode rate, control channel, call, encrypted, recording, live / ended,
  emergency, TDMA / Phase 2, snapshot, live stream, contract, hub, module, event*.
- **Numbers & units:** explicit and spelled out — `97.4%`, `0.85000 MHz`
  (5-dp frequency), `12s ago`, `3:07` elapsed, `SRC 1042 • REC 3`. Raw decode
  rate is shown as `34.0 / 40`.
- **Status microcopy:** short, lowercase or single-word — `Live`, `Reconnecting`,
  `Connecting`, `Offline`, `Polling fallback (5s)`, `Last fetch: 12s ago`.
- **Empty / error states are mandatory and plain-spoken:**
  "No recent calls yet." · "No systems are currently reporting decode rates." ·
  "Failed to load traffic data. Retrying automatically." (always pair errors with
  a **Retry** affordance).
- **Emoji:** essentially none in the UI. The platform README uses **🔥📜** beside
  the wordmark as a brand flourish — treat that as a docs/brand-mark accent only,
  **not** a UI pattern. Don't sprinkle emoji into product surfaces.
- **Helper / legend copy** sits in a muted footer and explains iconography in
  full sentences ("Talkgroups marked with 🔒 are encrypted.").

**Examples (verbatim from code):**
- H1: `Traffic Monitor` — sub: `Snapshot from /api/v1/traffic/summary + live updates from /api/v1/sse`
- Button: `Filter Calls` / `Showing Filter` · `Clear filters` · `Details` · `Retry`
- Eyebrow label (group): `PHOENIX FIRE` (uppercase, wide tracking)
- Flag chips: `ENC`, `REC`, `LIVE`, `Emergency`, `TDMA 1`

---

## Visual foundations

**Overall vibe:** a dark **firehouse / public-safety operations console**. Charcoal
gear-gray canvas, a bold fire-engine-red header bar, safety-orange for "live/active"
emphasis, brass-gold as a sparing tertiary accent, and **slate-dark data panels**
for tables and gauges. Dense but legible; utilitarian, not decorative.

- **Color usage:**
  - App background is **charcoal `#2E2E2E`** (`--color-surface`). The sticky
    **header is fire-engine red `#B22222`** (`bg-engine`) with a subtle backdrop blur
    and a white-alpha bottom border.
  - **Safety orange `#FF6B00`** = active/live + selection emphasis (selected card
    ring, live row tint, live dot). **Brass `#FFD447`** = tertiary highlight.
  - Two card paradigms coexist: a **light card** (`#FAFAFA`, dark `#1C1C1C` text,
    `--radius-card: 1rem`, `shadow-xl`, `#444` border) used for KPI/system cards,
    and **slate-dark panels** (`#0F172A` body / `#1E293B` head) used for the
    recent-calls table, gauge wells, and detail modals.
  - **Status semantics:** ok = emerald `#10B981`, warn = amber `#F59E0B`,
    bad = rose `#F43F5E`, idle/unknown = slate `#94A3B8`. Connection dots use the
    lighter -300 ramp (lime / amber / sky / rose).
- **Typography:** **no custom webfont ships** — Emberlog uses the platform
  **system sans stack** (`ui-sans-serif, system-ui, …`) and a **system mono stack**
  (`ui-monospace, SFMono-Regular, Menlo, …`) for IDs/frequencies. Weights run
  medium → extrabold; gauge values are `extrabold`, headings `semibold`. Group
  labels are uppercase with wide `0.2em` tracking. Page H1 ≈ 24px.
- **Spacing & layout:** centered content in a `max-w-7xl` container, `px-4`,
  `py-6`, `space-y-6` rhythm. **Sticky header** (`z-20`). System health is a
  responsive grid (`md:grid-cols-2` → `lg:grid-cols-5`). The data table scrolls
  horizontally inside a rounded, bordered panel.
- **Backgrounds:** flat solid fills — **no photographic imagery, no full-bleed
  hero images, no repeating textures.** The one "graphic" flourish is the
  **radial decode-rate gauge**: a `conic-gradient` ring (status-accent → faint
  white track) around a dark inner well. Subtle `backdrop-blur` on the header.
- **Borders & hairlines:** on dark chrome, borders are **white-alpha** (`/10`,
  `/15`, `/20`); on light cards a solid `#444`. Inputs and tables use
  `rounded-xl` (0.75rem); pills/gauges/dots are fully round; modals & the logo
  tile are `rounded-2xl` (1rem).
- **Corner radii:** pills/dots = full · inputs, tables, alerts = `0.75rem` ·
  cards = `1rem` · modals & logo tile = `1rem`.
- **Shadows / elevation:** light cards carry `shadow-xl`; modals `shadow-2xl`.
  Selection is communicated with a **ring** rather than a heavier shadow — the
  selected gauge gets `0 0 0 3px rgba(178,34,34,0.2)` (engine-red), selected
  system cards get `ring-2` in safety-orange.
- **Transparency & blur:** used for chrome and overlays only — header
  `bg-engine/95 backdrop-blur`; modal scrims `bg-black/55`; tinted flag chips use
  `~15%` color fills over slate. Body content stays opaque.
- **Animation (framer-motion available, used sparingly):** the only ambient motion
  is the **pulsing live dot** (`animate-pulse`) on live calls/rows; cards lift
  slightly on hover (`hover:-translate-y-0.5`) and gauges scale `1.01` on hover.
  No bounces, no parallax, no entrance choreography. Transitions are short
  `transition` fades on color/transform. Respect `prefers-reduced-motion`.
- **Hover states:** white-alpha fills lighten (`bg-white/5 → /10`); light cards
  lift; buttons gain a faint brass/white tint. **Press/active/selected:** ring +
  accent-tinted background + accent text (engine-red or safety-orange).
- **Imagery color vibe:** N/A — the product ships no photography. If imagery is
  ever needed, keep it cool/desaturated to sit beside the slate panels; never
  warm, glossy stock.

---

## Iconography

See **[ICONOGRAPHY](#iconography-detail)** below — the short version:

- **Primary set: [Lucide](https://lucide.dev)** (`lucide-react`), 1.5–2px stroke,
  rounded caps/joins, drawn at `h-3.5/4/4.5`. Icons seen in code:
  `AudioLines` (the brand mark), `Radio`, `Lock`, `Shield`, `Info`, `Search`,
  `TowerControl`, `AudioLines`.
- **Secondary: Font Awesome** free-solid (`@fortawesome/*`) is a declared
  dependency for occasional solid glyphs.
- **No icon font of its own, no custom SVG sprite, no PNG icons.** Emoji is **not**
  used in product UI (only 🔥📜 in the README brand mark).
- **Substitution flag:** there is **no standalone logo asset** in the repo — the
  header mark is a Lucide `AudioLines` glyph in a rounded safety-orange tile. The
  files in `assets/` recreate that faithfully (see Caveats).

<a name="iconography-detail"></a>
### Iconography — detail

The app renders icons exclusively through `lucide-react` (and has Font Awesome
available). Stroke icons are small and functional, paired with text in flag chips
and buttons (`inline-flex items-center gap-1`). The **brand mark itself is an
icon**: `<AudioLines>` inside a rounded tile — the wordmark "Emberlog" sits to its
right with a muted sub-label. Because Lucide is CDN-available, mocks should load it
from `https://unpkg.com/lucide@latest` rather than hand-drawing glyphs. Reserve
ALL-CAPS labels (`ENC`/`REC`/`LIVE`) as the textual companions to `Lock`/`Radio`.

---

## Files in this folder (index)

| Path | What it is |
|---|---|
| `README.md` | This document — context, voice, visual foundations, iconography |
| `colors_and_type.css` | CSS custom properties for color + type, plus semantic helper classes |
| `assets/emberlog-mark.svg` | Brand mark (AudioLines glyph in a safety-orange tile) |
| `assets/emberlog-logo-lockup.svg` | Full logo lockup (mark + wordmark + sub-label) |
| `preview/` | Small design-system cards (colors, type, components) for the DS tab |
| `ui_kits/web-console/` | High-fidelity recreation of the Emberlog web console |
| `SKILL.md` | Agent-Skills manifest so this system works in Claude Code |

### UI kits
- **`ui_kits/web-console/`** — the operations console shell hosting two domains:
  **Traffic Monitor** (app shell + red header, system-health gauges, system-card
  grid, recent-calls table, filters, modals) and **Dispatch Intelligence** (the
  reference design used for the implemented `dispatch` domain — a color-coded
  incident feed with a full filter system keyed off the official Phoenix Regional
  unit-number blocks, audio waveform, transcript toggle, and Traffic correlation).
  The nav switches between them. `index.html` is an interactive click-through;
  see its own `README.md` for component coverage.

---

## Caveats / substitutions

- **No custom webfont** ships with Emberlog — this is intentional; the brand uses
  the OS system sans + mono stacks. No substitution was needed (and no font files
  were copied).
- **No logo asset exists in the repos.** The brand mark is a Lucide `AudioLines`
  icon in a rounded orange tile (per the app header). `assets/emberlog-*.svg`
  recreate this from the real icon — if you have an official Emberlog logo, drop
  it into `assets/` and update these previews.
- **Icons** are loaded from the Lucide CDN in previews (the app uses the identical
  `lucide-react` set), so iconography is faithful, not substituted.
