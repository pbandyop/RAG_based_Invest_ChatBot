from __future__ import annotations

from urllib.parse import urlparse, urlunparse


def normalize_citation_url(url: str) -> str:
    """
    Normalize Groww URLs for allowlist comparison (edge case E3.2).
    https scheme, no fragment/query, host lowercased, path without trailing slash.
    """
    raw = (url or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"https://{raw}"
    p = urlparse(raw)
    netloc = (p.netloc or "").lower()
    path = (p.path or "").rstrip("/")
    return urlunparse(("https", netloc, path, "", "", ""))
