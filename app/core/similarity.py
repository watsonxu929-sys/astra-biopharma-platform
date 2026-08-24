from __future__ import annotations

from rapidfuzz.fuzz import ratio


def similarity_ratio(left: str, right: str) -> float:
    """Return a 0..1 generic string similarity score."""
    return ratio(left or "", right or "") / 100.0
