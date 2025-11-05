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
    # Crisis Response shorthand
    (re.compile(r"\bC R\s*?(\d+)\b", re.I), r"Crisis Response \1"),
    (re.compile(r"\bStage 4 PD\b", re.I), r"Stage For PD"),
]

MISHEARD_INCIDENTS = [
    # Tech Welfare -> Check Welfare
    (re.compile(r"\bTech Welfare\b", re.I), r"Check Welfare"),
    # Ill Person variations
    (
        re.compile(r"\b[A-Z]ill\s*Person\b|\bIlkerson\b|\bIlverson\b", re.I),
        r"Ill Person",
    ),
    # Park Problem -> Heart Problem
    (re.compile(r"\bPark Problem\b", re.I), r"Heart Problem"),
    # Just Payne -> Check Pain
    (re.compile(r"\bJust Payne\b", re.I), r"Chest Pain"),
    # Rush Fire -> Brush Fire
    (re.compile(r"\brush fire\b", re.I), r"Brush Fire"),
    # And no medical -> Unknown Medical
    (re.compile(r"\band no medical\b", re.I), r"Unknown Medical"),
]

UNIT_PATTERNS = [
    re.compile(r"\b(Batt(?:alion)?\s*\d{1,4})\b", re.I),
    re.compile(r"\b(Engine\s*\d{1,4})\b", re.I),
    re.compile(
        r"\b(Ladder\s+Tender\s*\d{1,4}|\bLA-\d{1,4}|Ladder\s*\d{1,4}|Truck\s*\d{1,4}|TR\s*\d{1,4})\b",
        re.I,
    ),
    re.compile(
        r"\b(Rescue\s*\d{1,4}|Medic\s*\d{1,4}|Maricopa\s*\d{1,4}|Medical Response\s*\d{1,4})\b",
        re.I,
    ),
    re.compile(r"\b(Crisis\s+Response\s*\d{1,4})\b", re.I),
    re.compile(r"\b(West Deputy)\b", re.I),
    re.compile(r"\b(Car\s+\d{1,4}\s+(?:North|South))\b", re.I),
    re.compile(r"\b(Heavy Rescue Tender\s*\d{1,4})\b", re.I),
    re.compile(r"\b(Hazmat\s*\d{1,4})\b", re.I),
    re.compile(r"\b(Brush\s*\d{1,4})\b", re.I),
    re.compile(r"\b(Car\s*\d{1,4})\b", re.I),
    re.compile(r"\b(South Deputy)\b", re.I),
    re.compile(r"\b(Medical Response\s*\d{1,4})\b", re.I),
    re.compile(r"\b(BH\s*\d{1,2})\b", re.I),
    re.compile(r"\b(Foam\s*\d{1,3})\b", re.I),
    re.compile(r"\b(Air Stair\s*\d{1,3})\b", re.I),
    re.compile(r"\b(Attack\s*\d{1,3})\b", re.I),
]

CHAN_RE = re.compile(
    r"""
    (?:                # non-capturing group for the two families
        K[- ]?De(?:ck|c)\s*(\d+)    # matches "K-Deck 8" or "K-Dec 8"
        |                        # OR
        (?:Fire\s*Channel\s*)?   # optional "Fire Channel"
        A(\d+)                     # matches "A5" or "Fire Channel A5"
    )
    """,
    re.I | re.VERBOSE,
)

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
ORD = r"\d{1,4}(?:st|nd|rd|th)\b"  # 1st..9999th
ADDR_RE = re.compile(
    rf"""
    \b
    (?P<num>\d{{3,5}})
    \s+
    (?P<compass>North|South|East|West|N|S|E|W)
    \s+
    # Street name tokens: allow Capitalized words OR ordinals like 146th
    (?P<name>
        (?:{ORD}|[A-Z][A-Za-z0-9\-']*)
        (?:\s+
            (?! # stop tokens the name must NOT absorb
                (?:Avenue|Ave|Street|St|Road|Rd|Drive|Dr|Lane|Ln|Way|
                 Boulevard|Blvd|Place|Pl|Court|Ct|Terrace|Ter|Trail|Trl|Parkway|Pkwy|Mall)\b
                |Engine\b|Rescue\b|Ladder\b|Batt(?:alion)?\b
                |Crisis\s+Response\b
                |K-?Deck\b
            )
            (?:{ORD}|[A-Z][A-Za-z0-9\-']*)
        )*
    )
    # Optional street type (kept separate from name)
    (?:\s+(?P<type>
        Avenue|Ave|Street|St|Road|Rd|Drive|Dr|Lane|Ln|Way|
        Boulevard|Blvd|Place|Pl|Court|Ct|Terrace|Ter|Trail|Trl|Parkway|Pkwy|Mall
    ))?
    # After the address, allow end, a number, a unit, or K-Deck — but don't consume it
    (?=
        (?:\s+(?:\d{{1,5}}\b
               |Engine\b|Rescue\b|Ladder\b|Batt(?:alion)?\b
               |Crisis\s+Response\b|K-?Deck\b))?
        |$
    )
    """,
    re.I | re.X,
)


