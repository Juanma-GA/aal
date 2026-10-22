# Security, Governance & Compliance Controls

The control catalogue for AI-assisted / "vibe coding" development at ATEXIS. Drawn from **ISO/IEC
27001:2022**, **GDPR**, a **Secure Software Development Lifecycle** (OWASP web + LLM Top 10, NIST
SSDF/800-218A, SLSA), and the **EU AI Act**. State of the art as of mid-2026
(`../docs/STATE_OF_THE_ART.md`).

Each control states **what**, **why**, and **the clause it maps to**. Enforcement mechanisms (hooks,
gates, scanning) are in [`guardrails.md`](guardrails.md). Every control here is checked by the
[`security-reviewer`](../agents/security-reviewer.agent.md) and, for production, the
[`codebase-hardening`](../agents/codebase-hardening.agent.md) agent.

> **Scope note.** Internal ATEXIS coding assistants make ATEXIS a *deployer/producer* of AI systems.
> Under the EU AI Act Digital Omnibus, the high-risk compliance deadline is deferred to **2 Dec
> 2027**, but AI-literacy (Art. 4) and prohibited-practice (Art. 5) duties already apply, and ISO /
> GDPR obligations bind now. Customer *deliverables* are governed by the customer's own contract +
> ISO 27001 + GDPR (not internal ATEXIS policy); everything else follows the tiered model in
> [`tier-checklists.md`](tier-checklists.md).

---

## 1. OWASP — risks specific to AI-generated code

**OWASP Top 10 for LLM Applications (2025):** LLM01 Prompt Injection · LLM02 Sensitive Information
Disclosure · LLM03 Supply Chain · LLM04 Data & Model Poisoning · LLM05 Improper Output Handling ·
LLM06 Excessive Agency · LLM07 System Prompt Leakage · LLM08 Vector & Embedding Weaknesses · LLM09
Misinformation · LLM10 Unbounded Consumption.

| # | Control | Why | Maps to |
|---|---------|-----|---------|
| 1.1 | Treat all AI output as untrusted — never execute/`eval`/shell/render without validation, encoding, sandboxing. | Prompt injection chains into output handling: injected instructions become code the app runs. | LLM05; OWASP ASVS V1 |
| 1.2 | Separate instructions from data in prompts; structured/parameterized prompts + delimiters; no secrets in system prompts. | Single-channel processing is the root of injection & prompt leakage. | LLM01, LLM07 |
| 1.3 | Verify every AI-suggested package exists and predates the project; block newly-registered packages (30–90 day cooldown). | "Slopsquatting": ~19.7% of AI code hallucinates package names; ~43% recur, so attackers pre-register them. | LLM03 |
| 1.4 | Dependency allowlist + lockfile/hash-pinning; anything else → human review. | Removes the package blind spot; deterministic builds. | LLM03; ISO A.5.21; SLSA |
| 1.5 | Constrain agent agency — least-privilege tokens, no destructive/prod actions without approval. | Excessive agency turns a bad suggestion into an incident. | LLM06 |
| 1.6 | Scan every AI diff for secrets before it lands; never embed credentials. | Assistants both leak and hard-code secrets. | LLM02; ASVS V13 |
| 1.7 | Counter over-reliance — mandatory human review, label AI commits, author must explain the code, fact-check APIs. | Models emit plausible-but-wrong code and invented APIs. | LLM09 |
| 1.8 | Rate-limit & quota AI tooling; monitor token/cost per user & repo. | Runaway cost / DoS via agent loops. | LLM10 |
| 1.9 | Apply **OWASP ASVS 5.0** as the acceptance bar (L1 public non-sensitive, **L2 default**, L3 catastrophic-impact). | ASVS is the normative checklist that catches the injection/authz/crypto defects AI reintroduces. | ASVS 5.0 (V1–V14) |
| 1.10 | Map every AI-generated web feature to **OWASP Top 10 (web)** — esp. A01, A03, A08. | Assistants replicate classic web flaws. | OWASP Top 10 |

---

## 2. Secure SDLC (NIST SSDF / 800-218A, SLSA, Microsoft SDL)

