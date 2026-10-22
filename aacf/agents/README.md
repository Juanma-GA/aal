# AACF Agents

Specialized agent definitions for AI-assisted development at ATEXIS. Each agent is a Markdown file
with YAML frontmatter (`name`, `description` written as **trigger conditions**, optional `tools`
allowlist and `model`) followed by the agent's system prompt. This format is the convergent 2025–26
standard (Claude Code `.claude/agents/`, and portable to Cursor / Copilot / other harnesses).

Two design principles carried from the state of the art (`../docs/STATE_OF_THE_ART.md`):

- **Isolated context per agent** — each runs in its own context window, keeping the main session
  clean and letting a reviewer grade a change without seeing the reasoning that produced it.
- **Least-privilege tools** — reviewers get **no write access**; a docs agent gets no shell. Narrow
  the `tools` allowlist to what the role needs.

## Roster

| Agent | Role | When to use |
|-------|------|-------------|
| [checklist-creator](checklist-creator.agent.md) | Turns a request into an actionable, codebase-grounded implementation checklist. | Start of any non-trivial feature. |
| [checklist-implementer](checklist-implementer.agent.md) | Executes a checklist item-by-item — full code, zero placeholders, deploy-verified. | Building from an agreed checklist. |
| [checklist-validator](checklist-validator.agent.md) | Validates a checklist/architecture against the codebase + best practice; finds gaps and risks. | Before committing to a plan. |
| [code-reviewer](code-reviewer.agent.md) | Adversarial diff review against the AACF rules + Hard Rules, in a fresh context. | Before marking any T2+ change done; every AI-generated diff. |
| [security-reviewer](security-reviewer.agent.md) | Security & compliance audit (OWASP web + LLM Top 10, ISO 27001, GDPR, SSDLC). | Auth/data/dependency/LLM/infra changes; before T3+ deploy. |
| [senior-prompt-engineer](senior-prompt-engineer.agent.md) | Designs, tests, versions, and hardens prompts / agent instructions / structured-output schemas. | Any LLM-facing feature; unreliable, hallucinating, or injectable prompts. |
| [codebase-hardening](codebase-hardening.agent.md) | Takes vibe-coded / AI-generated code to production — classifies deployment mode, pulls corporate policy, drives security + supply-chain + governance hardening with an evidence-backed report. | Promoting a POC to a real deployment (T3+ / client-facing / deliverable). |

## The golden path (how they compose)

```
checklist-creator ──▶ checklist-validator ──▶ checklist-implementer
                                                     │
                            ┌────────────────────────┼────────────────────────┐
                            ▼                        ▼                         ▼
                     code-reviewer          security-reviewer        senior-prompt-engineer
                       (every diff)        (security-critical)          (LLM-facing)
                                                     │
                                                     ▼
                                            codebase-hardening
                                          (before production / T3+)
```

Reviews run in **isolated contexts** and are **adversarial** — a fresh reviewer told to flag only
gaps that affect correctness, security, or the stated requirement (not to invent work). Spec-driven
flow: agree the checklist/spec first, implement against it, verify with an executable check, then
review before "done."

See `../rules/atexis-hard-rules.md` for the Hard Rules every agent enforces, and
`../governance/` for the review guidelines, guardrails, and compliance controls they draw on.
