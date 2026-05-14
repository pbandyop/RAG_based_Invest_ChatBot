"""
P1-S5 — low-content / JS-heavy follow-up (architecture §4.1).

- Default: annotate normalized JSON with ``p1_s5`` (flags only; no off-manifest URLs).
- Optional: Playwright headless ``page.goto`` **only** for URLs on the Phase 0 citation allowlist,
  then append rendered body text into ``combined_text_for_chunking``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ingestion.phase1.s5_js_fallback.allowlist import is_allowlisted_groww_url, load_citation_allowlist_urls

S5_VERSION = "p1-s5/1.0.0"


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _needs_low_yield_review(doc: dict[str, Any]) -> bool:
    m = doc.get("metrics") or {}
    return bool(m.get("needs_manual_review"))


def _playwright_fetch_visible_text(url: str, *, timeout_ms: int) -> str | None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    text: str | None = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
                body = page.locator("body")
                if body.count():
                    text = body.inner_text()
                else:
                    text = page.content()
            finally:
                browser.close()
    except Exception:
        return None
    if not text:
        return None
    return " ".join(text.split()).strip() or None


@dataclass
class S5DocResult:
    path: str
    status: str
    detail: str | None = None


def run_s5_on_normalized_dir(
    repo_root: Path,
    normalized_run_dir: Path,
    *,
    use_playwright: bool = False,
    playwright_timeout_ms: int = 60_000,
    force: bool = False,
) -> dict[str, Any]:
    """
    Walk ``*.normalized.json``; update ``p1_s5`` and optionally augment combined text.

    Returns a summary dict suitable for ``s5_report.json``.
    """
    repo_root = Path(repo_root)
    normalized_run_dir = Path(normalized_run_dir)
    allow = load_citation_allowlist_urls(repo_root)

    json_files = sorted(p for p in normalized_run_dir.glob("*.normalized.json") if p.is_file())
    results: list[S5DocResult] = []
    augmented = 0
    flagged = 0
    skipped_ok = 0
    skipped_idempotent = 0
    pw_failed = 0
    errors: list[dict[str, str]] = []

    for path in json_files:
        try:
            with path.open(encoding="utf-8") as f:
                doc = json.load(f)
        except OSError as e:
            errors.append({"path": str(path), "error": repr(e)})
            continue

        existing = doc.get("p1_s5")
        if existing and not force and existing.get("status") == "augmented_playwright":
            skipped_idempotent += 1
            results.append(S5DocResult(str(path), "skipped_idempotent"))
            continue

        cu = str(doc.get("canonical_url") or doc.get("requested_url") or "")
        low = _needs_low_yield_review(doc)

        if not low:
            doc["p1_s5"] = {
                "s5_version": S5_VERSION,
                "status": "skipped_not_low_yield",
                "low_yield": False,
            }
            skipped_ok += 1
            results.append(S5DocResult(str(path), "skipped_not_low_yield"))
            _write_doc(path, doc)
            continue

        if not use_playwright:
            doc["p1_s5"] = {
                "s5_version": S5_VERSION,
                "status": "flagged_manual_review",
                "low_yield": True,
                "canonical_url": cu,
                "detail": "Low text yield after P1-S4; enable --playwright for allowlisted headless augmentation.",
            }
            flagged += 1
            results.append(S5DocResult(str(path), "flagged_manual_review"))
            _write_doc(path, doc)
            continue

        p1_s5: dict[str, Any] = {
            "s5_version": S5_VERSION,
            "low_yield": True,
            "canonical_url": cu,
        }

        if not is_allowlisted_groww_url(cu, allow):
            p1_s5["status"] = "flagged_not_allowlisted_for_playwright"
            p1_s5["detail"] = "URL not on pilot citation allowlist; headless render skipped."
            doc["p1_s5"] = p1_s5
            flagged += 1
            results.append(S5DocResult(str(path), p1_s5["status"], p1_s5["detail"]))
            _write_doc(path, doc)
            continue

        rendered = _playwright_fetch_visible_text(cu, timeout_ms=playwright_timeout_ms)
        if rendered is None:
            p1_s5["status"] = "playwright_import_or_render_failed"
            p1_s5["detail"] = (
                "Install playwright and browsers: pip install playwright && playwright install chromium"
            )
            pw_failed += 1
            flagged += 1
        elif len(rendered) < 80:
            p1_s5["status"] = "playwright_low_text"
            p1_s5["rendered_char_count"] = len(rendered)
            flagged += 1
        else:
            marker = "\n\n--- p1-s5-playwright-body-text ---\n\n"
            combined = str(doc.get("combined_text_for_chunking") or "")
            doc["combined_text_for_chunking"] = (combined + marker + rendered).strip()
            doc["combined_text_sha256"] = _sha256_hex(doc["combined_text_for_chunking"])
            m = dict(doc.get("metrics") or {})
            m["s5_rendered_char_count"] = len(rendered)
            m["s5_combined_char_count"] = len(doc["combined_text_for_chunking"])
            doc["metrics"] = m
            p1_s5["status"] = "augmented_playwright"
            p1_s5["rendered_char_count"] = len(rendered)
            augmented += 1

        doc["p1_s5"] = p1_s5
        results.append(S5DocResult(str(path), str(p1_s5["status"]), p1_s5.get("detail")))
        _write_doc(path, doc)

    return {
        "p1_subphase": "P1-S5",
        "s5_version": S5_VERSION,
        "normalized_run_dir": str(normalized_run_dir.resolve()),
        "use_playwright": use_playwright,
        "counts": {
            "files_seen": len(json_files),
            "skipped_not_low_yield": skipped_ok,
            "skipped_idempotent": skipped_idempotent,
            "flagged_or_review": flagged,
            "augmented_playwright": augmented,
            "playwright_failed_or_tiny": pw_failed,
        },
        "results": [{"path": r.path, "status": r.status, "detail": r.detail} for r in results],
        "errors": errors,
    }


def _write_doc(path: Path, doc: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write("\n")