| # | Control | Why | Maps to |
|---|---------|-----|---------|
| 2.1 | Adopt **NIST SSDF (SP 800-218)** as the backbone — PO / PS / PW / RV practice groups. | Recognised auditable baseline; every control below hangs off it. | SSDF v1.1 |
| 2.2 | Overlay **NIST SP 800-218A** (Secure Dev for Generative AI) for any AI component built/fine-tuned/acquired. | The AI-specific SSDLC companion: model/data provenance, training integrity, abuse handling. | SP 800-218A |
| 2.3 | **SAST on every PR** (and pre-merge on AI diffs). | Catches injection/authz defects before merge. | SSDF PW.7/8; ISO A.8.29 |
| 2.4 | **SCA + SBOM** as a mandatory CI step; verify deps against known-good hashes. | Detects vulnerable/hallucinated/malicious deps; SBOM is the provenance auditors expect. | SSDF PS.3/PW.4; SLSA; ISO A.5.21 |
| 2.5 | **DAST** in staging before release. | Runtime validation of the deployed app. | SSDF PW.8; ISO A.8.29 |
| 2.6 | **Secret scanning at three gates** — pre-commit, PR, CI. | Defence-in-depth against AI credential leakage; fires regardless of author. | SSDF PS.1; ISO A.8.24 |
| 2.7 | Adopt **SLSA build provenance** — Build **L2 minimum**, L3 for high-value artifacts; verify with `slsa-verifier`; adopt the Source track. | Signed, tamper-resistant attestation of how/where each artifact was built. | SLSA v1.2 |
| 2.8 | Apply **Microsoft SDL "for AI"** threat-model pillar — AI threat models, observability, stronger agent identity. | Practitioner complement extending secure-dev to agents. | Microsoft SDL |
| 2.9 | **Threat-model AI features before build**; re-model when agent capabilities change. | Agent tool-scope is a new attack surface. | SSDF PW.1 |
| 2.10 | **Vulnerability response (RV)** covering AI-introduced defects & hallucinated-dependency incidents. | Slopsquatting is an ongoing external threat, not a one-time scan. | SSDF RV.1–3 |

---

## 3. ISO/IEC 27001:2022 Annex A (+ ISO/IEC 42001)

**Secure-development controls A.8.25–A.8.34** (exact titles):

| Clause | Title | Applied to the AI coding platform |
|--------|-------|-----------------------------------|
| A.8.25 | Secure Development Life Cycle | Documented secure-dev rules covering AI-assisted authorship and agent use. |
| A.8.26 | Application Security Requirements | Security requirements (incl. handling of AI output) defined before build; ASVS level set here. |
| A.8.27 | Secure System Architecture & Engineering Principles | Sandbox agents, least-privilege tokens, trust boundaries around AI output. |
| A.8.28 | Secure Coding | Secure-coding standards apply to AI output identically to human output. |
| A.8.29 | Security Testing in Development & Acceptance | SAST/DAST/SCA gates (2.3–2.5) are the evidence. |
| A.8.30 | Outsourced Development | Governs external AI coding vendors/models as outsourced dev. |
| A.8.31 | Separation of Dev / Test / Production | Agents never touch prod; branch protection on `main`; per-env creds. |
| A.8.32 | Change Management | AI-authored changes go through the same change-control + review gates. |
| A.8.33 | Test Information | No real personal data in AI prompts/test fixtures (→ GDPR §4). |
| A.8.34 | Protection During Audit Testing | Scope agent/scanner access during audits. |

**Supporting controls:** A.5.15 Access Control (RBAC + least privilege on platform, repos, agent
identities) · A.8.15 Logging (all AI actions centrally logged to the SIEM) · A.8.24 Cryptography
(encrypt in transit/at rest; secrets in a vault, never in prompts/code) · A.5.19–A.5.23
Supplier/ICT-supply-chain governance (DPAs, retention, provider-change review for model providers &
registries).

**ISO/IEC 42001:2023 (AI Management System)** — the umbrella that binds the AI-specific controls onto
the existing ISO 27001 ISMS (PDCA AIMS, 9 objectives / 38 Annex A controls). Its **AI impact
assessment** control unifies the GDPR DPIA and the EU AI Act risk-management artifact into one.

---

## 4. GDPR — AI-assisted development handling personal data

