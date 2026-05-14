"""P1-S4 — HTML normalization (Groww pilot)."""

from ingestion.phase1.s4_html_normalization.normalize import (
    DEFAULT_REVIEW_CHAR_THRESHOLD,
    DEFAULT_REVIEW_WORD_THRESHOLD,
    NORMALIZER_VERSION,
    NormalizationError,
    NormalizedDocument,
    html_to_plain_text,
    iter_meta_paths,
    normalize_from_meta_path,
    normalize_run,
    write_normalized_document,
)

SUBPHASE_ID = "P1-S4"

__all__ = [
    "DEFAULT_REVIEW_CHAR_THRESHOLD",
    "DEFAULT_REVIEW_WORD_THRESHOLD",
    "NORMALIZER_VERSION",
    "SUBPHASE_ID",
    "NormalizationError",
    "NormalizedDocument",
    "html_to_plain_text",
    "iter_meta_paths",
    "normalize_from_meta_path",
    "normalize_run",
    "write_normalized_document",
]
