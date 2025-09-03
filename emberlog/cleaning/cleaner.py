from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import List, Optional

from emberlog.models import Transcript  # your existing model

logger = logging.getLogger("emberlog.cleaning.cleaner")

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
# ADDR_RE = re.compile(
#    r"\b(?P<num>\d{3,5})\s+(?P<compass>[NnSsEeWw]|North|South|East|West)\s+"
#    r"(?P<name>(?:[A-Z][A-Za-z0-9\-']*(?:\s+[A-Z][A-Za-z0-9\-']*)*))"
#    r"(?:\s+(?P<type>Avenue|Ave|Street|St|Road|Rd|Drive|Dr|Lane|Ln|Way|Boulevard|Blvd|Place|Pl|Court|Ct|Terrace|Ter|Trail|Trl|Parkway|Pkwy))?\b",
#    re.I,
# )
ADDR_RE = re.compile(
    r"""
    \b
    (?P<num>\d{3,5})
    \s+
    (?P<compass>N|S|E|W|North|South|East|West)
    \s+
    # Street name tokens: Capitalized words, but NOT street types or unit/channel words
    (?P<name>
        [A-Z][A-Za-z0-9\-']*
        (?:\s+
            (?! # stop tokens the name must NOT absorb
                (?:Avenue|Ave|Street|St|Road|Rd|Drive|Dr|Lane|Ln|Way|
                 Boulevard|Blvd|Place|Pl|Court|Ct|Terrace|Ter|Trail|Trl|Parkway|Pkwy)\b
                |Engine\b|Rescue\b|Ladder\b|Batt(?:alion)?\b
                |Crisis\s+Response\b
                |K-?Deck\b
            )
            [A-Z][A-Za-z0-9\-']*
        )*
    )
    # Optional street type (kept separate from name)
    (?:\s+(?P<type>
        Avenue|Ave|Street|St|Road|Rd|Drive|Dr|Lane|Ln|Way|
        Boulevard|Blvd|Place|Pl|Court|Ct|Terrace|Ter|Trail|Trl|Parkway|Pkwy
    ))?
    # After the address, allow end, a number, a unit, or K-Deck — but don't consume it
    (?=
        (?:\s+(?:\d{1,5}\b
               |Engine\b|Rescue\b|Ladder\b|Batt(?:alion)?\b
               |Crisis\s+Response\b|K-?Deck\b))?
        |$
    )
    """,
    re.I | re.X,
)


def _normalize_address(text: str) -> Optional[dict[str, str]]:
    m = ADDR_RE.search(text)
    if not m:
        logger.info("Unable to extract address")
        return None
    logger.debug(
        "Address Groups\n\tnum:%s\n\tcompass:%s\n\tname:%s\n\ttype:%s",
        m.group("num"),
        m.group("compass"),
        m.group("name"),
        m.group("type"),
    )
    logger.debug("Cleaning Address Parts")
    num = m.group("num")
    comp = COMPASS_WORDS.get(m.group("compass").lower(), m.group("compass").upper())
    name = " ".join(part.capitalize() for part in m.group("name").split())
    stype = m.group("type")
    logger.debug(
        "Cleaned Parts:\n\tnum:%s\n\tcompass:%s\n\tname:%s\n\ttype:%s",
        num,
        comp,
        name,
        stype,
    )
    if stype:
        stype = ST_TYPE_MAP.get(stype.lower(), stype.title())
        return {
            "raw": f"{m.group("num")} {m.group("compass")} {m.group("name")} {m.group("type")}",
            "normalized": f"{num} {comp} {name} {stype}",
        }
        return f"{num} {comp} {name} {stype}"
    return {
        "raw": f"{m.group("num")} {m.group("compass")} {m.group("name")}",
        "normalized": f"{num} {comp} {name}",
    }


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
    incident_type: Optional[str]
    address: Optional[str]
    stats: CleanStats


# ------------------- Cleaner -------------------


def clean_transcript(t: Transcript) -> CleanResult:
    raw = t.text or ""
    logger.info("Cleaning Transcript: %s", raw)
    stats = CleanStats(chars_before=len(raw))

    # Apply regex replacements
    logger.info("Cleaning standard mis-heard words.")
    fixed = raw
    for pat, repl in REPLACEMENTS:
        fixed, n = pat.subn(repl, fixed)
        stats.replacements_applied += n
    if stats.replacements_applied > 0:
        logger.debug("Made %d replacements.", stats.replacements_applied)
        logger.debug("Updated Transcript: %s", fixed)
    else:
        logger.debug("No replacements made")

    # Collapse whitespace
    logger.info("Removing extra whitespace characters")
    fixed = re.sub(r"\s+", " ", fixed).strip()
    incident = fixed

    # Extract units
    logger.info("Extracting Units")
    units_found = []
    seen = set()
    for pat in UNIT_PATTERNS:
        for m in pat.finditer(fixed):
            u = m.group(1).title()
            if u not in seen:
                seen.add(u)
                units_found.append(u)
    logger.debug("Units found: %s", units_found)
    stats.units_before = len(
        re.findall(
            r"\b(Engine|Rescue|Ladder|Batt(?:alion)?|Crisis\s+Response)\s*\d{1,3}\b",
            fixed,
            re.I,
        )
    )
    stats.units_after = len(units_found)
    stats.deduped_units = stats.units_before - stats.units_after
    logger.debug("Removed %d duplicates", stats.deduped_units)
    # Remove Units from string
    for unit in units_found:
        incident = incident.replace(unit, "")

    # Extract channel
    logger.info("Extracting Channel")
    chan = None
    m = CHAN_RE.search(fixed)
    if m:
        chan = f"K-Deck {int(m.group(1))}"
        stats.channel_found = True
        logger.debug("Found channel: %s", chan)
        # Remove Channel from string
        incident = incident.replace(chan, "")
    else:
        logger.info("Unable to determine channel.")

    # Extract address
    logger.info("Extracting Address")
    addr = _normalize_address(fixed)
    if addr is not None:
        stats.address_found = True
        logger.debug("Address%s", addr)
        # Remove Channel from string
        incident = incident.replace(addr["raw"], "")
    else:
        addr = {"raw": "", "normalized": ""}

    # Strip extra spaced from the incident
    incident = re.sub(r"\s+", " ", incident).strip()
    stats.chars_after = len(fixed)
    logger.info(
        "Cleaner finished.  Result:\n\ttext=%s\n\tunits=%s\n\tchannel=%s\n\tincident=%s\n\taddress=%s\n\tstats=%s",
        fixed,
        units_found,
        chan,
        incident,
        addr,
        stats,
    )

    return CleanResult(
        text=fixed,
        units=units_found,
        channel=chan,
        incident_type=incident,
        address=addr["normalized"],
        stats=stats,
    )