| # | Control | Why | Clause |
|---|---------|-----|--------|
| 4.1 | **Do not send personal data to external models.** Default-deny personal/confidential data in prompts; DLP on egress; prefer self-hosted models; bind no-training/retention terms in the DPA where external use is unavoidable. | Sending personal data to a third-party LLM is a processing + potential transfer event with training-reuse risk. | Art. 5, Art. 28, Ch. V |
| 4.2 | **Data minimisation** — prompts/fixtures carry only necessary data; pseudonymise/anonymise before AI processing; delete when done. | Core Art. 5(1)(c) duty. | Art. 5(1)(c) |
| 4.3 | **DPIA before deploying AI against personal data** — treat AI-on-personal-data as a presumptive high-risk trigger. | Art. 35 requires a DPIA for high-risk processing; LLM-on-personal-data usually crosses the threshold. | Art. 35 |
| 4.4 | **Purpose limitation** — data collected for product X may not be repurposed to prompt/train tooling without a fresh lawful basis. | Art. 5(1)(b). | Art. 5(1)(b) |
| 4.5 | **RoPA** includes AI-assisted-development processing and external-model transfers. | Art. 30 recordkeeping; also feeds AI Act classification. | Art. 30 |
| 4.6 | **Data-subject rights stay honourable** — don't let personal data become irretrievably embedded in a model or vendor logs. | Embedding in an external model can make erasure impossible. | Arts. 15–22 |
| 4.7 | **Provider agreements** fix input/output retention and prohibit training on your data. | Controls residual risk of permitted external use. | Art. 28 |

---

## 5. EU AI Act — practical obligations for internal AI tools

| # | Control | Why | Clause |
|---|---------|-----|--------|
| 5.1 | **Inventory & classify every AI system** — unacceptable / high-risk / limited / minimal. Dev-assistant is usually limited/minimal; anything used for **employment decisions** is high-risk (Annex III). | Obligations scale by tier; misclassifying an HR-adjacent tool is the common trap. | Art. 6 + Annex III |
| 5.2 | **Record the classification** — methodology, criteria, evidence, roadmap. | Demonstrable due diligence; auditable trail. | Art. 6 |
| 5.3 | **AI-literacy for staff using AI tools** — in force since Feb 2025. | Art. 4 applies now, independent of the high-risk deferral. | Art. 4 |
| 5.4 | **Screen against prohibited practices** — no social scoring / manipulative / unlawful biometric use. | Art. 5 prohibitions apply now, heaviest penalties. | Art. 5 |
| 5.5 | **If any system is high-risk, build the full package** — risk management, data governance, technical docs, logging, human oversight, accuracy/robustness, conformity assessment, EU-database registration. Deadline **2 Dec 2027**; build the roadmap now. | High-risk duties are extensive; the deferral buys prep time, not exemption. | high-risk regime |
| 5.6 | **Transparency for limited-risk** — label AI-authored suggestions/outputs; users know they interact with AI. | Art. 50 transparency duty. | Art. 50 |

---

## 6. Cross-standard mapping — one implementation, many audits

| Implementation | OWASP | NIST SSDF/218A | ISO 27001/42001 | GDPR | EU AI Act |
|---|---|---|---|---|---|
| SAST/DAST/SCA + SBOM in CI | LLM03, ASVS | PW.7/8, PS.3 | A.8.29, A.5.21 | — | high-risk data governance |
| Secret scanning (3 gates) | LLM02 | PS.1 | A.8.24 | Art. 32 | — |
| Dependency allowlist + cooldown | LLM03 | PW.4 | A.5.21 | — | supply-chain |
| Branch protection / no agent→`main` | LLM06 | PW.4 | A.8.31/32 | — | — |
| Human review gate | LLM06/09 | PW.7 | A.8.32 | Art. 22 | human oversight |
| Audit logging to SIEM | LLM06 | RV.1 | A.8.15, 42001 | Art. 30 | logging/traceability |
| DLP / no personal data to external models | LLM02 | PS.1 | A.8.24 | Art. 5/28, Ch. V | — |
| DPIA / AI impact assessment | — | — | 42001 impact control | Art. 35 | risk management |

---

## Priorities for ATEXIS

- **Slopsquatting is the highest-signal new risk** for vibe coding — controls 1.3, 1.4, 2.4 and the
  supply-chain guardrails are cheap, deterministic, and go first.
- **Make guardrails non-bypassable** — deterministic hooks, hard secret-scan gates, branch
  protection, full audit logging. Agents can rationalise around advisory prose but cannot pass a
  failing hook (see [`guardrails.md`](guardrails.md)).
- **ISO/IEC 42001 is the umbrella** to bind these AI controls onto the existing ISO 27001 ISMS; its
  impact-assessment control unifies GDPR DPIA + AI Act risk-management.

*Sources & full citations: [`../docs/STATE_OF_THE_ART.md`](../docs/STATE_OF_THE_ART.md). Some
mid-2026 figures (hallucination rates, the Digital Omnibus deferral date) come from secondary
reporting — verify against the primary NIST / Official Journal texts before external publication.*
