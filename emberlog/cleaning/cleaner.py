from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from emberlog.models import Transcript  # your existing model

# ------------------- Normalization rules -------------------

REPLACEMENTS = [
    # Italian → Battalion
    (re.compile(r"\bItalian\s+(\d{1,3})\b", re.I), r"Battalion \1"),
    (re.compile(r"\bBattalion\s+Chief\s+(\d{1,3})\b", re.I), r"Battalion \1"),
    # K deck variants → K-Deck N
    (re.compile(r"\bK\s*[-]?\s*dec?k\s*(\d{1,2})\b", re.I), r"K-Deck \1"),
    # Lifepak spelling
    (re.compile(r"\bLife\s*Pack\b", re.I), "Lifepak"),
    # Crisis Response shorthand
    (re.compile(r"\bC R\s*?(\d+)\b", re.I), r"Crisis Response \1"),
]

UNIT_PATTERNS = [
    re.compile(r"\b(Batt(?:alion)?\s*\d{1,3})\b", re.I),
    re.compile(r"\b(Engine\s*\d{1,3})\b", re.I),
    re.compile(
        r"\b(Ladder\s+Tender\s*\d{1,3}|Ladder\s*\d{1,3}|Truck\s*\d{1,3}|TR\s*\d{1,3})\b",
        re.I,
    ),
    re.compile(r"\b(Rescue\s*\d{1,3}|Medic\s*\d{1,3})\b", re.I),
    re.compile(r"\b(Crisis\s+Response\s*\d{1,3})\b", re.I),
]

CHAN_RE = re.compile(r"\bK[-\s]?D(?:ec|eck)\s*(\d{1,2})\b", re.I)

# ------------------- Address extraction -------------------
# Compass normalization
COMPASS_WORDS = {
    "north": "N",
    "south": "S",
    "east": "E",
    "west": "W",
    "n": "N",
    "s": "S",
    "e": "E",
    "w": "W",
}
# Common street type abbreviations (extend as needed)
ST_TYPE_MAP = {
    "avenue": "Ave",
    "ave": "Ave",
    "street": "St",
    "st": "St",
    "road": "Rd",
    "rd": "Rd",
    "drive": "Dr",
    "dr": "Dr",
    "lane": "Ln",
    "ln": "Ln",
    "way": "Way",
    "boulevard": "Blvd",
    "blvd": "Blvd",
    "place": "Pl",
    "pl": "Pl",
    "court": "Ct",
    "ct": "Ct",
    "terrace": "Ter",
    "ter": "Ter",
    "trail": "Trl",
    "trl": "Trl",
    "parkway": "Pkwy",
    "pkwy": "Pkwy",
}

# A light-touch Phoenix-friendly pattern:
# <block 3-5 digits> <compass word/letter> <one+ street-name tokens> [optional street type]
ADDR_RE = re.compile(
    r"\b(?P<num>\d{3,5})\s+(?P<compass>[NnSsEeWw]|North|South|East|West)\s+"
    r"(?P<name>(?:[A-Z][A-Za-z0-9\-']*(?:\s+[A-Z][A-Za-z0-9\-']*)*))"
    r"(?:\s+(?P<type>Avenue|Ave|Street|St|Road|Rd|Drive|Dr|Lane|Ln|Way|Boulevard|Blvd|Place|Pl|Court|Ct|Terrace|Ter|Trail|Trl|Parkway|Pkwy))?\b",
    re.I,
)


def _normalize_address(text: str) -> Optional[str]:
    m = ADDR_RE.search(text)
    if not m:
        return None
    num = m.group("num")
    comp = COMPASS_WORDS.get(m.group("compass").lower(), m.group("compass").upper())
    name = " ".join(part.capitalize() for part in m.group("name").split())
    stype = m.group("type")
    if stype:
        stype = ST_TYPE_MAP.get(stype.lower(), stype.title())
        return f"{num} {comp} {name} {stype}"
    return f"{num} {comp} {name}"


# ------------------- Result containers -------------------


@dataclass
class CleanStats:
    replacements_applied: int = 0
    units_before: int = 0
    units_after: int = 0
    deduped_units: int = 0
    channel_found: bool = False
    address_found: bool = False
    chars_before: int = 0
    chars_after: int = 0


@dataclass
class CleanResult:
    text: str
    units: List[str]
    channel: Optional[str]
    address: Optional[str]
    stats: CleanStats


# ------------------- Cleaner -------------------


def clean_transcript(t: Transcript) -> CleanResult:
    raw = t.text or ""
    stats = CleanStats(chars_before=len(raw))

    # Apply regex replacements
    fixed = raw
    for pat, repl in REPLACEMENTS:
        fixed, n = pat.subn(repl, fixed)
        stats.replacements_applied += n

    # Collapse whitespace
    fixed = re.sub(r"\s+", " ", fixed).strip()

    # Extract units
    units_found = []
    seen = set()
    for pat in UNIT_PATTERNS:
        for m in pat.finditer(fixed):
            u = m.group(1).title()
            if u not in seen:
                seen.add(u)
                units_found.append(u)

    stats.units_before = len(
        re.findall(
            r"\b(Engine|Rescue|Ladder|Batt(?:alion)?|Crisis\s+Response)\s*\d{1,3}\b",
            fixed,
            re.I,
        )
    )
    stats.units_after = len(units_found)
    stats.deduped_units = stats.units_before - stats.units_after

    # Extract channel
    chan = None
    m = CHAN_RE.search(fixed)
    if m:
        chan = f"K-Deck {int(m.group(1))}"
        stats.channel_found = True

    # Extract address
    addr = _normalize_address(fixed)
    stats.address_found = addr is not None

    stats.chars_after = len(fixed)

    return CleanResult(
        text=fixed,
        units=units_found,
        channel=chan,
        address=addr,
        stats=stats,
    )
