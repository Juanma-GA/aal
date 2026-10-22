# State of the Art — AI-Assisted Coding Frameworks (mid-2026)

The research foundation the AACF v2.0 is built on: how leading teams structure the rules/agent/UX/
governance layers for AI-assisted development, as of mid-2026. This is the "latest, most informed
approach" — kept in the framework so the *why* behind each convention is auditable.

---

## 1. Rules & agent layer — the convergence

The per-tool file chaos of 2024 has converged onto open standards:

- **`AGENTS.md` won the base-instructions layer.** Plain Markdown, no required fields, nearest-file
  wins in monorepos. Formalised as an open spec (Aug 2025), donated to the Linux Foundation's
  Agentic AI Foundation (Dec 2025), adopted by 60,000+ repos and read natively by Codex, Cursor,
  Copilot, Gemini CLI, Aider, Windsurf, Zed. **This is the single highest-leverage file to add.**
  ([agents.md](https://agents.md))
- **Scoped rules, not a dump.** Cursor `.cursor/rules/*.mdc` (frontmatter `description`/`globs`/
  `alwaysApply`; four activation modes), Copilot `*.instructions.md` (`applyTo` glob), Cline
  `.clinerules/` (paths frontmatter). Best practice: **5–8 rules, one concern each, imperative
  voice, glob-scoped, `alwaysApply` only for universal constraints.** The `.cursorrules` single-file
  format is deprecated.
- **`CLAUDE.md` + `.claude/agents/*.md` + Skills** for Claude Code. Anthropic's own guidance:
  *"Bloated CLAUDE.md files cause Claude to ignore your actual instructions"* — the litmus test per
  line is "would removing this cause a mistake? If not, cut it." Sometimes-relevant knowledge →
  **Skills (progressive disclosure)**, not the always-loaded base.
  ([Claude Code best practices](https://code.claude.com/docs/en/best-practices))

**Sub-agent patterns:** specialized agents in their own files with a **trigger-condition
`description`** and a **minimal tool allowlist** (reviewers get no write). Orchestrator-worker (lead
plans → writes plan to memory → fans out workers with self-contained tasks + explicit output
formats) beat single-agent by >90% in Anthropic's research system. **Writer/reviewer separation** —
a fresh reviewer sees only the diff + criteria — but tell it to *"flag only gaps that affect
correctness or requirements,"* or it invents work.
([Anthropic multi-agent](https://www.anthropic.com/engineering/), [sub-agents](https://code.claude.com/docs/en/sub-agents))

**Spec-driven development:** GitHub **Spec Kit** (Specify → Plan → Tasks → Implement, ~111k★,
agent-agnostic) and Anthropic's interview→`SPEC.md`→fresh-session variant. Specs name the files/
interfaces touched, state what's out of scope, and end with an **executable verification step**.
([github/spec-kit](https://github.com/github/spec-kit))

**Context engineering** replaced prompt engineering as the primary skill. "Context rot" is measured
— all frontier models degrade as input grows. Fixes: ruthless pruning, progressive disclosure,
just-in-time retrieval, external memory, small tool sets, and **deterministic hooks for
must-happen rules** (advisory prose gets lost). ([Sourcegraph](https://sourcegraph.com/blog/context-engineering))

> **AACF adoption:** `AGENTS.md` as the tool-agnostic base (`../AGENTS.md`); scoped `.mdc` rules
> (one concern, glob-scoped); an agent roster with trigger-condition descriptions + least-privilege
> tools (`../agents/`); spec-first golden path; deterministic guardrails
> (`../governance/guardrails.md`) for the non-negotiables.

---

## 2. Security, governance & compliance

- **OWASP Top 10 for LLM Applications (2025)** is the canonical threat map; the risks that actually
  bite AI-*assisted development* are LLM01 injection, LLM02 secret/PII disclosure, LLM03 supply
  chain, LLM05 improper output handling, LLM06 excessive agency, LLM09 over-reliance.
  ([genai.owasp.org/llm-top-10](https://genai.owasp.org/llm-top-10/))
- **Slopsquatting is the highest-signal new risk**: ~19.7% of AI-generated code hallucinates package
  names and ~43% recur, making them pre-registerable by attackers. Mitigate with dependency
  allowlists, install cooldowns, existence/registration checks, lockfile+hash pinning, SBOM.
  ([CSA research note](https://labs.cloudsecurityalliance.org/research/csa-research-note-slopsquatting-ai-supply-chain-20260419-csa/))
- **NIST SSDF (SP 800-218)** + the GenAI companion **SP 800-218A**; **SLSA** build provenance (L2
  min, L3 high-value); **Microsoft SDL for AI**. ([NIST SSDF](https://csrc.nist.gov/projects/ssdf))
- **ISO/IEC 27001:2022** secure-development controls **A.8.25–A.8.34** + logging (A.8.15), crypto
  (A.8.24), dev/test/prod separation (A.8.31); **ISO/IEC 42001:2023** as the AI-management umbrella
  whose impact-assessment control unifies GDPR DPIA + AI Act risk-management.
  ([ISO 42001](https://www.iso.org/standard/42001))
- **GDPR**: no personal data to external models, data minimization, DPIA triggers, purpose
  limitation, RoPA, honourable data-subject rights, DPA no-training terms.
- **EU AI Act**: classify every system; AI-literacy (Art. 4) and prohibited-practice (Art. 5) apply
  now; high-risk regime deferred to **2 Dec 2027** (Digital Omnibus) — build the roadmap now;
  transparency (Art. 50) = label AI outputs.
- **The strongest move is deterministic, non-bypassable guardrails**: pre-commit hooks, hard
  secret-scan merge gates, dependency allowlists + cooldown, branch protection barring agent pushes
  to `main`, human-in-the-loop gates, full audit logging to SIEM, DLP on prompts.

> **AACF adoption:** the full control catalogue
> (`../governance/security-governance-compliance.md`), the enforcement layer
> (`../governance/guardrails.md`), and the `ai-output-safety.mdc` rule.

---

## 3. Unified UX / design framework

Consistency across many AI-generated apps comes from **encoding the design system as machine-readable
data + agent-readable rules** — three layers:

- **Tokens** — W3C Design Tokens (DTCG) format reached first stable spec **2025.10**; author one
  `*.tokens.json` (OKLCH colours), compile with **Style Dictionary** into CSS custom properties +
  Tailwind theme. ([W3C DTCG](https://www.designtokens.org/tr/2025.10/format/))
- **Components** — **shadcn/ui** (code-in-repo, so the agent can read/extend it) shipped as a private
  **`registry:base` preset** (CLI v4, Mar 2026): `npx shadcn init <registry>` is the golden-path
  starter. ([shadcn registry](https://ui.shadcn.com/docs))
- **Agent** — a shadcn **Skill** reads `components.json`/`shadcn info` and enforces composition
  rules; a private registry over **MCP** gives the agent a constrained palette. Non-negotiable
  acceptance: semantic tokens (no raw values), **WCAG 2.2 AA**, `prefers-reduced-motion`, responsive,
  humanized + localized text. ([shadcn Skills](https://ui.shadcn.com/docs/skills), [Vercel v0](https://vercel.com/blog/ai-powered-prototyping-with-design-systems))

> **AACF adoption:** `../styles/design-system.md` (three layers), `../styles/branding.md` (tokens),
> `../styles/ui-kit.md` (components).

---

## 4. Senior prompt engineering

What distinguishes a *senior* prompt engineer: **evals, versioning, adversarial testing,
model-specificity, and system-level safety** — not clever one-off strings.

- **Context engineering** — finite attention budget; smallest high-signal token set; JIT retrieval;
  compaction + sub-agents for long-horizon. ([Anthropic](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents))
- **Model-conditional** — techniques don't port: don't force CoT on a reasoning-router model; put
  the question last for Gemini; prefill for Claude JSON. ([OpenAI GPT-5 guide](https://developers.openai.com/cookbook/examples/gpt-5/gpt-5_prompting_guide))
- **Structured/guided output** is the highest-leverage control per hour — closes exfiltration
  classes by construction (HR6 alignment).
- **Injection defense is system-wide** — published in-prompt defenses were bypassed >90% of the
  time; enforce via schema + tool scoping + retrieval hygiene + auth.
- **Evals as a release gate** — golden + adversarial corpus, versioned, run on every prompt/model
  change.

> **AACF adoption:** the [`senior-prompt-engineer`](../agents/senior-prompt-engineer.agent.md) agent
> and the senior-PE section of `../prompts/prompt-library.md`.

---

## The one durable bet

Build on the **open, cross-tool standards** — `AGENTS.md` + Skills + Spec Kit (Linux Foundation /
MIT governed) — rather than any single vendor's proprietary file. That is what keeps the AACF
portable as the tool landscape keeps churning.

---

*Compiled mid-2026 from primary sources (OWASP, NIST, ISO, W3C, Anthropic/OpenAI/Google docs) and
current secondary reporting. Some figures (hallucination rates, the EU AI Act Digital Omnibus
deferral date) are from secondary reporting — verify against primary texts before external
publication.*
