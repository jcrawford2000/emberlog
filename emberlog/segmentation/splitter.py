from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List


@dataclass
class Segment:
    start: float
    end: float
    text: str


@dataclass
class Dispatch:
    audio_path: str
    start_s: float
    end_s: float
    channel: int | None  # parsed KDEC number if found
    text: str  # concatenated segment text
    segments: List[Segment]


# --- Patterns ---------------------------------------------------------------

# KDEC variants: "KDEC 9", "K-Deck 10", "K deck8"
KDEC_RE = re.compile(r"\bK\s*[-]?\s*D(?:ec|eck)?\s*(\d{1,2})\b", re.I)

# A minimal “unit block” detector (used only to spot likely dispatch starts)
UNIT_TOKEN = re.compile(
    r"\b(?:Engine|Rescue|Ladder(?:\s+Tender)?|Batt(?:alion)?|Crisis\s+Response|Truck|Medic)\s*\d{1,3}\b",
    re.I,
)

# “Special Call …” should force a new dispatch even if channel repeats
SPECIAL_CALL_RE = re.compile(r"\bSpecial\s+Call\b", re.I)

# Half-hour timestamp IDs to ignore entirely:
#   "1530 hours, Phoenix Fire Regional Dispatch."
TS_ANNOUNCE_RE = re.compile(
    r"\b([01]?\d|2[0-3])[0-5]\d\s+hours,?\s+Phoenix\s+Fire\s+Regional\s+Dispatch\.?",
    re.I,
)

# If segments are very long, avoid gluing multiple calls forever
MAX_DISPATCH_SPAN_S = 240.0  # 4 minutes
SILENCE_BOUNDARY_S = 2.5  # optional helper boundary if needed


def _is_announce(s: str) -> bool:
    return bool(TS_ANNOUNCE_RE.search(s))


def _first_kdec_number(s: str) -> int | None:
    m = KDEC_RE.search(s)
    return int(m.group(1)) if m else None


def _looks_like_dispatch_lead(s: str) -> bool:
    # a “lead” is a unit burst or a Special Call before the first KDEC
    if SPECIAL_CALL_RE.search(s):
        return True
    # unit token near front is a good hint
    return bool(UNIT_TOKEN.search(s))


def split_transcript(segments: Iterable[Segment], audio_path: str) -> List[Dispatch]:
    # 1) filter out timestamp announcements and empty text
    segs = [s for s in segments if s.text and not _is_announce(s.text)]
    if not segs:
        return []

    groups: List[List[Segment]] = [[]]
    groups[0].append(segs[0])

    # candidate channel for current group (first KDEC we see inside it)
    cur_ch: int | None = _first_kdec_number(segs[0].text)

    for prev, cur in zip(segs, segs[1:]):
        gap = cur.start - prev.end
        cur_text = cur.text

        # signals for a boundary
        next_ch = _first_kdec_number(cur_text)
        special_call_ahead = bool(
            SPECIAL_CALL_RE.search(cur_text)
        )  # before any next KDEC in this segment

        boundary = False

        # A. “Special Call …” starts a new dispatch (even if channel repeats)
        if special_call_ahead and _looks_like_dispatch_lead(cur_text):
            boundary = True

        # B. Channel changes → definite new dispatch
        elif next_ch is not None and cur_ch is not None and next_ch != cur_ch:
            boundary = True

        # C. Conservative helpers: long silence or overly long span
        elif gap >= SILENCE_BOUNDARY_S:
            boundary = True
        else:
            # if current group is getting too long, cut at the largest cue we have
            span = groups[-1][-1].end - groups[-1][0].start
            if span >= MAX_DISPATCH_SPAN_S:
                boundary = True

        if boundary:
            groups.append([cur])
            cur_ch = _first_kdec_number(cur_text)
        else:
            groups[-1].append(cur)
            # set channel if we didn’t have one yet
            if cur_ch is None and next_ch is not None:
                cur_ch = next_ch

    # finalize
    out: List[Dispatch] = []
    for g in groups:
        txt = " ".join(s.text.strip() for s in g if s.text).strip()
        chan = None
        # first KDEC inside the group is the group’s channel
        for s in g:
            c = _first_kdec_number(s.text)
            if c is not None:
                chan = c
                break
        out.append(
            Dispatch(
                audio_path=audio_path,
                start_s=g[0].start,
                end_s=g[-1].end,
                channel=chan,
                text=txt,
                segments=g,
            )
        )
    return out
