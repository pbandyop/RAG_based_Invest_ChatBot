"""
P1-S4 — HTML normalization.

Reads P1-S3 `fetch_*.meta.json` + body files under data/phase1/raw/{run_id}/,
produces structured JSON documents for Phase 2 chunking (plain text + metrics).
"""

from __future__ import annotations

import hashlib
import html as html_module
import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


NORMALIZER_VERSION = "p1-s4/1.0.0"

# Heuristic: Groww CSR pages often yield little visible text until richer extraction (P1-S5).
DEFAULT_REVIEW_CHAR_THRESHOLD = 500
DEFAULT_REVIEW_WORD_THRESHOLD = 80


class NormalizationError(ValueError):
    """Invalid inputs or refuse to overwrite output."""


def _collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _extract_title_regex(html: str) -> str | None:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    raw = m.group(1)
    return _collapse_ws(html_module.unescape(re.sub(r"<[^>]+>", " ", raw)))


def _extract_script_json_blocks(html: str, max_each: int = 120_000) -> list[str]:
    """
    Pull inline JSON payloads (common on Next.js / MF sites) for supplemental text.
    Truncates each block to max_each chars to bound memory.
    """
    blocks: list[str] = []
    patterns = [
        r'<script[^>]*type=["\']application/json["\'][^>]*>(.*?)</script>',
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
    ]
    for pat in patterns:
        for m in re.finditer(pat, html, flags=re.IGNORECASE | re.DOTALL):
            inner = m.group(1).strip()
            if not inner:
                continue
            if len(inner) > max_each:
                inner = inner[:max_each] + "\n…[truncated-json-block]"
            blocks.append(inner)
    return blocks


