"""
Validate Phase 0 configuration: manifest, citation allowlist, schemes, taxonomy, refusal templates.
Usage: python scripts/validate_phase0.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
PHASE0 = REPO_ROOT / "config" / "phase0"


def _load(name: str) -> Any:
    path = PHASE0 / name
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _fail(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    manifest = _load("manifest.json")
    allow = _load("citation_allowlist.json")
    schemes = _load("schemes.json")
    taxonomy = _load("query_taxonomy.json")
    refusal = _load("refusal_and_education.json")

    if not isinstance(manifest, dict) or "urls" not in manifest:
        _fail("manifest.json must be an object with 'urls' array")
    urls = manifest["urls"]
    if not isinstance(urls, list) or not urls:
        _fail("manifest.urls must be a non-empty list")

    allowed_uses = {"ingest", "retrieve", "cite"}
    citable_urls: list[str] = []
    scheme_ids_manifest: set[str] = set()

    for i, row in enumerate(urls):
        if not isinstance(row, dict):
            _fail(f"manifest.urls[{i}] must be an object")
        for key in ("url", "document_type", "priority", "allowed_use", "citable", "included_in_crawl"):
            if key not in row:
                _fail(f"manifest.urls[{i}] missing required key '{key}'")
        u = row["url"]
        if not isinstance(u, str) or not u.startswith("https://"):
            _fail(f"manifest.urls[{i}].url must be https string")
        if not u.startswith("https://groww.in"):
            _fail(f"manifest.urls[{i}].url must be under https://groww.in (pilot corpus)")
        au = row["allowed_use"]
        if not isinstance(au, list) or not au:
            _fail(f"manifest.urls[{i}].allowed_use must be a non-empty list")
        if not set(au).issubset(allowed_uses):
            _fail(f"manifest.urls[{i}].allowed_use contains unknown value")
        if row["citable"] is True:
            citable_urls.append(u)
            if "cite" not in au:
                _fail(f"manifest.urls[{i}] citable=true requires 'cite' in allowed_use")
        sid = row.get("scheme_id")
        if sid is not None:
            if not isinstance(sid, str):
                _fail(f"manifest.urls[{i}].scheme_id must be string or null")
            scheme_ids_manifest.add(sid)

    if not isinstance(allow, dict) or "urls" not in allow:
        _fail("citation_allowlist.json must have 'urls' array")
    allow_urls = allow["urls"]
    if not isinstance(allow_urls, list) or len(allow_urls) != 5:
        _fail("citation_allowlist.urls must contain exactly five pilot scheme URLs")

    if set(allow_urls) != set(citable_urls):
        _fail("citation_allowlist.urls must match manifest rows where citable=true (set equality)")

    for u in allow_urls:
        if not u.startswith("https://groww.in/"):
            _fail(f"Allowlisted citation must be groww.in: {u}")

    if not isinstance(schemes, dict) or "schemes" not in schemes:
        _fail("schemes.json must have 'schemes' array")
    slist = schemes["schemes"]
    if len(slist) != 5:
        _fail("schemes.schemes must have length 5")
    citation_from_schemes = []
    scheme_ids_json = set()
    for s in slist:
        sid = s.get("scheme_id")
        cu = s.get("citation_url")
        if not isinstance(sid, str) or not isinstance(cu, str):
            _fail("Each scheme needs string scheme_id and citation_url")
        scheme_ids_json.add(sid)
        citation_from_schemes.append(cu)
    if set(citation_from_schemes) != set(allow_urls):
        _fail("schemes[].citation_url set must equal citation_allowlist.urls")

    if scheme_ids_json != scheme_ids_manifest - {None}:
        _fail("scheme_id sets between manifest (citable rows) and schemes.json must match")

    if "in_scope_intents" not in taxonomy or "out_of_scope_intents" not in taxonomy:
        _fail("query_taxonomy.json missing intent arrays")

    edu = refusal.get("educational_links") or {}
    templates = refusal.get("templates") or {}
    if not templates:
        _fail("refusal_and_education.json must define templates")
    for name, tpl in templates.items():
        if not isinstance(tpl, dict):
            _fail(f"template {name} must be object")
        key = tpl.get("educational_link_key")
        if key not in edu:
            _fail(f"template {name} educational_link_key {key!r} missing in educational_links")

    print("Phase 0 validation OK:")
    print(f"  - manifest rows: {len(urls)}")
    print(f"  - citable URLs: {len(citable_urls)}")
    print(f"  - refusal templates: {len(templates)}")


if __name__ == "__main__":
    main()
