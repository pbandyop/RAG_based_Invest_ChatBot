# P1-S5 — JS / low-content fallback (optional)

**Inputs:** P1-S4 `*.normalized.json` under `data/phase1/normalized/{run_id}/`.

**Outputs:**

- Top-level **`p1_s5`** on each document: status, version, and notes.
- **Default (no Playwright):** low-yield pages (`metrics.needs_manual_review` from P1-S4) get `flagged_manual_review` — no off-manifest URLs.
- **Optional `--playwright`:** headless Chromium `page.goto` **only** for URLs listed in `config/phase0/citation_allowlist.json`; rendered body text is appended to `combined_text_for_chunking` under a `--- p1-s5-playwright-body-text ---` marker.

**CLI**

```bash
set PYTHONPATH=src
python scripts/ingestion/phase1/run_s5_low_yield.py --run-id <run_id>
python scripts/ingestion/phase1/run_s5_low_yield.py --run-id <run_id> --playwright
```

**Optional dependency**

```bash
pip install playwright
playwright install chromium
```

See architecture [docs/phase-wise-architecture.md](../../../docs/phase-wise-architecture.md) §4.1 **P1-S5**.
