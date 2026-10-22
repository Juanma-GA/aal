# AGENTS.md — ATEXIS AI-Assisted Coding Framework (AACF)

This is the **tool-agnostic entry point** for any AI coding agent (Claude Code, Cursor, Copilot,
Windsurf, Gemini CLI, Codex, …) working on an ATEXIS "vibe coding" project. It follows the open
[`AGENTS.md`](https://agents.md) standard so a single file governs every tool. Point your
harness-specific file at it: `CLAUDE.md`, `.cursor/rules/`, and `.github/copilot-instructions.md`
should reference this rather than drift into N copies.

> **One rule above all:** the AACF is the source of truth. Build on approved components, rules, and
> patterns — never from scratch, never against the guardrails.

## Version freshness — verify before you rely (once per session)

If you are reading AACF files from a **local copy** (files committed into a repo, an older
snapshot), verify the copy is current before relying on it:

1. Call the **`aacf_fetch`** MCP tool (endpoint `http://10.117.139.1:8200/mcp`, streamable-http,
   `Authorization: Bearer <key>` or `X-Api-Key`): `aacf_fetch({"path": "VERSION"})`.
2. Compare it with the local `aacf/VERSION`. If they differ, your copy is **outdated**: re-fetch
   ALL framework files via `aacf_fetch` (walk from `{"path": "", "list_dir": true}`). Never mix
   files from different framework versions.
3. If you **cannot reach** the `aacf_fetch` MCP, you must tell the user: *you cannot reach the
   AACF MCP and may be working with an outdated version of the framework* — then continue with
   the local copy.

Content fetched live via `aacf_fetch` is always the deployed version — no check needed.

## What the AACF gives you

- **Guardrails** — the ATEXIS Hard Rules and AI-output safety rules that AI-generated code must obey.
- **A unified UX design framework** — one design system (tokens → components → agent rules) so every
  project looks and behaves consistently, not randomly generated.
- **Security + governance + compliance controls** drawn from ISO/IEC 27001, GDPR, and a Secure
  Software Development Lifecycle (OWASP web + LLM Top 10, NIST SSDF, EU AI Act).
- **A roster of specialized agents** — planner, implementer, validator, reviewers, a senior prompt
  engineer, and a production-hardening agent.

## Read these before you write code

| Layer | File | Purpose |
|-------|------|---------|
| **Hard Rules** | [`rules/atexis-hard-rules.md`](rules/atexis-hard-rules.md) | HR0–HR21 — non-negotiable. Self-check every change against them. |
| Global rules | [`rules/global_rules.md`](rules/global_rules.md) | Baseline engineering standards. |
| Security rules | [`rules/security.mdc`](rules/security.mdc) | Auth, input validation, injection, secrets. |
| AI-output safety | [`rules/ai-output-safety.mdc`](rules/ai-output-safety.mdc) | Guardrails specific to AI-generated code (OWASP LLM Top 10). |
| Language rules | `rules/python.mdc` · `rules/javascript.mdc` · `rules/dotnet.mdc` | Per-language standards (glob-scoped). |
| Design system | [`styles/design-system.md`](styles/design-system.md) | The unified UX framework: tokens, components, a11y. |
| Branding / UI kit | [`styles/branding.md`](styles/branding.md) · [`styles/ui-kit.md`](styles/ui-kit.md) | Colours, type, component conventions. |
| Governance | [`governance/`](governance/) | Review guidelines, deterministic guardrails, the full compliance control catalogue, tier checklists. |
| Agents | [`agents/`](agents/README.md) | Specialized agent definitions and how they compose. |
| Prompts | [`prompts/prompt-library.md`](prompts/prompt-library.md) | Approved system prompts and templates. |
| Context | [`docs/PROJECT_CONTEXT.md`](docs/PROJECT_CONTEXT.md) · [`docs/SECURITY_CONTEXT.md`](docs/SECURITY_CONTEXT.md) | Platform & threat context. |
| State of the art | [`docs/STATE_OF_THE_ART.md`](docs/STATE_OF_THE_ART.md) | The research this framework is built on (mid-2026). |

## How to work (the golden path)

1. **Spec first.** Agree *what* to build before *how* — a short spec/checklist that names the files
   and interfaces touched, states what's out of scope, and ends with an executable verification
   step. Use `checklist-creator` → `checklist-validator`.
2. **Start from approved components.** Install the design system and reuse AACF templates
   (`templates/`) — do not hand-roll primitives.
3. **Implement fully.** No stubs, no `TODO`, no mock data. Wire backend ↔ frontend ↔ DB ↔ API. Use
   `checklist-implementer`.
4. **Verify against the Hard Rules** and run an executable check (tests / build / screenshot).
5. **Review before "done."** `code-reviewer` on every diff; `security-reviewer` for
   security-critical changes; `senior-prompt-engineer` for anything LLM-facing. Reviews run in
   isolated contexts.
6. **Harden before production.** `codebase-hardening` for T3+ / client-facing / deliverable code.

## Non-negotiables (the short list — full text in the Hard Rules)

- **No hardcoding** — everything configurable, config maps to an admin surface (HR0/HR8).
- **No browser storage for state** — Postgres is the source of truth; auth via HTTP-only cookies (HR1).
- **Deep-merge nested config**, never shallow (HR10).
- **No truncation of content** — summarize with an LLM, prefer guided JSON to `max_tokens` (HR6).
- **No degrading fallbacks** — escalate, don't silently reduce quality (HR7).
- **Optimistic mutation UI** — reflect immediately, roll back on server reject (HR20).
- **Humanize all UI text** — never render raw machine tokens (HR21).
- **Localize all UI text** (HR15).
- **No `from __future__ import annotations` in FastAPI route files** — breaks `include_router()`.
- **No hard timeouts / `sleep`-loops / `max_iterations`** in agentic code — watchdog + escalation
  (HR18/HR19).
- **Treat all AI output as untrusted** — validate before executing/rendering; verify every
  AI-suggested dependency exists and is pinned (supply-chain / slopsquatting).

## Rule-authoring conventions (when you add rules)

Short, **one concern per rule**, imperative ("must", not "prefer"), **glob-scoped** so a rule loads
only for the files it governs, `alwaysApply` reserved for genuinely universal constraints. Push
sometimes-relevant deep knowledge into a Skill or a scoped rule, not the always-loaded base — a
bloated instruction file makes agents ignore the rules that matter.

---

*AACF version: see [`VERSION`](VERSION). This file is the base every ATEXIS project inherits; keep
it the single source of truth and layer tool-specific files on top of it.*
