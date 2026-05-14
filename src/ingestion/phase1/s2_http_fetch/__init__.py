"""P1-S2 — HTTP fetch layer."""

from ingestion.phase1.s2_http_fetch.fetcher import (
    DEFAULT_USER_AGENT,
    DEFAULT_MAX_BYTES,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT_SEC,
    FetchResult,
    RETRYABLE_STATUS,
    RobotsPolicy,
    body_extension,
    content_sha256,
    fetch_url,
    unverified_ssl_context,
)

SUBPHASE_ID = "P1-S2"

__all__ = [
    "DEFAULT_USER_AGENT",
    "DEFAULT_MAX_BYTES",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_TIMEOUT_SEC",
    "FetchResult",
    "RETRYABLE_STATUS",
    "RobotsPolicy",
    "SUBPHASE_ID",
    "body_extension",
    "content_sha256",
    "fetch_url",
    "unverified_ssl_context",
]
