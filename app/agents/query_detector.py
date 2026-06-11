import re
from typing import Literal

EXACT_MATCH_PATTERNS: list[tuple[re.Pattern, float]] = [
    (re.compile(r'"[^"]{2,}"'), 0.85),
    (re.compile(r"'[^']{2,}'"), 0.85),
    (re.compile(r'^[A-Z]{2,}-\d{3,}$'), 0.95),
    (re.compile(r'^\d{6,}$'), 0.90),
    (re.compile(r'^[A-Z_]{3,}[A-Z]$'), 0.80),
]

QueryType = Literal["exact", "semantic"]


def detect_query_type(query: str) -> dict:
    """Detect if a query looks like an exact-match (ID, code, quoted phrase).

    Returns a dict with query_type and confidence (0.0-1.0).
    High-confidence exact matches should bias routing toward keyword_search.
    """
    if not query or not query.strip():
        return {"query_type": "semantic", "confidence": 0.5}

    stripped = query.strip()
    for pattern, confidence in EXACT_MATCH_PATTERNS:
        if pattern.search(stripped):
            return {"query_type": "exact", "confidence": confidence}

    return {"query_type": "semantic", "confidence": 0.5}