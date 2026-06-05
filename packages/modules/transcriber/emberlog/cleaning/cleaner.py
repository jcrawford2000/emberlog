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
    (?P<num>\d{{2,5}})
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
            rest = text[m.end() :].strip()
            cross_m = re.match(r"(?:at|and)\s+(.+)", rest, re.I)
            if cross_m:
                cross = cross_m.group(1).strip()
                raw_span = text[m.start() :].strip()
                return {"raw": raw_span, "normalized": f"{m.group(0)} at {cross}"}
            notes_m = re.match(
                r"(?:northbound|southbound|eastbound|westbound).*", rest, re.I
            )
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


# ------------------- Bookend helpers -------------------


def _resolve_channel_match(m: re.Match) -> tuple[Optional[str], bool]:
    """Return (channel_string, is_mesa_mutual_aid) from a channel regex match."""
    if m.group(1):
        return f"K-Deck {int(m.group(1))}", False
    if m.group(2):
        return f"A{int(m.group(2))}", False
    if m.group(3):
        return f"Mesa Fire Channel B{int(m.group(3))}", True
    return None, False


def _extract_units_from_region(region: str, vocab: Vocab) -> list[str]:
    """Extract all unit matches from a text region, deduped by canonical name."""
    seen: set[str] = set()
    units: list[str] = []
    for pat, canonical_type, requires_number in vocab.unit_patterns:
        for m in pat.finditer(region):
            unit_str = (
                f"{canonical_type} {m.group(1)}" if requires_number else canonical_type
            )
            if unit_str not in seen:
                seen.add(unit_str)
                units.append(unit_str)
    return units


def _scan_leading_bookend(
    text: str, vocab: Vocab
) -> tuple[list[str], Optional[str], bool, int]:
    """
    Find the first channel in `text`. Extract unit patterns from the region before it.
    Returns (units, chan, is_mutual_aid, end_pos). end_pos == 0 if no channel found.
    """
    ch_m = vocab.channel_re.search(text)
    if not ch_m:
        return [], None, False, 0
    chan, is_mutual_aid = _resolve_channel_match(ch_m)
    if chan is None:
        return [], None, False, 0

    units = _extract_units_from_region(text[: ch_m.start()], vocab)

    end_pos = ch_m.end()
    ws = re.match(r"\s*", text[end_pos:])
    if ws:
        end_pos += ws.end()

    return units, chan, is_mutual_aid, end_pos


def _backward_scan_units(text: str, vocab: Vocab) -> tuple[list[str], int]:
    """
    Starting from the end of `text`, greedily consume unit tokens and 'and'
    separators working backwards. Returns (units_in_forward_order, block_start)
    where block_start is the index of the first character of the trailing unit block.
    Returns ([], len(text)) if no units are found.
    """
    seen: set[str] = set()
    units: list[str] = []
    end = len(text.rstrip())
    block_start = end

    while end > 0:
        found = False
        for pat, canonical_type, requires_number in vocab.unit_patterns:
            best_m = None
            for m in pat.finditer(text, 0, end):
                if m.end() == end:
                    best_m = m
                    break
            if best_m is not None:
                unit_str = (
                    f"{canonical_type} {best_m.group(1)}"
                    if requires_number
                    else canonical_type
                )
                if unit_str not in seen:
                    seen.add(unit_str)
                    units.insert(0, unit_str)
                block_start = best_m.start()
                # Retract past any preceding 'and' separator
                prefix = text[: best_m.start()].rstrip()
                if re.search(r"\band$", prefix, re.I):
                    prefix = re.sub(r"\s+and$", "", prefix, flags=re.I).rstrip()
                end = len(prefix)
                found = True
                break
        if not found:
            break

    if not units:
        return [], len(text)
    return units, block_start


