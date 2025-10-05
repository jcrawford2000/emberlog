from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

log = logging.getLogger("emberlog.segmentation.splitter")


@dataclass
class Segment:
    start: float
    end: float
    text: str


@dataclass
class Dispatch:
    audio_path: str
    text: str  # concatenated segment text


# --- Patterns ---------------------------------------------------------------

# KDEC variants: "KDEC 9", "K-Deck 10", "K deck8"
# KDEC_RE = re.compile(r"\bK\s*[-]?\s*D(?:ec|EC|eck|ECK)?\s*(\d{1,2})\b", re.I)

KDEC_RE = re.compile(
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

# Half-hour timestamp IDs to ignore entirely:
#   "1530 hours, Phoenix Fire Regional Dispatch."
TS_ANNOUNCE_RE = re.compile(
    r"\b([01]?\d|2[0-3])[0-5]\d\s+hours,?\s+Phoenix\s+Fire\s+Regional\s+Dispatch\.?",
    re.I,
)


def _strip_announce(s: str) -> str:
    if bool(TS_ANNOUNCE_RE.search(s)):
        stripped = TS_ANNOUNCE_RE.sub("", s)
        return stripped
    else:
        return s


def split_transcript(segments: Iterable[Segment], audio_path: Path) -> List[Dispatch]:
    # 1) filter out timestamp announcements and empty text
    ps = audio_path.stem
    segs = [s for s in segments if s.text]
    if not segs:
        log.warning("[%s] No Segments, skipping", ps)
        return []
    out: List[Dispatch] = []
    for seg in segs:
        log.debug("[%s] Splitting Segment", ps)
        # Check if this segment is a timestamp
        text = _strip_announce(seg.text)
        if not text:
            log.debug("[%s] Stripped Timestamp Announcement, no remaining text.", ps)
            continue
        # This segment could still contain multiple dispatches if whisper didn't detect
        # We use the Channel as the boundry since it's voiced twice
        result = KDEC_RE.finditer(text)
        cur_chan = ""
        dispatches = 0
        disp_chan_index = 0
        disp_start = 0
        disp_end = 0
        for occurance in result:
            log.debug(
                "[%s] Cur_Chan:%s | Occurance:%s", ps, cur_chan, occurance.group(0)
            )
            if cur_chan != occurance.group(0):
                cur_chan = occurance.group(0)
                log.debug("[%s] Dispatch Start, channel:%s", ps, cur_chan)
                disp_chan_index = 0
                dispatches = dispatches + 1
            elif disp_chan_index == 0:
                log.debug("[%s] Dispatch End.", ps)
                disp_chan_index = 1
                disp_end = occurance.end()
                out.append(
                    Dispatch(audio_path=str(audio_path), text=text[disp_start:disp_end])
                )
                disp_start = disp_end + 1
            else:
                log.debug("[%s] New dispatch on same channel!", ps)
                disp_chan_index = 0
                cur_chan = occurance.group(0)
                log.debug("[%s] Dispatch Start, channel: %s", ps, cur_chan)
                dispatches = dispatches + 1
    return out
