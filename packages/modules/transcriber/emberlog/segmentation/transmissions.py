"""Split a call into dispatches using trunk-recorder's per-call JSON sidecar.

trunk-recorder writes ``<call>.json`` next to each ``<call>.wav``. Its
``freqList`` gives every transmission's position and length inside the WAV
(and ``srcList`` the radio ID that keyed up). On the dispatch talkgroup each
transmission from the console is one dispatch, which is a far more reliable
boundary than finding channel bookends in the transcript text.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from emberlog.segmentation.splitter import KDEC_RE, _strip_announce

log = logging.getLogger("emberlog.segmentation.transmissions")


@dataclass(frozen=True)
class Transmission:
    index: int  # 1-based, in call order
    pos: float  # seconds from the start of the WAV
    length: float  # seconds
    src: int | None = None  # radio ID that keyed up (e.g. the dispatch console)
    time: int | None = None  # epoch seconds when the transmission started


def sidecar_path(audio: Path) -> Path:
    return Path(audio).with_suffix(".json")


def load_transmissions(sidecar: Path) -> list[Transmission] | None:
    """Parse a trunk-recorder call JSON. None if missing, unreadable or empty."""
    try:
        data = json.loads(Path(sidecar).read_text())
    except (OSError, ValueError) as e:
        log.debug("No usable sidecar %s: %s", sidecar, e)
        return None
    freqs = data.get("freqList") or []
    if not freqs:
        return None
    # srcList and freqList are parallel in practice; fall back to matching by pos.
    srcs = data.get("srcList") or []
    src_by_pos = {round(float(s.get("pos", -1)), 2): s.get("src") for s in srcs}
    out: list[Transmission] = []
    for i, f in enumerate(freqs):
        try:
            pos, length = float(f["pos"]), float(f["len"])
        except (KeyError, TypeError, ValueError):
            log.warning("Malformed freqList entry in %s: %r", sidecar, f)
            return None
        if i < len(srcs) and round(float(srcs[i].get("pos", -1)), 2) == round(pos, 2):
            src = srcs[i].get("src")
        else:
            src = src_by_pos.get(round(pos, 2))
        out.append(Transmission(index=i + 1, pos=pos, length=length, src=src, time=f.get("time")))
    return out


def cut_transmission(audio: Path, tx: Transmission, out_dir: Path | None = None) -> Path:
    """Write one transmission of ``audio`` to its own WAV; the caller deletes it.

    The file is named ``<call>-tx<N>.wav`` so backend logs stay readable.
    Backends apply their usual tone trim and resampling to it.
    """
    audio = Path(audio)
    out_dir = Path(out_dir or tempfile.mkdtemp(prefix="emberlog-tx-"))
    out = out_dir / f"{audio.stem}-tx{tx.index}.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{tx.pos:.3f}",
            "-t",
            f"{tx.length:.3f}",
            "-i",
            str(audio),
            str(out),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )
    return out


# Channel mentions the text splitter's KDEC_RE misses but that still mark a
# dispatch: "K-Deck" whose number was lost ("Medic 331, K-Deck.") and
# hyphenated fire channels ("Fire to A-10").
_LOOSE_CHANNEL_RE = re.compile(r"\bK[- ]?De(?:ck|c)\b|\bA-\d{1,2}\b", re.IGNORECASE)


def dispatch_text(text: str) -> str | None:
    """Return the transmission's text if it looks like a dispatch, else None.

    Time-check announcements are stripped first. A dispatch must name a channel
    (K-Deck N / Fire Channel AN, as the text splitter requires, or the looser
    forms above). This drops unit traffic and instructions such as
    "Engine 40, you're clearing on channel 1".
    """
    cleaned = _strip_announce(text or "").strip()
    if not cleaned:
        return None
    if not (KDEC_RE.search(cleaned) or _LOOSE_CHANNEL_RE.search(cleaned)):
        return None
    return cleaned