def _scan_trailing_bookend(
    text: str, leading_end: int, leading_units: list[str], vocab: Vocab
) -> tuple[list[str], Optional[str], bool, int]:
    """
    In `text[leading_end:]`, find the last channel. Returns (units, chan,
    is_mutual_aid, trailing_start) where trailing_start marks the end of the
    middle content in `text`. Returns len(text) if no trailing channel is found.

    Trailing unit block is located by backward scan first. If the scan yields
    nothing (e.g., a non-unit directional suffix sits at the very end of the
    trailing region), fall back to using the earliest re-occurrence of a leading
    unit string as the block anchor.
    """
    segment = text[leading_end:]
    all_ch = list(vocab.channel_re.finditer(segment))
    if not all_ch:
        return [], None, False, len(text)

    last_ch_m = all_ch[-1]
    chan, is_mutual_aid = _resolve_channel_match(last_ch_m)
    if chan is None:
        return [], None, False, len(text)

    # Content between leading bookend and the trailing channel
    before_last_ch = segment[: last_ch_m.start()]

    # Phase A: backward scan (handles the common case directly)
    trailing_units, block_start = _backward_scan_units(before_last_ch, vocab)

    # Phase B fallback: if backward scan found nothing but leading units are known,
    # use their first re-occurrence to locate the block (handles trailing suffixes
    # like "Car 957 North" that prevent an exact end-position match).
    if not trailing_units and leading_units:
        anchor = len(before_last_ch)
        for unit_str in leading_units:
            unit_pat = re.compile(r"\b" + re.escape(unit_str) + r"\b", re.I)
            m = unit_pat.search(before_last_ch)
            if m and m.start() < anchor:
                anchor = m.start()
        if anchor < len(before_last_ch):
            trailing_units = _extract_units_from_region(before_last_ch[anchor:], vocab)
            block_start = anchor

    trailing_start = leading_end + block_start
    return trailing_units, chan, is_mutual_aid, trailing_start


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

    # ---- Step 3: Channel-stage ASR corrections ----
    # Run before bookend extraction so channel patterns see corrected text.
    for pat, repl in vocab.asr_corrections.get("channel", []):
        fixed, n = pat.subn(repl, fixed)
        stats.replacements_applied += n

    # ---- Step 4: Dispatch action detection ----
    incident = fixed
    dispatch_action = "initial"
    for pat, action, _is_supplement in vocab.dispatch_action_patterns:
        m = pat.match(incident)
        if m:
            dispatch_action = action
            incident = incident[m.end() :].lstrip()
            logger.debug("[%s] Dispatch action: %s", ps, dispatch_action)
            break
    parsed["dispatch_action"] = dispatch_action
    # Back-compat bool
    special_call = dispatch_action == "special_call"

    # ---- Step 5: Bookend extraction (two-phase) ----
    # Phase 1 — leading bookend: find first channel; extract units before it.
    # Phase 2 — trailing bookend: find last channel; use leading units to locate
    #   where the trailing unit block begins in the between-channel content.
    # The middle remainder (between bookends) is passed to all subsequent steps;
    # no unit pattern matching runs on it, preventing false matches like
    # "Rescue 2425" inside "Mountain Rescue 2425 East Valley View Drive".
    logger.info("[%s] Extracting Units (bookend)", ps)

    leading_units, leading_chan, leading_mutual_aid, leading_end = (
        _scan_leading_bookend(incident, vocab)
    )
    trailing_units, trailing_chan, trailing_mutual_aid, trailing_start = (
        _scan_trailing_bookend(incident, leading_end, leading_units, vocab)
    )

    # Merge and deduplicate units (leading order preserved, trailing adds new entries)
    seen_units: set[str] = set(leading_units)
    units_found: list[str] = list(leading_units)
    for u in trailing_units:
        if u not in seen_units:
            seen_units.add(u)
            units_found.append(u)

    chan: Optional[str] = leading_chan or trailing_chan
    is_mutual_aid = leading_mutual_aid or trailing_mutual_aid

    if chan:
        stats.channel_found = True
        logger.debug("[%s] Found channel: %s", ps, chan)
        if is_mutual_aid:
            parsed["mutual_aid"] = "Mesa"
    else:
        logger.warning("[%s] Unable to determine channel.", ps)

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

    # Middle remainder: incident_type, address (and any modifier) live here.
    incident = incident[leading_end:trailing_start].strip()
    logger.debug("[%s] Middle remainder: %s", ps, incident)

    # ---- Step 6: Response modifier extraction ----
    for pat, parsed_key, parsed_value in vocab.modifier_patterns:
        if pat.search(incident):
            parsed[parsed_key] = parsed_value
            incident = pat.sub("", incident)
    incident = re.sub(r"\s+", " ", incident).strip()
    logger.debug("[%s] After modifier removal: %s", ps, incident)

    # ---- Step 7: Address extraction (4-step cascade) ----
    logger.info("[%s] Extracting Address", ps)
    incident_type = incident.strip()
    addr: dict[str, str] = {"raw": "", "normalized": ""}

    # Sub-step 7a: 9xx-style incident code at front
    m = re.match(r"^(?P<code>\d{3})\b\s+(?P<rest>.+)", incident_type)
    if m:
        code_str = m.group("code")
        rest_after_code = m.group("rest").strip()

        # For stem codes (e.g. 962), check for a known qualifier phrase before the address.
        # "962 involving pedestrian I-10 at..." → type="962 involving pedestrian", addr="I-10..."
        consumed_qualifier = None
        for entry in vocab.incident_type_entries:
            if entry.get("code") == code_str and entry.get("is_stem"):
                for q in sorted(
                    entry.get("qualifiers", []), key=lambda x: -len(x["phrase"])
                ):
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
        # Sub-step 7b: Numbered address anywhere
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
            # Sub-step 7c: Street anchor (intersection / freeway, no leading house number)
            m_anchor = STREET_ANCHOR_RE.search(incident_type)
            if m_anchor:
                prefix = incident_type[: m_anchor.start()].rstrip()
                address_text = incident_type[m_anchor.start() :].lstrip()

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
                # Sub-step 7d: Last resort — try the full remaining string.
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

    # ---- Step 8: Incident type cleanup and vocab match ----
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
