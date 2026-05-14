# Phase 6 — Edge Cases (Integration, Observability, Documentation)

Parent reference: [phase-wise-architecture.md](../phase-wise-architecture.md) (Section 9).

| # | Edge case | Why it matters | Suggested handling |
|---|-----------|----------------|-------------------|
| E6.1 | **Query API** returns HTTP 200 with empty `answer` but `refusal=false` | Client shows blank “success” | JSON schema validation in API layer; reject invalid payloads; integration tests in CI. |
| E6.2 | **Ingestion manifest** version **≠** index used by API | Stale or missing facts | Stamp `manifest_version` / `index_build_id` in health endpoint; block deploy if mismatch; document upgrade path in README. |
| E6.3 | Logs include **full prompt** with retrieved chunks | May contain noisy personal text from user | Log hashes or truncated prefixes; align with Phase 0 logging policy. |
| E6.4 | **API keys** in client bundle for LLM/embeddings | Secret leak | Proxy through backend; never ship provider keys to browser. |
| E6.5 | **Clock skew** between ingestion workers and API servers | `last_updated` inconsistent | UTC everywhere; display user-local only in UI if desired, with clear semantics. |
| E6.6 | README **omits** Groww-only citation pilot | Wrong reviewer expectations | README must reference **1.1** and link to [phase-wise-architecture.md](../phase-wise-architecture.md). |
| E6.7 | **Rate limiting** missing on `POST /query` | Abuse / cost | Per-IP or per-session limits; captcha only if product allows (watch PII). |
| E6.8 | **Partial deploy** (new API, old index) | Wrong citations or errors | Blue/green or atomic release with version checks; rollback playbook in README. |

**Phase gate:** E2E demo failures should map to a row above before declaring pilot “done.”
