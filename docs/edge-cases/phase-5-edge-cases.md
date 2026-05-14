# Phase 5 — Edge Cases (Minimal User Interface)

Parent reference: [phase-wise-architecture.md](../phase-wise-architecture.md) (Section 8).

| # | Edge case | Why it matters | Suggested handling |
|---|-----------|----------------|-------------------|
| E5.1 | User pastes **PAN / Aadhaar / account number** into the chat box | PII policy violation if forwarded to logs or model vendor | Client-side max length + pattern warning; server rejects/redacts before persistence; never echo PII in UI. |
| E5.2 | **Disclaimer** below fold on mobile | Compliance perception | Sticky compact disclaimer bar or modal on first send; example questions remain visible without scrolling where possible. |
| E5.3 | Example question is **out of scope** for pilot (e.g. compares two funds) | Trains wrong behavior | Curate three examples strictly in-scope and single-scheme; align with Phase 0 taxonomy. |
| E5.4 | **No scheme selected** and question uses “this fund” | Wrong retrieval (E3.5) | Default: force scheme pick before first query, or show disambiguation when confidence low (coordinate with Phase 3/4). |
| E5.5 | **Very long** pasted text (DOS / token burn) | Cost and latency | Hard cap on input characters; show friendly error. |
| E5.6 | **Markdown/HTML** in user input breaks rendering | XSS if rendered unsafely | Escape or sanitize; render assistant output as plain text or trusted pipeline only. |
| E5.7 | **Citation link** not obviously clickable (accessibility) | Users miss source | Use semantic link text (“View scheme on Groww”) plus URL; meet contrast and focus ring guidelines. |
| E5.8 | User opens app **offline** | Errors confuse users | Detect network failure; show retry, not raw stack traces. |

**PII:** No login, no email/phone fields (architecture); same bar applies to optional “feedback” widgets.