class _VisibleTextParser(HTMLParser):
    """Collect visible text; skip script/style/noscript/template; light heading capture."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._chunks: list[str] = []
        self._in_heading: str | None = None
        self._heading_buf: list[str] = []
        self.headings: list[dict[str, Any]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        if t in ("script", "style", "noscript", "template"):
            self._skip_depth += 1
            return
        if self._skip_depth > 0:
            return
        if t in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._in_heading = t
            self._heading_buf = []

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in ("script", "style", "noscript", "template"):
            if self._skip_depth > 0:
                self._skip_depth -= 1
            return
        if self._skip_depth > 0:
            return
        if self._in_heading and t == self._in_heading:
            text = _collapse_ws("".join(self._heading_buf))
            if text:
                self.headings.append({"level": int(t[1]), "text": text})
            self._in_heading = None
            self._heading_buf = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        chunk = data
        if not chunk or not chunk.strip():
            return
        if self._in_heading:
            self._heading_buf.append(chunk)
            return
        self._chunks.append(chunk)

    def text(self) -> str:
        raw = " ".join(self._chunks)
        raw = html_module.unescape(raw)
        return _collapse_ws(raw)


def html_to_plain_text(html: str) -> tuple[str, list[dict[str, Any]]]:
    parser = _VisibleTextParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # noqa: BLE001 — malformed HTML
        # Regex fallback: strip tags coarsely
        no_scripts = re.sub(
            r"<(?i)(script|style|noscript|template)[^>]*>.*?</\1>",
            " ",
            html,
            flags=re.DOTALL,
        )
        no_tags = re.sub(r"<[^>]+>", " ", no_scripts)
        return _collapse_ws(html_module.unescape(no_tags)), []
    return parser.text(), parser.headings


def _word_count(s: str) -> int:
    return len(re.findall(r"\b\w+\b", s))


def _combined_document_text(
    *,
    title: str | None,
    headings: list[dict[str, Any]],
    plain: str,
    supplement: str,
) -> str:
    parts: list[str] = []
    if title:
        parts.append(f"# {title}")
    for h in headings:
        lvl = min(int(h.get("level", 2)), 6)
        parts.append(f"{'#' * lvl} {h.get('text', '')}")
    if plain:
        parts.append(plain)
    if supplement:
        parts.append("\n--- json-payloads ---\n" + supplement)
    return "\n\n".join(p for p in parts if p).strip()


@dataclass
class NormalizedDocument:
    """Structured output written as JSON for Phase 2."""

    p1_subphase: str = "P1-S4"
    normalizer_version: str = NORMALIZER_VERSION
    run_id: str = ""
    base: str = ""
    canonical_url: str = ""
    requested_url: str = ""
    document_type: str | None = None
    scheme_id: str | None = None
    scheme_display_name: str | None = None
    citable: bool | None = None
    fetched_at_utc: str | None = None
    last_modified: str | None = None
    etag: str | None = None
    content_sha256: str | None = None
    truncated: bool | None = None
    title: str | None = None
    headings: list[dict[str, Any]] = field(default_factory=list)
    plain_text: str = ""
    supplement_text: str = ""
    combined_text_for_chunking: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)
    source_meta_path: str = ""
    source_body_path: str = ""

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "p1_subphase": self.p1_subphase,
            "normalizer_version": self.normalizer_version,
            "run_id": self.run_id,
            "base": self.base,
            "canonical_url": self.canonical_url,
            "requested_url": self.requested_url,
            "document_type": self.document_type,
            "scheme_id": self.scheme_id,
            "scheme_display_name": self.scheme_display_name,
            "citable": self.citable,
            "fetched_at_utc": self.fetched_at_utc,
            "last_modified": self.last_modified,
            "etag": self.etag,
            "content_sha256": self.content_sha256,
            "truncated": self.truncated,
            "title": self.title,
            "headings": self.headings,
            "plain_text": self.plain_text,
            "supplement_text": self.supplement_text,
            "combined_text_for_chunking": self.combined_text_for_chunking,
            "metrics": self.metrics,
            "source_meta_path": self.source_meta_path,
            "source_body_path": self.source_body_path,
        }


def normalize_from_meta_path(
    meta_path: Path,
    *,
    review_char_threshold: int = DEFAULT_REVIEW_CHAR_THRESHOLD,
    review_word_threshold: int = DEFAULT_REVIEW_WORD_THRESHOLD,
) -> NormalizedDocument:
    """Load one P1-S3 sidecar + body; return NormalizedDocument (does not write)."""
    if not meta_path.is_file():
        raise NormalizationError(f"meta not found: {meta_path}")
    with meta_path.open(encoding="utf-8") as f:
        meta: dict[str, Any] = json.load(f)

    if not meta.get("ok"):
        raise NormalizationError(f"skip failed fetch meta: {meta_path}")
    body_file = meta.get("body_file")
    if not body_file:
        raise NormalizationError(f"no body_file in meta: {meta_path}")

    run_dir = meta_path.parent
    body_path = run_dir / str(body_file)
    if not body_path.is_file():
        raise NormalizationError(f"body not found: {body_path}")

    html = body_path.read_text(encoding="utf-8", errors="replace")
    title = _extract_title_regex(html)
    plain, headings = html_to_plain_text(html)
    json_blocks = _extract_script_json_blocks(html)
    supplement = "\n\n".join(json_blocks) if json_blocks else ""

    combined = _combined_document_text(
        title=title,
        headings=headings,
        plain=plain,
        supplement=supplement,
    )

    plain_chars = len(plain)
    combined_chars = len(combined)
    wc_plain = _word_count(plain)
    wc_combined = _word_count(combined)
    needs_review = (
        combined_chars < review_char_threshold and wc_combined < review_word_threshold
    )

    base = meta_path.name[: -len(".meta.json")]

    doc = NormalizedDocument(
        run_id=str(meta.get("run_id", "")),
        base=base,
        canonical_url=str(meta.get("canonical_url", "")),
        requested_url=str(meta.get("requested_url", "")),
        document_type=meta.get("document_type"),
        scheme_id=meta.get("scheme_id"),
        scheme_display_name=meta.get("scheme_display_name"),
        citable=meta.get("citable"),
        fetched_at_utc=meta.get("fetched_at_utc"),
        last_modified=meta.get("last_modified"),
        etag=meta.get("etag"),
        content_sha256=meta.get("content_sha256"),
        truncated=meta.get("truncated"),
        title=title,
        headings=headings,
        plain_text=plain,
        supplement_text=supplement,
        combined_text_for_chunking=combined,
        metrics={
            "plain_char_count": plain_chars,
            "combined_char_count": combined_chars,
            "plain_word_count": wc_plain,
            "combined_word_count": wc_combined,
            "script_json_block_count": len(json_blocks),
            "needs_manual_review": needs_review,
            "review_char_threshold": review_char_threshold,
            "review_word_threshold": review_word_threshold,
        },
        source_meta_path=str(meta_path.resolve()),
        source_body_path=str(body_path.resolve()),
    )
    return doc


def write_normalized_document(
    doc: NormalizedDocument,
    out_dir: Path,
    *,
    overwrite: bool = False,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{doc.base}.normalized.json"
    if out_path.exists() and not overwrite:
        raise NormalizationError(f"refusing to overwrite: {out_path}")
    payload = doc.to_json_dict()
    payload["combined_text_sha256"] = hashlib.sha256(
        doc.combined_text_for_chunking.encode("utf-8", errors="replace"),
    ).hexdigest()
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return out_path


def iter_meta_paths(run_dir: Path) -> list[Path]:
    """Sorted fetch meta paths for one run_id directory."""
    if not run_dir.is_dir():
        raise NormalizationError(f"run dir not found: {run_dir}")
    metas = sorted(run_dir.glob("fetch_*.meta.json"))
    return metas


def normalize_run(
    run_dir: Path,
    out_dir: Path,
    *,
    overwrite: bool = False,
    review_char_threshold: int = DEFAULT_REVIEW_CHAR_THRESHOLD,
    review_word_threshold: int = DEFAULT_REVIEW_WORD_THRESHOLD,
) -> dict[str, Any]:
    """
    Normalize all successful body artifacts in run_dir; write to out_dir.
    Returns summary dict.
    """
    written: list[str] = []
    skipped: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []

    for meta_path in iter_meta_paths(run_dir):
        try:
            doc = normalize_from_meta_path(
                meta_path,
                review_char_threshold=review_char_threshold,
                review_word_threshold=review_word_threshold,
            )
            out_path = write_normalized_document(doc, out_dir, overwrite=overwrite)
            written.append(str(out_path))
        except NormalizationError as e:
            skipped.append({"path": str(meta_path), "reason": str(e)})
        except Exception as e:  # noqa: BLE001
            errors.append({"path": str(meta_path), "error": repr(e)})

    return {
        "p1_subphase": "P1-S4",
        "normalizer_version": NORMALIZER_VERSION,
        "run_dir": str(run_dir.resolve()),
        "out_dir": str(out_dir.resolve()),
        "written_count": len(written),
        "skipped": skipped,
        "errors": errors,
        "written": written,
    }
