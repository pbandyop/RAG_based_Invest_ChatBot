# Phase 0 — Logging policy (privacy-safe)

Aligned with architecture: **do not** collect, store, or process PAN, Aadhaar, account numbers, OTPs, email addresses, or phone numbers.

## Defaults (recommended)

| Data | Production | Debug / local |
|------|----------------|---------------|
| Full user query text | **Do not log** by default | Optional short TTL; redact patterns first |
| Query length / hash | Allowed | Allowed |
| `scheme_id` from UI | Allowed | Allowed |
| Retrieval scores, latency | Allowed | Allowed |
| Model provider request IDs | Allowed if no PII in payload | Allowed |

## Redaction (if full queries are ever logged)

Strip or mask patterns consistent with:

- PAN-like sequences
- Long digit runs (Aadhaar/account-like)
- Email and phone regexes (high false-positive risk — prefer **not** logging body)

## Retention

- Define max retention for any log that might contain user text (e.g. 7 days) and document in deployment runbooks (Phase 6).

## Checklist

- [ ] Application code does not persist chat transcripts containing user input to durable stores without this review.
- [ ] Analytics events exclude raw prompt text.
- [ ] Error reports scrub attachments that might contain PII.
