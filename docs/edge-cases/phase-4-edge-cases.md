# Phase 4 — Edge Cases (Refusal, Guardrails, Edge Cases)

Parent reference: [phase-wise-architecture.md](../phase-wise-architecture.md) (Section 7).

| # | Edge case | Why it matters | Suggested handling |
|---|-----------|----------------|-------------------|
| E4.1 | User prefixes factual question with **“Should I…”** | Mixed intent | If guard fires only on prefix, user gets refusal despite factual tail—prefer **intent classifier** or strip-and-reparse with caution; default safe: refusal with explanation. |
| E4.2 | **Jailbreak** wrapped as “hypothetically, which fund is better” | Advice leakage | Refusal template; do not retrieve/compare; no fund rankings. |
| E4.3 | **Out-of-corpus** but user demands a number (e.g. exact expense ratio) | Pressure to hallucinate | Refusal + “not found in pilot corpus”; **no URLs** in the user-visible reply (**1.1**); **no** AMC factsheet as a factual citation. |
| E4.4 | **Performance** question asked as “**What was** last year’s return?” | Factual wording but disallowed computation | Architecture path: no numbers from model; point to **Groww scheme page** as single citation if still offering a pointer; else educational refusal. |
| E4.5 | User asks for **tax advice** for their situation | Not facts-only FAQ | Refusal + SEBI/AMFI generic investor education; no personalized tax computation. |
| E4.6 | **Multi-turn** prior message was advisory; current message is factual | Context pollution | Stateless API: do not carry advisory context into retrieval; or clear system boundary each turn with disclaimer. |
| E4.7 | Classifier **false positive** (factual query marked advisory) | Bad UX | Golden-set tuning; confidence threshold; optional “appeal” copy (“rephrase as a factual question about one scheme”). |
| E4.8 | Classifier **false negative** (advisory marked factual) | Compliance risk | Phase 3 post-checks for advisory language in **answer**; block before return. |

**Refusal vs answer:** Refusal responses must not carry a **fund-fact** citation to non-allowlist domains; educational AMFI/SEBI links are allowed per **1.1** for non-answer pointers only.
