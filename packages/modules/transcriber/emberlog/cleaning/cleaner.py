from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

from emberlog.models import Transcript
from emberlog.cleaning.vocab_loader import Vocab, load_vocab, match_incident_type

logger = logging.getLogger("emberlog.cleaning.cleaner")

# Load the region vocab once at import time.
# To use a different region set EMBERLOG_REGION_DIR before importing this module.
_VOCAB: Vocab = load_vocab()


# ------------------- Address extraction -------------------

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

_ORD_ADDR = r"\d{1,4}(?:st|nd|rd|th)\b"
ADDR_RE = re.compile(
    rf"""
    \b
    (?P<num>\d{{3,5}})
    \s+
    (?P<compass>North|South|East|West|N|S|E|W)
    \s+
    (?P<name>
        (?:{_ORD_ADDR}|[A-Z][A-Za-z0-9\-']*)
        (?:\s+
            (?!
                (?:Avenue|Ave|Street|St|Road|Rd|Drive|Dr|Lane|Ln|Way|
                 Boulevard|Blvd|Place|Pl|Court|Ct|Terrace|Ter|Trail|Trl|Parkway|Pkwy|Mall)\b
                |Engine\b|Rescue\b|Ladder\b|Batt(?:alion)?\b
                |Crisis\s+Response\b
                |K-?Deck\b
            )
            (?:{_ORD_ADDR}|[A-Z][A-Za-z0-9\-']*)
        )*
    )
    (?:\s+(?P<type>
        Avenue|Ave|Street|St|Road|Rd|Drive|Dr|Lane|Ln|Way|
        Boulevard|Blvd|Place|Pl|Court|Ct|Terrace|Ter|Trail|Trl|Parkway|Pkwy|Mall
    ))?
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
ORD = r"(?:\d{1,3}(?:st|nd|rd|th))"
WORD = r"(?:[A-Z][A-Za-z0-9''\-]*)"

STREET_ANCHOR_RE = re.compile(
    rf"""
    \b(
        {DIR}\s+{WORD}
        |{ORD}
        |{WORD}\s+{STREET_TYPE}\b
    )
    """,
    re.I | re.X,
)

INTERSECTION_RE = re.compile(
    rf"""
    \b
    (?P<street1>
        (?:(?P<pre1>{DIR})\s+)?
        (?P<name1>
            (?:{ORD}|{WORD})
            (?:\s+(?:{ORD}|{WORD}))*
        )
        (?:\s+(?P<type1>{STREET_TYPE}))?
    )
    \s+(?:and|&|at)\s+
    (?P<street2>
        (?:(?P<pre2>{DIR})\s+)?
        (?P<name2>
            (?:{ORD}|{WORD})
            (?:\s+(?:{ORD}|{WORD}))*
        )
        (?:\s+(?P<type2>{STREET_TYPE}))?
    )
    (?P<notes>
        (?:\s+(?:northbound|southbound|eastbound|westbound))?
        (?:\s+(?:north|south|east|west)\s+of)?
    )?
    \b
    """,
    re.I | re.X,
)

FREEWAY_INTERSECTION_RE = re.compile(
    rf"""
    \b
    (?P<freeway>
        I-?\d+|Loop\s+\d+|US\s*\d+|SR\s*\d+|A(\s*|-)\d{{2,3}}
    )
    \s+(at|and)\s+
    (?P<cross_street>
        (?:(?P<pre>{DIR})\s+)?
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
    # 1. Numbered address
    m = ADDR_RE.search(text)
    if m:
        num = m.group("num")
        comp = COMPASS_WORDS.get(m.group("compass").lower(), m.group("compass").upper())
        name = " ".join(part.capitalize() for part in m.group("name").split())
        stype = m.group("type")
        if stype:
            stype = ST_TYPE_MAP.get(stype.lower(), stype.title())
            return {
                "raw": f"{m.group('num')} {m.group('compass')} {m.group('name')} {m.group('type')}",
                "normalized": f"{num} {comp} {name} {stype}",
            }
        return {
            "raw": m.group(0),
            "normalized": f"{num} {comp} {name}",
        }

    logger.info("Unable to extract address, trying intersection types")

    # 2. Named interchange (vocab) — bare landmark address form
    if _VOCAB.interchange_re:
        m = _VOCAB.interchange_re.search(text)
        if m:
            return {"raw": m.group(0), "normalized": m.group(0)}

    # 3. General intersection — runs BEFORE freeway alias so "I-10 at N 7th St" is
    #    normalized to "I-10 and N 7th St" (converting "at" → "and"), matching corpus form.
    m = INTERSECTION_RE.search(text)
    if m:
        notes = (m.group("notes") or "").strip()
        normalized = f"{m.group('street1')} and {m.group('street2')}"
        if notes:
            normalized += f" {notes}"
        return {
            "raw": m.group(0),
            "normalized": normalized.strip(),
        }

    # 4. Freeway alias (vocab) — catches named freeways not covered by INTERSECTION_RE
    #    (e.g. "Papago Freeway westbound" with no cross street) or bare interchange names.
    if _VOCAB.freeway_re:
        m = _VOCAB.freeway_re.search(text)
        if m:
            rest = text[m.end():].strip()
            cross_m = re.match(r"(?:at|and)\s+(.+)", rest, re.I)
            if cross_m:
                cross = cross_m.group(1).strip()
                raw_span = text[m.start():].strip()
                return {"raw": raw_span, "normalized": f"{m.group(0)} at {cross}"}
            notes_m = re.match(r"(?:northbound|southbound|eastbound|westbound).*", rest, re.I)
            if notes_m or not rest:
                return {"raw": m.group(0), "normalized": m.group(0)}

    # 5. Structural freeway form (I-10 at Nth Ave)
    m = FREEWAY_INTERSECTION_RE.search(text)
    if m:
        notes = (m.group("notes") or "").strip()
        normalized = f"{m.group('freeway')} at {m.group('cross_street')}"
        if notes:
            normalized += f" {notes}"
        return {
            "raw": m.group(0),
            "normalized": normalized.strip(),
        }

    logger.warning("Unable to parse address")
    return None


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
    parsed: dict
    stats: CleanStats


# ------------------- Cleaner -------------------


def clean_transcript(t: Transcript, vocab: Vocab = _VOCAB) -> CleanResult:
    ps = t.audio_path.stem
    raw = t.text or ""
    logger.info("[%s] Cleaning Transcript: %s", ps, raw)
    stats = CleanStats(chars_before=len(raw))
    parsed: dict = {}

    # ---- Step 1: ASR corrections (pre_extraction stage) ----
    fixed = raw
    for pat, repl in vocab.asr_corrections.get("pre_extraction", []):
        fixed, n = pat.subn(repl, fixed)
        stats.replacements_applied += n

    # ---- Step 2: Whitespace/punctuation cleanup ----
    fixed = re.sub(r",+", "", fixed)
    fixed = re.sub(r"\.+", "", fixed)
    fixed = re.sub(r"\s+", " ", fixed).strip()
    logger.debug("[%s] Normalized: %s", ps, fixed)

    # ---- Step 3: Dispatch action detection ----
    incident = fixed
    dispatch_action = "initial"
    for pat, action, _is_supplement in vocab.dispatch_action_patterns:
        m = pat.match(incident)
        if m:
            dispatch_action = action
            incident = incident[m.end():].lstrip()
            logger.debug("[%s] Dispatch action: %s", ps, dispatch_action)
            break
    parsed["dispatch_action"] = dispatch_action
    # Back-compat bool
    special_call = dispatch_action == "special_call"

    # ---- Step 4: Unit extraction ----
    logger.info("[%s] Extracting Units", ps)
    # Track both the canonical unit name (for output) and the literal matched text
    # (for removal). Dedup by canonical name.
    seen_units: set[str] = set()
    unit_matches: list[tuple[str, str]] = []  # (canonical_name, literal_matched_text)

    for pat, canonical_type, requires_number in vocab.unit_patterns:
        for m in pat.finditer(fixed):
            if requires_number:
                unit_str = f"{canonical_type} {m.group(1)}"
            else:
                unit_str = canonical_type
            if unit_str not in seen_units:
                seen_units.add(unit_str)
                unit_matches.append((unit_str, m.group(0)))

    units_found = [name for name, _ in unit_matches]
    logger.debug("[%s] Units found: %s", ps, units_found)

    # Remove unit text from working string (case-insensitive)
    for _, literal in unit_matches:
        incident = re.sub(re.escape(literal), "", incident, flags=re.I)

    # Strip LEADING and TRAILING "and" tokens (bookend unit/channel separators).
    # Middle "and" connectors (intersection addresses) are intentionally preserved.
    incident = re.sub(r"^(?:and\s+)+", "", incident)
    incident = re.sub(r"(?:\s+and)+$", "", incident)
    incident = re.sub(r"\s+", " ", incident).strip()
    logger.debug("[%s] After unit removal: %s", ps, incident)

    stats.units_after = len(units_found)

    # ---- Step 5: Channel-stage ASR corrections ----
    # Applied to fixed so channel matching sees the corrected text
    for pat, repl in vocab.asr_corrections.get("channel", []):
        fixed, n = pat.subn(repl, fixed)
        stats.replacements_applied += n
        # Also apply to the working incident string
        incident, _ = pat.subn(repl, incident)

    # ---- Step 6: Channel extraction ----
    logger.info("[%s] Extracting Channel", ps)
    chan: Optional[str] = None
    m = vocab.channel_re.search(fixed)
    if m:
        if m.group(1):
            chan = f"K-Deck {int(m.group(1))}"
            stats.channel_found = True
        elif m.group(2):
            chan = f"A{int(m.group(2))}"
            stats.channel_found = True
        elif m.group(3):
            chan = f"Mesa Fire Channel B{int(m.group(3))}"
            stats.channel_found = True
            parsed["mutual_aid"] = "Mesa"

        if chan:
            logger.debug("[%s] Found channel: %s", ps, chan)
            incident = vocab.channel_re.sub("", incident)
        else:
            logger.warning("[%s] Unable to determine channel.", ps)
    else:
        logger.warning("[%s] Unable to determine channel.", ps)

    incident = re.sub(r"^(?:and\s+)+", "", incident)
    incident = re.sub(r"(?:\s+and)+$", "", incident)
    incident = re.sub(r"\s+", " ", incident).strip()
    logger.debug("[%s] After channel removal: %s", ps, incident)

    # ---- Step 7: Response modifier extraction ----
    for pat, parsed_key, parsed_value in vocab.modifier_patterns:
        if pat.search(incident):
            parsed[parsed_key] = parsed_value
            incident = pat.sub("", incident)
    incident = re.sub(r"\s+", " ", incident).strip()
    logger.debug("[%s] After modifier removal: %s", ps, incident)

    # ---- Step 8: Address extraction (4-step cascade) ----
    logger.info("[%s] Extracting Address", ps)
    incident_type = incident.strip()
    addr: dict[str, str] = {"raw": "", "normalized": ""}

    # Sub-step 8a: 9xx-style incident code at front
    m = re.match(r"^(?P<code>\d{3})\b\s+(?P<rest>.+)", incident_type)
    if m:
        code_str = m.group("code")
        rest_after_code = m.group("rest").strip()

        # For stem codes (e.g. 962), check for a known qualifier phrase before the address.
        # "962 involving pedestrian I-10 at..." → type="962 involving pedestrian", addr="I-10..."
        consumed_qualifier = None
        for entry in vocab.incident_type_entries:
            if entry.get("code") == code_str and entry.get("is_stem"):
                for q in sorted(entry.get("qualifiers", []), key=lambda x: -len(x["phrase"])):
                    ph = q["phrase"].lower()
                    rl = rest_after_code.lower()
                    if rl.startswith(ph) and (
                        len(rl) == len(ph) or not rl[len(ph) : len(ph) + 1].isalpha()
                    ):
                        consumed_qualifier = f"{code_str} {q['phrase']}"
                        rest_after_code = rest_after_code[len(q["phrase"]) :].lstrip()
                        break
                break

        incident_type = consumed_qualifier or code_str
        address_text = rest_after_code
        addr_candidate = _normalize_address(address_text)
        if addr_candidate is not None:
            addr = addr_candidate
        else:
            # 9xx rest is always address text — use raw when normalization fails
            addr = {"raw": address_text, "normalized": address_text}

    else:
        # Sub-step 8b: Numbered address anywhere
        m_addr = ADDR_RE.search(incident_type)
        if m_addr:
            prefix = incident_type[: m_addr.start()].strip()
            address_text = incident_type[m_addr.start() : m_addr.end()].strip()
            incident_type = prefix
            addr_candidate = _normalize_address(address_text)
            if addr_candidate is not None:
                addr = addr_candidate
            else:
                addr = {"raw": address_text, "normalized": address_text}

        else:
            # Sub-step 8c: Street anchor (intersection / freeway, no leading house number)
            m_anchor = STREET_ANCHOR_RE.search(incident_type)
            if m_anchor:
                prefix = incident_type[: m_anchor.start()].rstrip()
                address_text = incident_type[m_anchor.start():].lstrip()

                num_match = re.search(r"\b(\d{3,5})\s*$", prefix)
                if num_match:
                    house_num = num_match.group(1)
                    prefix = prefix[: num_match.start()].rstrip()
                    address_text = f"{house_num} {address_text}"

                addr_candidate = _normalize_address(address_text)
                if addr_candidate is not None:
                    incident_type = prefix
                    addr = addr_candidate
                elif num_match:
                    # House number confirmed the split — use raw text when normalization
                    # fails (e.g. no-compass addresses like "5325 Butler Drive").
                    incident_type = prefix
                    addr = {"raw": address_text, "normalized": address_text}
                # If no house number and normalization failed — don't split (false positive risk)

            if not addr["normalized"]:
                # Sub-step 8d: Last resort — try the full remaining string.
                # Reached when anchor matched but didn't normalize, or no anchor at all.
                addr_candidate = _normalize_address(incident_type)
                if addr_candidate is not None:
                    addr = addr_candidate
                    raw_span = addr.get("raw", "")
                    if raw_span and raw_span in incident_type:
                        incident_type = incident_type.replace(raw_span, "").strip()

    if addr["normalized"]:
        stats.address_found = True
        logger.debug("[%s] Address: %s", ps, addr)
        incident = incident_type
    else:
        logger.warning("[%s] Unable to determine address", ps)

    # ---- Step 9: Incident type cleanup and vocab match ----
    incident = re.sub(r"\s+", " ", incident).strip()

    # Apply incident_type ASR corrections (sound-alike fixes on the residual)
    for pat, repl in vocab.asr_corrections.get("incident_type", []):
        incident, n = pat.subn(repl, incident)
        stats.replacements_applied += n

    # Strip stray "and" tokens
    incident = re.sub(r"(?:\band\s*)+", "", incident).strip()
    incident = re.sub(r"\s+", " ", incident).strip()

    # Vocab match: normalize to canonical phrase when recognized
    match = match_incident_type(incident, vocab)
    if match:
        canonical_phrase, code = match
        parsed["incident_code"] = code
        incident = canonical_phrase
        logger.debug("[%s] Incident type matched: %s (%s)", ps, canonical_phrase, code)
    else:
        logger.debug("[%s] Incident type unmatched, using residual: %r", ps, incident)

    stats.chars_after = len(fixed)
    logger.info(
        "[%s] Cleaner finished. units=%s channel=%s incident=%s address=%s parsed=%s",
        ps,
        units_found,
        chan,
        incident,
        addr,
        parsed,
    )

    return CleanResult(
        text=fixed,
        special_call=special_call,
        units=units_found,
        channel=chan,
        incident_type=incident,
        address=addr["normalized"],
        parsed=parsed,
        stats=stats,
    )
