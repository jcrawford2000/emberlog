"""Audio preprocessing shared by transcriber backends."""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger("emberlog.transcriber.audio")


def trim_dispatch_tones(src: Path, ms: int = 600) -> Path:
    """Drop the leading dispatch tones and resample to 16 kHz mono WAV.

    Returns the path of a temporary WAV file; the caller must delete it.
    """
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    logger.debug("Trimming Dispatch Tones from %s into %s", src, tmp_path)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(src),
            "-ss",
            f"{ms / 1000:.3f}",
            "-ac",
            "1",
            "-ar",
            "16000",
            str(tmp_path),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )
    return tmp_path
