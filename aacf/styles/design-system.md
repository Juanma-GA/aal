# Unified UX Design Framework

One design language for **every** ATEXIS vibe-coding project, so AI-generated UIs are consistent by
construction — not random. The principle from the state of the art (`../docs/STATE_OF_THE_ART.md`):
**consistency comes from making the design system a shared installable artifact + a shared agent
instruction, not from hoping each generation "matches the vibe."**

The system is **three layers**, each a real artifact projects consume:

```
   ┌──────────────────────────────────────────────────────────────┐
   │  Layer 3 — AGENT layer   (rules + Skill + MCP registry)       │  how the AI follows it
   ├──────────────────────────────────────────────────────────────┤
   │  Layer 2 — COMPONENT layer  (shadcn registry:base preset)     │  the golden-path starter
   ├──────────────────────────────────────────────────────────────┤
   │  Layer 1 — TOKEN layer  (DTCG *.tokens.json → CSS vars)       │  the single source of truth
   └──────────────────────────────────────────────────────────────┘
```

## Layer 1 — Tokens (the single source of truth)

- Author **one** design-tokens file in the **W3C Design Tokens (DTCG) format** (first stable spec
  2025.10): `design.tokens.json`. Colours in **OKLCH**, plus spacing, type scale, radii, motion, and
  light/dark + brand themes. `$`-prefixed properties, aliases/inheritance.
- Compile it with **Style Dictionary** into `globals.css` **CSS custom properties** + the Tailwind
  theme. Nothing hardcodes a hex or a px value — components reference **semantic token variables**
  (`--color-primary`, `--radius`, `--space-md`), never raw values. This is the design-system
  expression of **HR0/HR8 (no hardcoding, everything configurable)**.
- Canonical values live in [`branding.md`](branding.md) (ATEXIS blue `#2E74B5`, Inter / JetBrains
  Mono, spacing/radius scale, semantic + tier colours). Treat that file as the human-readable
  mirror of the token source.

## Layer 2 — Components (the golden-path starter)

- Standardise on **shadcn/ui + Tailwind** — code lives *in the project* (not a black-box dep), so
  the agent can read, understand, and extend it. This is why v0 and most AI tools default to it.
- Ship the ATEXIS components as a **private shadcn `registry:base` preset** (CLI v4). Then the
  golden path for a new project is a single command:

  ```bash
  npx shadcn init <atexis-registry>     # installs tokens, fonts, config, vetted components
  ```

  Every project starts **identical by construction** — same tokens, same primitives, same config.
- Component conventions (buttons, forms, tables, nav, cards, dialogs, toasts) are in
  [`ui-kit.md`](ui-kit.md). Compose from the registry; **never hand-roll a primitive** that already
  exists.

## Layer 3 — Agent (how the AI follows it)

- Provide a **design-system rule / Skill** that: detects `components.json`, reads the project's real
  config (`shadcn info --json` — framework, Tailwind version, aliases, icon lib, installed
  components), and **enforces composition rules** before generating (e.g. use `FieldGroup` for
  forms, `ToggleGroup` for option sets, semantic colours only).
- Expose the private registry over an **MCP server** so the agent installs from a *constrained
  palette* rather than inventing markup.
- The agent's non-negotiable acceptance criteria for any UI it produces:
  - **Reference semantic token variables, never raw hex/px.**
  - **WCAG 2.2 AA** — meaningful alt text (not placeholder), sufficient contrast, visible keyboard
    focus, real labels.
  - **`prefers-reduced-motion` respected**; auto-moving content > 5s is pausable (WCAG 2.2.2).
  - **Responsive down to mobile.**
  - **Humanize all displayed text (HR21)** — never render `snake_case` / enum keys / status slugs;
    replace separators, title-case, format lists readably.
  - **Localize all UI text (HR15)** via the i18n layer.
  - **Optimistic mutation UI (HR20)** — reflect immediately, roll back on server reject.

## The contract & release gate

- A **Storybook** is the human + visual-regression contract for the components.
- CI runs an **accessibility check** (axe / WCAG 2.2 AA) and visual-regression as a **release gate**
  — a UI that fails a11y or drifts from the token system does not ship.

## Why this shape

- **Tokens as data** → one change re-themes every project; no per-project hex drift.
- **Components as an installable preset** → new projects begin consistent, not from a blank canvas.
- **Design system as an agent instruction + constrained MCP palette** → the AI produces on-brand,
  accessible code on the first try instead of plausible-looking but random markup.

*See [`branding.md`](branding.md) for the token values and [`ui-kit.md`](ui-kit.md) for component
conventions. Research & sources: [`../docs/STATE_OF_THE_ART.md`](../docs/STATE_OF_THE_ART.md).*
