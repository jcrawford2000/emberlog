"""
Shared normalization for eval scoring.

This module is the SINGLE SOURCE for all normalization used during scoring.
Both runner.py and scorer.py import from here. Do not duplicate normalization
logic in either module.

Rules:
- channel: case/punct-insensitive, K-Deck/KDEC/K-Dec variants all → "k-deck N"
- units:   order-insensitive, case/whitespace-insensitive comparison
- address: directional words + suffix synonyms, case/punct-insensitive
- incident_type: case/whitespace only — do NOT over-normalize
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

# ---------------------------------------------------------------------------
# Channel
# ---------------------------------------------------------------------------

_KDECK_RE = re.compile(r"k\s*[-]?\s*de(?:ck|c)\s*(\d+)", re.I)
_ACHAN_RE = re.compile(r"\ba\s*(\d{1,2})\b", re.I)


def norm_channel(raw: Optional[str]) -> Optional[str]:
    """
    Normalize a channel value for equality comparison.

    "K-Deck 8", "K-Dec 8", "KDEC8", "K Deck 8" → "k-deck 8"
    "A5", "a 5" → "a5"
    None → None
    """
    if not raw:
        return None
    s = raw.strip()
    m = _KDECK_RE.search(s)
    if m:
        return f"k-deck {int(m.group(1))}"
    m = _ACHAN_RE.search(s)
    if m:
        return f"a{int(m.group(1))}"
    return s.lower()


# ---------------------------------------------------------------------------
# Units
# ---------------------------------------------------------------------------

_UNIT_WS_RE = re.compile(r"\s+")


def norm_unit(u: str) -> str:
    """Normalize a single unit string: lowercase, collapse whitespace."""
    return _UNIT_WS_RE.sub(" ", u.strip().lower())


def norm_units(units: list[str]) -> frozenset[str]:
    """Normalize a list of units to an order-insensitive frozenset for comparison."""
    return frozenset(norm_unit(u) for u in units if u.strip())


# ---------------------------------------------------------------------------
# Address
# ---------------------------------------------------------------------------

_DIRECTIONAL_MAP = {
    "north": "n",
    "south": "s",
    "east": "e",
    "west": "w",
    "northeast": "ne",
    "northwest": "nw",
    "southeast": "se",
    "southwest": "sw",
}

_SUFFIX_MAP = {
    "avenue": "ave",
    "street": "st",
    "road": "rd",
    "drive": "dr",
    "lane": "ln",
    "boulevard": "blvd",
    "place": "pl",
    "court": "ct",
    "terrace": "ter",
    "trail": "trl",
    "parkway": "pkwy",
    "way": "way",
    "mall": "mall",
    "freeway": "fwy",
    "highway": "hwy",
}

_ADDR_PUNCT_RE = re.compile(r"[.,;:#]")
_ADDR_WS_RE = re.compile(r"\s+")


def norm_address(raw: Optional[str]) -> Optional[str]:
    """
    Normalize an address for equality comparison.

    Steps:
    1. Lowercase, strip punctuation
    2. Expand/contract directionals (north → n, etc.)
    3. Normalize street suffixes (avenue → ave, etc.)
    4. Collapse whitespace
    """
    if not raw:
        return None
    s = _ADDR_PUNCT_RE.sub(" ", raw.lower())
    tokens = _ADDR_WS_RE.split(s.strip())
    out = []
    for tok in tokens:
        tok = _DIRECTIONAL_MAP.get(tok, tok)
        tok = _SUFFIX_MAP.get(tok, tok)
        if tok:
            out.append(tok)
    return " ".join(out) if out else None


# ---------------------------------------------------------------------------
# Incident type
# ---------------------------------------------------------------------------

_ITYPE_WS_RE = re.compile(r"\s+")


def norm_incident_type(raw: Optional[str]) -> Optional[str]:
    """
    Light normalization for incident_type: lowercase + whitespace collapse only.
    Do NOT apply synonym maps — incident_type is the fall-through remainder and
    over-normalizing it masks real parser failures.
    """
    if not raw:
        return None
    return _ITYPE_WS_RE.sub(" ", raw.strip().lower())


# ---------------------------------------------------------------------------
# WER helpers
# ---------------------------------------------------------------------------

_TIMESTAMP_ANNOUNCE_RE = re.compile(
    r"\b([01]?\d|2[0-3])[0-5]\d\s+hours,?\s+phoenix\s+fire\s+regional\s+dispatch\.?",
    re.I,
)
_PUNCT_RE = re.compile(r"[^\w\s]")
_WER_WS_RE = re.compile(r"\s+")


def _tokenize(text: str) -> list[str]:
    """Lowercase, strip punctuation, collapse whitespace, split to tokens."""
    s = _TIMESTAMP_ANNOUNCE_RE.sub("", text)
    s = _PUNCT_RE.sub(" ", s)
    s = _WER_WS_RE.sub(" ", s).strip().lower()
    return s.split() if s else []


def wer(reference: str, hypothesis: str) -> float:
    """
    Token-level Word Error Rate: (S + D + I) / len(reference_tokens).

    Returns 0.0 if reference is empty.
    Timestamp announcement tokens are excluded from both sequences before scoring.
    """
    ref = _tokenize(reference)
    hyp = _tokenize(hypothesis)
    if not ref:
        return 0.0

    # Standard edit distance DP
    n, m = len(ref), len(hyp)
    dp = list(range(m + 1))
    for i in range(1, n + 1):
        prev = dp[:]
        dp[0] = i
        for j in range(1, m + 1):
            if ref[i - 1] == hyp[j - 1]:
                dp[j] = prev[j - 1]
            else:
                dp[j] = 1 + min(prev[j], dp[j - 1], prev[j - 1])

    return dp[m] / n
