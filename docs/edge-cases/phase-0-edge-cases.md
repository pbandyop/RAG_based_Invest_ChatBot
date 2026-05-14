# Phase 0 — Edge Cases (Foundation, Compliance, Scope Lock)

Parent reference: [phase-wise-architecture.md](../phase-wise-architecture.md) (Section 3, pilot policy **1.1**).

| # | Edge case | Why it matters | Suggested handling |
|---|-----------|----------------|-------------------|
| E0.1 | Stakeholder adds **non-`groww.in`** URLs to the manifest “for better accuracy” | Violates pilot citation policy if those pages become retrievable and the model cites them | Keep manifest columns `allowed_use` / `citable`; only the five scheme rows may set `citable=true` for factual answers unless Phase 0 explicitly extends **1.1**. |
| E0.2 | Same scheme appears under **two different Groww paths** (slug change, redirect) | Duplicate corpus, ambiguous `scheme_id` | Pick one canonical URL per scheme (the table in **3.1.1**); treat alternates as redirects to canonical in the manifest. |
| E0.3 | **“Last updated”** semantics when the page has no clear date but fetch time exists | User-facing footer may confuse “source date” vs “crawl time” | Document in Phase 0: prefer explicit on-page date if extracted reliably; else `fetched_at` from ingestion; never invent a regulatory “as of” date. |
| E0.4 | Query taxonomy: borderline prompts (e.g. “**Is** exit load applied on every withdrawal?”) | Teams disagree whether “is” questions are advice | Classify by **intent**: factual mechanism → in-scope; personalized suitability → out-of-scope. Record examples in the taxonomy doc. |
| E0.5 | Refusal copy references a **third-party** explainer | Conflicts with “no blogs” content posture | Refusals: **AMFI/SEBI only** (per architecture) unless product legal approves another domain. |
| E0.6 | Logging policy silent on **query body in traces** | Risk of accidental PAN/Aadhaar if user pastes them | Phase 0 deliverable: default **no full query logging** in prod; if enabled for debug, run redaction patterns and short TTL. |
| E0.7 | Manifest grows past **25 URLs** of only `groww.in` | Crawl cost and noise | Cap optional non-scheme pages; require `priority` and periodic review so Phase 1 gate stays meaningful. |

**Open decisions to log:** Any exception to Groww-only citations; which educational URLs are approved for refusals.
