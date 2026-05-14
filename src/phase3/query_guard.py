"""Shim: query guard lives in ``phase4`` (architecture §7); kept for stable imports."""

from phase4.query_guard import GuardResult, evaluate_query_guard

__all__ = ["GuardResult", "evaluate_query_guard"]