STREET_TYPE = r"(?:Avenue|Ave|Street|St|Road|Rd|Drive|Dr|Lane|Ln|Way|Boulevard|Blvd|Place|Pl|Court|Ct|Terrace|Ter|Trail|Trl|Parkway|Pkwy|Freeway|Fwy|Highway|Hwy)"
DIR = r"(?:N|S|E|W|North|South|East|West)"
ORD = r"(?:\d{1,3}(?:st|nd|rd|th))"  # 5th, 7th, etc.
WORD = r"(?:[A-Z][A-Za-z0-9'’\-]*)"  # Port-au-Prince, Cinnabar, McDowell, etc.

# Street Anchors
STREET_ANCHOR_RE = re.compile(
    rf"""
    \b(
        {DIR}\s+{WORD}              # N Scottsdale, North 7th
        |{ORD}                      # 59th, 7th, 35th
        |{WORD}\s+{STREET_TYPE}     # Scottsdale Road, Roosevelt Street
    )
    """,
    re.I | re.X,
)

# --- 1) General intersection: "79th Avenue and Thunderbird Road", "5th Street & McDowell Road", "Prasada Parkway at Waddell Road"
INTERSECTION_RE = re.compile(
    rf"""
    \b
    (?P<street1>
        (?:(?P<pre1>{DIR})\s+)?             # optional pre-direction
        (?P<name1>
            (?:{ORD}|{WORD})                # first token (ordinal or capitalized)
            (?:\s+(?:{ORD}|{WORD}))*        # additional tokens
        )
        (?:\s+(?P<type1>{STREET_TYPE}))?    # optional street type
    )
    \s+(?:and|&|at)\s+                      # connector
    (?P<street2>
        (?:(?P<pre2>{DIR})\s+)?             # optional pre-direction
        (?P<name2>
            (?:{ORD}|{WORD})
            (?:\s+(?:{ORD}|{WORD}))*
        )
        (?:\s+(?P<type2>{STREET_TYPE}))?
    )
    (?P<notes>                              # optional trailing notes like "westbound", "east of"
        (?:\s+(?:northbound|southbound|eastbound|westbound))?
        (?:\s+(?:north|south|east|west)\s+of)?
    )?
    \b
    """,
    re.I | re.X,
)

# --- 2) Freeway-style: "I-10 at North 7th Street westbound east of", "I-17 at South 19th Avenue"
FREEWAY_INTERSECTION_RE = re.compile(
    rf"""
    \b
    (?P<freeway>
        I-?\d+|Loop\s+\d+|US\s*\d+|SR\s*\d+|A(\s*|-)\d{2,3}    # I-10, I17, Loop 101, US 60, SR 51
    )
    \s+(at|and)\s+
    (?P<cross_street>
        (?:(?P<pre>{DIR})\s+)?                 # optional pre-direction
        (?P<name>
            (?:{ORD}|{WORD})
            (?:\s+(?:{ORD}|{WORD}))*
        )
        (?:\s+(?P<type>{STREET_TYPE}))?
    )
    (?P<notes>
        (?:\s+(?:northbound|southbound|eastbound|westbound))?
        (?:\s+(?:north|south|east|west)\s+of)?
    )?
    \b
    """,
    re.I | re.X,
)


