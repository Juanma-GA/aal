---
description: ATEXIS Hard Rules (HR0–HR21) — non-negotiable engineering constraints for all AI-assisted development
globs: **/*
alwaysApply: true
---

# ATEXIS Hard Rules (HR0–HR21)

These are the **absolute, non-negotiable** constraints for every AI-assisted ("vibe coding")
project at ATEXIS. They are the source of the guardrails the AACF enforces. AI coding agents,
human developers, and reviewers are all held to them equally. A change that violates a Hard Rule
is not "done" — it is a defect.

> **How to read this:** each rule is imperative ("must"/"never"), one concern per rule, and
> phrased so it can be checked. When an agent proposes code, it self-checks against this list
> before presenting it; reviewers check against it before approving (see
> `../governance/code-review-guidelines.md`).

## Data & Auth

- **HR0 — Config is a first-class surface.** Every YAML/config setting must have a corresponding
  admin UI section. Nothing tunable is hidden in code.
- **HR1 — No browser storage for state.** Never use `localStorage` / `sessionStorage` for
  authoritative or persistent state. The server (Postgres) is the source of truth.
- **HR8 — No hardcoding.** Everything configurable — endpoints, thresholds, limits, feature
  flags, copy. No magic numbers or magic strings in logic.
- **HR9 — Never delete persistent data without explicit confirmation.** Soft-delete / retain by
  default; destructive operations require an explicit, logged confirmation.
- **HR10 — Deep-merge nested config, never shallow-merge.** Use `deep_merge()`; a shallow merge
  silently drops nested keys.
- **HR15 — All UI text must be localizable.** Route user-facing strings through the i18n layer
  (e.g. `next-intl`); no hardcoded display strings.
- **HR21 — Humanize all user-facing text.** Never render raw machine tokens (snake_case,
  kebab-case, enum keys, status slugs) in the UI. Humanize before display — replace separators,
  title-case, format lists readably. Applies to every surface: cards, tables, detail views,
  notifications, emails.

## Code Quality

- **HR2 — Fix all detected issues, and test every fix.** No known-broken code ships.
- **HR3 — Verify against the actual codebase.** Ground every claim in real files; provide
  references (`path:line`). No assertions about code you haven't read.
- **HR4 — Never silently simplify.** If the task cannot be done as specified, report the blocker
  and escalate — do not quietly ship a reduced version.
- **HR5 — Every code change must be deployed** (via the project's deploy procedure, never by
  hand-copying files).
- **HR6 — No truncation of content.** Never slice quality-bearing or user-facing content (docs,
  history, answers) to fit a limit — use LLM summarization instead. Bounding a machine-consumed
  control signal (a grader/judge structured output) is allowed only when it is code-consumed,
  compressed by the LLM itself (guided decoding / instructed brevity, never slicing), and loses
  zero decision fidelity. Prefer guided JSON over `max_tokens` caps.
- **HR7 — No fallbacks that degrade UX, quality, or data integrity.** A silent lossy fallback is
  worse than a visible failure. Escalate instead.
- **HR11 — No regex for critical operations.** For semantic/critical decisions use an LLM call,
  not a brittle pattern.
- **HR13 — No legacy code.** Remove or refactor dead/duplicated code; don't leave it "just in
  case."
- **HR14 — Single-developer model.** No effort/time estimates; do the work.
- **HR16 — Verify no other deploy is running before starting one.**
- **HR18 / HR19 — No hard timeouts on agentic processes.** No `max_iterations`, no
  `time.sleep()` loops, no silent hard caps. Use a watchdog + escalation for any limit, never a
  silent rejection.
- **HR20 — All mutation UI must be OPTIMISTIC.** Reflect the change immediately, persist in the
  background, roll back only if the server rejects. The only exception is a genuinely
  server-computed / unpredictable result (LLM consolidation, server-generated id) — then apply
  the authoritative response and document why.

## Agentic Workflows

- No `max_iterations`, no `time.sleep()` loops, no hard caps (HR18/HR19).
- No truncation — summarize with an LLM (HR6).
- Escalate rather than fall back (HR7).
- Watchdog + escalation for any limit; never silent rejection.

## Auth & Storage

- Postgres is the source of truth.
- Auth via HTTP-only cookies (server-set), never a JWT in `localStorage`.
- No offline authoritative state.

## Language / Framework Pitfalls

- **Python / FastAPI:** NEVER put `from __future__ import annotations` in a FastAPI route file —
  it breaks `include_router()` silently. Python 3.12 natively supports `str | None` and
  `dict[str, Any]`, so it is unnecessary anyway.

## Anti-Patterns (never ship these)

- `localStorage` / `sessionStorage` for state (HR1)
- `from __future__ import annotations` in route files
- Hardcoded config values (HR8)
- Regex for critical/semantic decisions (HR11)
- Shallow dict merges (HR10)
- Timeout / `sleep`-loop agentic logic (HR18/HR19)
- Truncating content to fit a window instead of summarizing (HR6)
- Blocking a mutation UI on a round-trip when the client already knows the result (HR20)
- Raw machine tokens rendered in the UI (HR21)

---

*These Hard Rules are the ATEXIS-specific layer on top of the AACF global rules
(`global_rules.md`), security rules (`security.mdc`), and AI-output safety rules
(`ai-output-safety.mdc`). Where a general rule and a Hard Rule overlap, the Hard Rule governs.*
