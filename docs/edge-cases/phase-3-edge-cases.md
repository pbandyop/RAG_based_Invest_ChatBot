# Phase 3 — Edge Cases (Retrieval & Grounded Generation)

Parent reference: [phase-wise-architecture.md](../phase-wise-architecture.md) (Section 6, pilot **1.1**).

| # | Edge case | Why it matters | Suggested handling |
|---|-----------|----------------|-------------------|
| E3.1 | Top scores **flat** (no clear winner) | Unstable citation chunk choice | Use secondary sort (recency `fetched_at`, chunk id); or require margin over #2 score to answer, else clarification flow (Phase 4/5). |
| E3.2 | Model emits **http** or **trailing-slash** variant of a valid Groww URL | Allowlist check may fail | Normalize URLs before compare (scheme `https`, strip fragment, optional trailing slash rule—**fixed in code** and documented). |
| E3.3 | Model cites **`groww.in` help** URL not in the five-scheme allowlist | Violates **1.1** | Grounding rejects; regenerate once; if still wrong → safe refusal with educational link (no factual citation). |
| E3.4 | Answer is **4+ sentences** but factually grounded | Spec violation | Truncate is risky; prefer regenerate with stricter prompt or hard fail + refusal. |
| E3.5 | User asks about **Fund A**, retrieval strongest for **Fund B** (name collision) | Wrong citation URL for scheme | Phase 5 scheme selector + Phase 3 metadata filter; if ambiguous, ask user to pick scheme (per architecture **6.2**). |
| E3.6 | Retrieved text contains **marketing language** (“high growth potential”) | Sounds like advice | Post-check forbidden patterns; strip in generation prompt (“do not repeat promotional phrasing”); still cite scheme page if answering a factual field. |
| E3.7 | Question needs **aggregation** (e.g. min SIP across all five funds) | Not in single chunk; risk of hallucination | Refuse partial aggregation or answer only with per-fund disclaimer + point user to each scheme page separately—**still** one citation per architecture means **one scheme per answer**; split into multi-turn or UI “compare” out of scope for pilot. |
| E3.8 | **Footer date** and citation URL **scheme mismatch** (bug in assembly) | Trust break | Integration test: `citation_url` host/path must match answered `scheme_id`. |

**Grounding order:** Check allowlist URL first, then sentence count, then advisory patterns.
