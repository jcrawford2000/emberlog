---
name: emberlog-design
description: Use this skill to generate well-branded interfaces and assets for Emberlog, either for production or throwaway prototypes/mocks/etc. Emberlog is an open-source, contract-first platform for Trunk Recorder ecosystems (real-time trunked-radio traffic monitoring, system-health telemetry, dispatch intelligence). Contains essential design guidelines, colors, type, fonts, assets, and UI kit components for prototyping.
user-invocable: true
---

Read the `README.md` file within this skill, and explore the other available files:

- `README.md` — product context, content/voice rules, visual foundations, iconography, file index
- `colors_and_type.css` — color + type CSS custom properties and semantic helper classes (copy/import this)
- `assets/` — brand mark + logo lockup (the mark is a Lucide `audio-lines` glyph in a safety-orange tile)
- `preview/` — small reference cards for colors, type, spacing, components, brand
- `ui_kits/web-console/` — high-fidelity, interactive recreation of the Emberlog Traffic Monitor console (header, decode-rate gauges, recent-calls table, filters, detail modal)

If creating visual artifacts (slides, mocks, throwaway prototypes, etc.), copy assets out
and create static HTML files for the user to view. Load Lucide icons from CDN
(`https://unpkg.com/lucide@latest`) — the product uses the same set. If working on
production code, copy assets and read the rules here to become an expert in designing
with this brand (the live app is React 19 + Tailwind v4 + daisyUI 5 + lucide-react).

Key brand reminders:
- Dark **firehouse / public-safety** console: charcoal `#2E2E2E` canvas, **fire-engine-red `#B22222`** header, **safety-orange `#FF6B00`** for live/active, brass `#FFD447` accent, slate-dark data panels.
- Status semantics: ok `#10B981` / warn `#F59E0B` / bad `#F43F5E` / idle `#94A3B8`.
- System font stacks (no custom webfont). Title Case for nav/headings/buttons; ALL-CAPS only for compact flags (`ENC` / `REC` / `LIVE`). Terse, operational voice — never marketing. No emoji in product UI.
- **Traffic** and **Dispatch** are implemented in the product. The Dispatch
  design in the UI kit remains a reference/prototype source (color-coded incident
  feed + filters keyed off the Phoenix Regional unit-number blocks). Systems /
  Scanner / Command remain planned — don't invent them.

If the user invokes this skill without any other guidance, ask them what they want to
build or design, ask some questions, and act as an expert designer who outputs HTML
artifacts _or_ production code, depending on the need.
