"""
P1-S2 — HTTP fetch layer.

GET with timeouts, retries/backoff, stable User-Agent, selected response headers,
optional robots.txt check, final-URL host guard (groww.in), max body size.
"""

from __future__ import annotations

import hashlib
import ssl
import time
import urllib.error
import urllib.request
import urllib.robotparser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.message import Message
from typing import Any, Mapping
from urllib.parse import urlparse

from ingestion.phase1.s1_manifest_binding.manifest_binding import ALLOWED_HOST, canonical_url

DEFAULT_USER_AGENT = (
    "NextLeap-Groww-FAQ-Ingestion/1.0 "
    "(educational corpus; +https://groww.in; respects robots.txt)"
)

# Architecture / edge cases: transient HTTP + network retries
RETRYABLE_STATUS = {429, 502, 503, 504}
DEFAULT_MAX_RETRIES = 4
DEFAULT_TIMEOUT_SEC = 45.0
DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10 MiB per E1.6


def unverified_ssl_context() -> ssl.SSLContext:
    """Use only when the host TLS chain fails on a dev machine (e.g. corporate MITM). Not for production."""
    return ssl._create_unverified_context()


class FetchError(Exception):
    """Unrecoverable fetch failure (after retries or policy violation)."""


@dataclass
class FetchResult:
    """Outcome of a single fetch attempt (after retry loop)."""

    ok: bool
    requested_url: str
    canonical_url: str
    final_url: str
    status_code: int | None
    body: bytes | None
    headers_lower: dict[str, str]
    last_modified: str | None
    etag: str | None
    content_type: str | None
    fetched_at_utc: str
    truncated: bool
    attempts: int
    error: str | None = None
    robots_allowed: bool | None = None
    robots_note: str | None = None
    fetcher_version: str = field(default="p1-s2/1.0.0")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _final_host_ok(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host == ALLOWED_HOST


def _read_body_limited(resp: Any, max_bytes: int) -> tuple[bytes, bool]:
    """Read up to max_bytes; return (data, truncated)."""
    chunks: list[bytes] = []
    total = 0
    chunk_size = 64 * 1024
    truncated = False
    while True:
        chunk = resp.read(chunk_size)
        if not chunk:
            break
        if total + len(chunk) > max_bytes:
            allow = max_bytes - total
            if allow > 0:
                chunks.append(chunk[:allow])
                total += allow
            truncated = True
            break
        chunks.append(chunk)
        total += len(chunk)
    return b"".join(chunks), truncated


def _normalize_headers(msg: Message | Mapping[str, str]) -> dict[str, str]:
    if isinstance(msg, Message):
        return {k.lower(): v for k, v in msg.items()}
    return {str(k).lower(): str(v) for k, v in msg.items()}


def _pick_header(headers: dict[str, str], name: str) -> str | None:
    v = headers.get(name.lower())
    return v.strip() if v else None


def _retry_after_seconds(headers: dict[str, str]) -> float | None:
    raw = _pick_header(headers, "retry-after")
    if not raw:
        return None
    if raw.isdigit():
        return float(raw)
    return None


def _sleep_backoff(attempt: int, base: float = 0.75, cap: float = 20.0) -> None:
    # attempt is 0-based index of retry (after a failure)
    delay = min(cap, base * (2**attempt))
    time.sleep(delay)


class RobotsPolicy:
    """Lightweight robots.txt gate for groww.in."""

    def __init__(self, user_agent: str) -> None:
        self.user_agent = user_agent
        self._parser: urllib.robotparser.RobotFileParser | None = None
        self.note: str = ""

    def load(self, timeout: float = 15.0, *, ssl_context: ssl.SSLContext | None = None) -> None:
        robots_url = f"https://{ALLOWED_HOST}/robots.txt"
        try:
            req = urllib.request.Request(
                robots_url,
                headers={"User-Agent": self.user_agent},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=timeout, context=ssl_context) as resp:
                raw = resp.read(2**20)  # 1 MiB cap for robots file
            text = raw.decode("utf-8", errors="replace")
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(robots_url)
            rp.parse(text.splitlines())
            self._parser = rp
            self.note = "robots.txt loaded"
        except Exception as exc:  # noqa: BLE001 — best-effort; report in note
            self._parser = None
            self.note = f"robots unavailable ({exc!r}); not blocking fetch (review for production)"

    def can_fetch(self, url: str) -> bool:
        if self._parser is None:
            return True
        return self._parser.can_fetch(self.user_agent, url)


def fetch_url(
    url: str,
    *,
    user_agent: str = DEFAULT_USER_AGENT,
    timeout: float = DEFAULT_TIMEOUT_SEC,
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_retries: int = DEFAULT_MAX_RETRIES,
    robots: RobotsPolicy | None = None,
    ssl_context: ssl.SSLContext | None = None,
) -> FetchResult:
    """
    Fetch a single URL with retries. Validates final URL host == groww.in.
    """
    requested = url.strip()
    canon = canonical_url(requested)
    fetched_at = _utc_now_iso()
    robots_allowed: bool | None = None
    robots_note: str | None = None

    if robots is not None:
        robots_allowed = robots.can_fetch(requested)
        robots_note = robots.note
        if not robots_allowed:
            return FetchResult(
                ok=False,
                requested_url=requested,
                canonical_url=canon,
                final_url="",
                status_code=None,
                body=None,
                headers_lower={},
                last_modified=None,
                etag=None,
                content_type=None,
                fetched_at_utc=fetched_at,
                truncated=False,
                attempts=0,
                error="disallowed by robots.txt",
                robots_allowed=False,
                robots_note=robots_note,
            )

    last_error: str | None = None
    attempts = 0

    for attempt in range(max_retries):
        attempts = attempt + 1
        try:
            req = urllib.request.Request(
                requested,
                headers={"User-Agent": user_agent, "Accept": "*/*"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=timeout, context=ssl_context) as resp:
                final_url = resp.geturl()
                if not _final_host_ok(final_url):
                    return FetchResult(
                        ok=False,
                        requested_url=requested,
                        canonical_url=canon,
                        final_url=final_url,
                        status_code=getattr(resp, "status", None) or resp.getcode(),
                        body=None,
                        headers_lower=_normalize_headers(resp.headers),
                        last_modified=None,
                        etag=None,
                        content_type=None,
                        fetched_at_utc=fetched_at,
                        truncated=False,
                        attempts=attempts,
                        error=f"final URL host must be {ALLOWED_HOST!r} after redirects",
                        robots_allowed=True if robots is not None else None,
                        robots_note=robots_note,
                    )
                status = getattr(resp, "status", None)
                if status is None:
                    status = resp.getcode()
                headers = _normalize_headers(resp.headers)
                body, truncated = _read_body_limited(resp, max_bytes)

            if status in RETRYABLE_STATUS and attempt < max_retries - 1:
                ra = _retry_after_seconds(headers)
                if ra is not None:
                    time.sleep(min(ra, 60.0))
                else:
                    _sleep_backoff(attempt)
                last_error = f"HTTP {status} (retrying)"
                continue

            if status is not None and status >= 400:
                return FetchResult(
                    ok=False,
                    requested_url=requested,
                    canonical_url=canon,
                    final_url=final_url,
                    status_code=status,
                    body=body if status < 500 else None,
                    headers_lower=headers,
                    last_modified=_pick_header(headers, "last-modified"),
                    etag=_pick_header(headers, "etag"),
                    content_type=_pick_header(headers, "content-type"),
                    fetched_at_utc=fetched_at,
                    truncated=truncated,
                    attempts=attempts,
                    error=f"HTTP {status}",
                    robots_allowed=True if robots is not None else None,
                    robots_note=robots_note,
                )

            return FetchResult(
                ok=True,
                requested_url=requested,
                canonical_url=canon,
                final_url=final_url,
                status_code=status,
                body=body,
                headers_lower=headers,
                last_modified=_pick_header(headers, "last-modified"),
                etag=_pick_header(headers, "etag"),
                content_type=_pick_header(headers, "content-type"),
                fetched_at_utc=fetched_at,
                truncated=truncated,
                attempts=attempts,
                error=None,
                robots_allowed=True if robots is not None else None,
                robots_note=robots_note,
            )

        except urllib.error.HTTPError as e:
            status = e.code
            headers = _normalize_headers(e.headers or {})
            body = b""
            try:
                body, truncated = _read_body_limited(e, max_bytes)
            except Exception:  # noqa: BLE001
                truncated = False
            if status in RETRYABLE_STATUS and attempt < max_retries - 1:
                ra = _retry_after_seconds(headers)
                if ra is not None:
                    time.sleep(min(ra, 60.0))
                else:
                    _sleep_backoff(attempt)
                last_error = f"HTTPError {status}"
                continue
            return FetchResult(
                ok=False,
                requested_url=requested,
                canonical_url=canon,
                final_url=requested,
                status_code=status,
                body=body or None,
                headers_lower=headers,
                last_modified=_pick_header(headers, "last-modified"),
                etag=_pick_header(headers, "etag"),
                content_type=_pick_header(headers, "content-type"),
                fetched_at_utc=fetched_at,
                truncated=truncated,
                attempts=attempts,
                error=f"HTTPError {status}: {e.reason!r}",
                robots_allowed=True if robots is not None else None,
                robots_note=robots_note,
            )
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_error = repr(e)
            if attempt < max_retries - 1:
                _sleep_backoff(attempt)
                continue
            return FetchResult(
                ok=False,
                requested_url=requested,
                canonical_url=canon,
                final_url="",
                status_code=None,
                body=None,
                headers_lower={},
                last_modified=None,
                etag=None,
                content_type=None,
                fetched_at_utc=fetched_at,
                truncated=False,
                attempts=attempts,
                error=last_error,
                robots_allowed=True if robots is not None else None,
                robots_note=robots_note,
            )

    return FetchResult(
        ok=False,
        requested_url=requested,
        canonical_url=canon,
        final_url="",
        status_code=None,
        body=None,
        headers_lower={},
        last_modified=None,
        etag=None,
        content_type=None,
        fetched_at_utc=fetched_at,
        truncated=False,
        attempts=attempts,
        error=last_error or "exhausted retries",
        robots_allowed=True if robots is not None else None,
        robots_note=robots_note,
    )


def body_extension(content_type: str | None) -> str:
    if not content_type:
        return "bin"
    ct = content_type.split(";")[0].strip().lower()
    if ct in ("text/html", "application/xhtml+xml"):
        return "html"
    if ct == "application/json":
        return "json"
    if ct in ("text/plain", "text/css"):
        return "txt"
    return "bin"


def content_sha256(body: bytes | None) -> str | None:
    if body is None:
        return None
    return hashlib.sha256(body).hexdigest()
