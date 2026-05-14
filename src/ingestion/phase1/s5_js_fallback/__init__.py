"""P1-S5 — low-content / JS-heavy follow-up (optional Playwright on allowlisted URLs)."""

from ingestion.phase1.s5_js_fallback.allowlist import is_allowlisted_groww_url, load_citation_allowlist_urls
from ingestion.phase1.s5_js_fallback.s5_pass import S5_VERSION, run_s5_on_normalized_dir

SUBPHASE_ID = "P1-S5"

__all__ = [
    "SUBPHASE_ID",
    "S5_VERSION",
    "is_allowlisted_groww_url",
    "load_citation_allowlist_urls",
    "run_s5_on_normalized_dir",
]
