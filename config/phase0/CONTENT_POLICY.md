# Phase 0 — Content policy checklist

Derived from [phase-wise-architecture.md](../../docs/phase-wise-architecture.md) and the problem statement.

Use this as a **sign-off checklist** before Phase 1 ingestion at scale (Phase 0 gate).

## Pilot citation surface (1.1)

- [ ] Factual answers use **exactly one** citation URL from [citation_allowlist.json](citation_allowlist.json) (the five Groww scheme pages).
- [ ] No AMC, AMFI, or SEBI URL is used as **`citation_url`** for a successful factual answer in this pilot.
- [ ] Refusal / education-only responses may use AMFI/SEBI links from [refusal_and_education.json](refusal_and_education.json) only as **non-fund-fact** pointers.

## Corpus sources

- [ ] No third-party blogs or random aggregators in `manifest.json`.
- [ ] Additional corpus rows (if any) are **`https://groww.in/...` only**, with `citable: false` unless Phase 0 is formally extended.
- [ ] No performance **comparisons** or **rankings** in assistant-generated prose.
- [ ] No personalized investment **recommendations** or “you should” language in templates (refusal templates are defensive only).

## Facts vs advice

- [ ] [query_taxonomy.json](query_taxonomy.json) reviewed: in-scope intents are objective; out-of-scope routes map to refusal templates.

## Sign-off

| Role | Name | Date | Notes |
|------|------|------|-------|
| Owner | | | |
| Reviewer | | | |
