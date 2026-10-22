# AACF Changelog

## [2.0.0] - 2026-07-15

Major expansion into a full framework: guardrails + unified UX + security/governance/compliance +
an agent roster, built on a deep review of the mid-2026 state of the art (`docs/STATE_OF_THE_ART.md`).

### Added
- **`AGENTS.md`** — tool-agnostic entry point following the open AGENTS.md standard (the convergent
  base-instructions layer for Claude Code / Cursor / Copilot / Windsurf / Gemini CLI / Codex).
- **`rules/atexis-hard-rules.md`** — the ATEXIS Hard Rules HR0–HR21 brought into the framework.
- **`rules/ai-output-safety.mdc`** — safety rules specific to AI-generated code (OWASP LLM Top 10,
  slopsquatting/supply-chain, prompt-injection, excessive-agency, structured-output-as-control).
- **`agents/`** — agent roster: the four workspace agents (checklist-creator / -implementer /
  -validator, codebase-hardening) ported in, plus new **senior-prompt-engineer**, **code-reviewer**,
  and **security-reviewer** agents, with a roster README and golden-path composition.
- **`governance/security-governance-compliance.md`** — control catalogue mapping ISO/IEC 27001
  (A.8.25–A.8.34), GDPR, NIST SSDF/800-218A, SLSA, OWASP web + LLM Top 10, and the EU AI Act, with a
  one-implementation-many-audits cross-mapping.
- **`governance/guardrails.md`** — deterministic, non-bypassable enforcement (pre-commit hooks,
  secret-scan gates, dependency allowlist + cooldown, branch protection, HITL gates, audit logging,
  DLP) with a per-tier minimum bar.
- **`styles/design-system.md`** — the unified UX framework as three layers (DTCG tokens → shadcn
  `registry:base` preset → agent Skill/MCP), with WCAG 2.2 AA acceptance criteria.
- **`docs/STATE_OF_THE_ART.md`** — the mid-2026 research foundation with sources.

### Changed
- `styles/branding.md` — corrected primary palette to **ATEXIS blue `#2E74B5`**; noted DTCG/OKLCH
  token source of truth.
- `README.md` — rewritten around the framework's four pillars and an index.
- Ported agents now reference `rules/atexis-hard-rules.md` instead of the workspace `CLAUDE.md`.

## [1.0.0] - 2025-01-01

### Added
- Initial AACF framework structure
- Templates: web-app, api-service, data-pipeline, internal-tool, automation-script
- Global rules (10 rules)
- IDE rules: atexis-global.mdc, security.mdc, python.mdc, javascript.mdc, dotnet.mdc
- Project context files: PROJECT_CONTEXT.md, SECURITY_CONTEXT.md
- UI kit component library definitions
- Branding assets (colours, fonts, design tokens)
- Tier governance checklists (T1-T4)
- Code review guidelines
- Prompt library (system prompts, templates, anti-patterns)