def _normalize_address(text: str) -> Optional[dict[str, str]]:
    m = ADDR_RE.search(text)
    if m:
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
            "raw": f"{m.group(0)}",
            "normalized": f"{num} {comp} {name}",
        }
    logger.info("Unable to extract address, trying intersection types")
    m = INTERSECTION_RE.search(text)
    if m:
        logger.debug(
            "Found Intersection:\n\tStreet 1: %s\n\tStreet 2: %s\n\tNotes: %s",
            m.group("street1"),
            m.group("street2"),
            m.group("notes"),
        )
        return {
            "raw": f"{m.group(0)}",
            "normalized": f"{m.group("street1")} and {m.group("street2")}",
        }
    logger.info("Unable to extract intersection, trying freeway types")
    m = FREEWAY_INTERSECTION_RE.search(text)
    if m:
        logger.debug(
            "Found Freeway Intersection:\n\tFreeway: %s\n\tCross Street: %s\n\tNotes: %s",
            m.group("freeway"),
            m.group("cross_street"),
            m.group("notes"),
        )
        return {
            "raw": f"{m.group(0)}",
            "normalized": f"{m.group("freeway")} at {m.group("cross_street")} {m.group("notes")}",
        }
    logger.warning("Unable to parse address")
    return


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
    special_call: bool
    units: List[str]
    channel: Optional[str]
    incident_type: Optional[str]
    address: Optional[str]
    stats: CleanStats


# ------------------- Cleaner -------------------


