# Guardrails — Deterministic Enforcement

Rules an agent can read are advisory; rules a **pipeline enforces** are guarantees. Agents can
rationalise around prose but cannot pass a failing hook. This document lists the *mechanical*
guardrails the AACF expects every ATEXIS project to wire in — the enforcement layer under the
control catalogue in [`security-governance-compliance.md`](security-governance-compliance.md).

The 2026 practitioner "policy stack" for coding agents has six layers: **permission ladders →
pre-tool hooks → OS sandboxes → human-in-the-loop interrupts → audience-bound tokens → threat map
(OWASP)**. Reserve the rules files for judgment; use this layer for the non-negotiables.

## The enforcement layers

| # | Guardrail | Mechanism | Enforces |
|---|-----------|-----------|----------|
| G1 | **Pre-commit hooks** | Secret scan + lint + forbidden-pattern block that can *reject* the commit. Runs whether a human, agent, or script commits. | HR8; ISO A.8.28; SSDF PS.1 |
| G2 | **Secret scanning as a hard merge gate** | Three levels — commit-time (detect-secrets), PR-time (Gitleaks), CI content analysis. | LLM02; ISO A.8.24 |
| G3 | **Dependency allowlist + install cooldown + hash/lockfile verification** | CI blocks packages off the allowlist and packages < 30–90 days old; `npm ci` / hashed `pip`; SBOM on every build. | LLM03 (slopsquatting); ISO A.5.21; SLSA |
| G4 | **Hallucinated-package detection** | CI step verifies each dependency exists + registration date *before* install (e.g. sloppy-joe / supply-chain-guard). | LLM03; SSDF PW.4 |
| G5 | **Branch protection — no agent pushes to `main`** | Agents work on feature branches only; PR + review required to merge; `main` stays a clean undo point. | LLM06; ISO A.8.31/8.32 |
| G6 | **Human-in-the-loop review gates / interrupts** | Mandatory human approval before destructive/high-privilege agent actions and before merge. | LLM06; ISO A.8.32; AI Act human oversight |
| G7 | **Audit logging of every AI action** | File access, shell command, PR, API call → streamed to the SIEM, queryable. | ISO A.8.15; AI Act logging; ISO 42001 |
| G8 | **DLP on prompts** | Inspect/redact/block personal data, secrets, and confidential source leaving to external models. | GDPR Art. 5/28; ISO A.8.24 |
| G9 | **OS sandboxing + least-privilege, short-lived, audience-bound tokens** for agents. | Limits blast radius of a misdirected/compromised agent. | LLM06; ISO A.8.27 |
| G10 | **CI security gates** — SAST + SCA + DAST must pass to merge/release. | Catches injection/authz/dependency defects deterministically. | SSDF PW.7/8; ISO A.8.29 |
| G11 | **Grounding + low temperature** for coding assistants | RAG-ground; reduce randomness to shrink hallucinated packages/APIs (43% of hallucinations are repeatable). | LLM03/LLM09 |
| G12 | **Rate limits & cost quotas** per user and per repo, with a watchdog. | Bounds runaway agent loops without a silent hard cap. | LLM10; HR18/HR19 |

## How this maps to the AACF Hard Rules

- **HR7 (no degrading fallback)** and **HR18/HR19 (watchdog + escalation, no hard caps)** mean a
  guardrail *blocks and escalates* — it never silently downgrades or truncates to keep going.
- **HR6 (no truncation; guided JSON)** is itself a guardrail: structured output closes exfiltration
  classes by construction.
- **HR9 (no destructive data ops without confirmation)** is enforced by G6 (human interrupt) + G5
  (branch protection).

## Minimum bar by tier

| Tier | Required guardrails |
|------|---------------------|
| **T1** (self-service, no sensitive data) | G1, G11, G12; outputs reviewed before commit. |
| **T2** (internal tools) | + G2, G3, G5, G6, G7, G10. |
| **T3** (data-warehouse access) | + G4, G8, G9; column-level access control; DLP on all outputs. |
| **T4** (production / customer-exposed) | All of G1–G12; provenance (SLSA L3) on release artifacts; 24/7 monitoring + anomaly detection. |

Tiers are defined in [`tier-checklists.md`](tier-checklists.md) (the AACF governance-maturity model;
the IdAI platform uses a finer exposure-based T1–T5 + T1-E scheme — map to the nearest AACF tier). The
[`security-reviewer`](../agents/security-reviewer.agent.md) verifies the required guardrails are
present for the target tier; [`codebase-hardening`](../agents/codebase-hardening.agent.md) is the
full production-hardening pass for T3+.

> **The strongest single move:** make the guardrails deterministic and non-bypassable — pre-commit
> hooks (G1), hard secret-scan merge gates (G2), branch protection barring agent pushes to `main`
> (G5), and full audit logging to the SIEM (G7). Everything else is defence-in-depth on top.