def clean_transcript(t: Transcript) -> CleanResult:
    ps = t.audio_path.stem
    raw = t.text or ""
    logger.info("[%s] Cleaning Transcript: %s", ps, raw)
    stats = CleanStats(chars_before=len(raw))

    # Apply regex replacements
    logger.info("[%s] Cleaning standard mis-heard words.", ps)
    fixed = raw
    for pat, repl in REPLACEMENTS:
        fixed, n = pat.subn(repl, fixed)
        stats.replacements_applied += n
    if stats.replacements_applied > 0:
        logger.debug("[%s] Made %d replacements.", ps, stats.replacements_applied)
        logger.debug("[%s] Updated Transcript: %s", ps, fixed)
    else:
        logger.debug("[%s] No replacements made", ps)

    # Collapse whitespace, special characters, 'and'
    fixed = re.sub(r",+", "", fixed)
    # fixed = re.sub(r"\band\b", "", fixed)
    logger.info("[%s] Removing periods", ps)
    fixed = re.sub(r"\.+", "", fixed)
    logger.info("[%s] Removing extra whitespace characters", ps)
    fixed = re.sub(r"\s+", " ", fixed).strip()

    incident = fixed
    logger.debug("[%s] Incident: %s", ps, incident)

    # Determine Special Call
    sc_re = re.compile(r"^special call", re.I)
    special_call = bool(sc_re.search(fixed))
    incident = sc_re.sub("", fixed)
    logger.debug("[%s] Special call? %s, Incident: %s", ps, special_call, incident)
    # Extract units
    logger.info("[%s] Extracting Units", ps)
    units_found = []
    seen = set()
    for pat in UNIT_PATTERNS:
        for m in pat.finditer(fixed):
            u = m.group(1).title()
            if u not in seen:
                seen.add(u)
                units_found.append(u)
    logger.debug("[%s] Units found: %s", ps, units_found)
    stats.units_before = len(
        re.findall(
            r"\b(Engine|Rescue|Ladder|Batt(?:alion)?|Crisis\s+Response)\s*\d{1,3}\b",
            fixed,
            re.I,
        )
    )
    stats.units_after = len(units_found)
    stats.deduped_units = stats.units_before - stats.units_after
    logger.debug("[%s] Removed %d duplicates", ps, stats.deduped_units)
    # Remove Units from string
    for unit in units_found:
        incident = incident.replace(unit, "")
    # Remove any 'and' leftover
    incident = re.sub(r"^(?:and\s+)+", "", incident)
    logger.debug("[%s] Incident: %s", ps, incident)

    # Extract channel
    logger.info("[%s] Extracting Channel", ps)
    chan = None
    m = CHAN_RE.search(fixed)
    logger.debug("[%s] Channel Regex Returned %s", ps, m)
    if m and m.group(1):
        chan = f"K-Deck {int(m.group(1))}"
        stats.channel_found = True
        logger.debug("[%s] Found channel: %s", ps, chan)
        # Remove Channel from string
        incident = CHAN_RE.sub("", incident)
    elif m and m.group(2):
        chan = f"A{int(m.group(2))}"
        stats.channel_found = True
        logger.debug("[%s] Found channel: %s", ps, chan)
        # Remove Channel from string
        incident = CHAN_RE.sub("", incident)
    else:
        logger.warning("[%s] Unable to determine channel.", ps)
    # Remove any 'and' leftover
    incident = re.sub(r"^(?:and\s+)+", "", incident)
    logger.debug("[%s] Incident: %s", ps, incident)

    # Extract address
    logger.info("[%s] Extracting Address", ps)

    incident_type = incident
    addr = {"raw": "", "normalized": ""}

    m = re.match(r"^(?P<code>\d{3})\b\s+(?P<rest>.+)", incident)
    if m:
        incident_type = m.group("code").strip()
        address_text = m.group("rest").strip()
        addr_candidate = _normalize_address(address_text)
        if addr_candidate is not None:
            addr = addr_candidate
        else:
            addr = {"raw": address_text, "normalized": address_text}
    else:
        m = STREET_ANCHOR_RE.search(incident)
        if m:
            prefix = incident[: m.start()].rstrip()
            address_text = incident[m.start() :].lstrip()
            num_match = re.search(r"\b(\d{3,5})\s*$", prefix)
            if num_match:
                house_num = num_match.group(1)
                prefix = prefix[: num_match.start()].rstrip()
                address_text = f"{house_num} {address_text}"
            incident_type = prefix
            addr_candidate = _normalize_address(address_text)
            if addr_candidate is not None:
                addr = addr_candidate
            else:
                addr = {"raw": address_text, "normalized": address_text}
        else:
            addr_candidate = _normalize_address(incident)
            if addr_candidate is not None:
                addr = addr_candidate
                incident_type = incident.replace(addr["raw"], "").strip()

    if addr["normalized"]:
        stats.address_found = True
        logger.debug("[%s] Address%s", ps, addr)
        incident = incident_type
        logger.debug("[%s] Incident after address split %s", ps, incident)
    else:
        logger.warning("[%s] Unable to determine address", ps)
    # addr = _normalize_address(incident)
    # if addr is not None:
    #    stats.address_found = True
    #    logger.debug("[%s] Address%s", ps, addr)
    #    # Remove Channel from string
    #    incident = incident.replace(addr["raw"], "")
    # else:
    #    logger.warning("[%s] Unable to determine address", ps)
    #    addr = {"raw": "", "normalized": ""}

    # Now What we should be left with is the Incident Type
    # Strip extra spaced from the incident
    incident = re.sub(r"\s+", " ", incident).strip()
    logger.debug("[%s] Incident: %s", ps, incident)

    # Fix commonly misheard incidents
    logger.debug("[%s], Fixing common mis-heard incident types", ps)
    for pat, repl in MISHEARD_INCIDENTS:
        incident, n = pat.subn(repl, incident)
        stats.replacements_applied += n

    # Remove any remaining stray and's
    incident = re.sub(r"(?:\band\s*)+", "", incident)
    logger.debug("[%s] Incident: %s", ps, incident)

    stats.chars_after = len(fixed)
    logger.info(
        "[%s] Cleaner finished.  Result:\n\ttext=%s\n\tunits=%s\n\tchannel=%s\n\tincident=%s\n\taddress=%s\n\tstats=%s",
        ps,
        fixed,
        units_found,
        chan,
        incident,
        addr,
        stats,
    )

    return CleanResult(
        text=fixed,
        special_call=special_call,
        units=units_found,
        channel=chan,
        incident_type=incident,
        address=addr["normalized"],
        stats=stats,
    )
