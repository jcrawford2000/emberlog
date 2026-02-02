from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from emberlog.models import Transcript


class StubFixtureTranscriber:
    """Transcriber backend that reads fixed transcript fixtures from text files."""

    def __init__(self, transcripts_dir: Path):
        self.transcripts_dir = Path(transcripts_dir)

    async def transcribe(self, path: Path) -> Transcript:
        txt_path = self.transcripts_dir / f"{Path(path).stem}.txt"
        text = txt_path.read_text(encoding="utf-8").strip()
        created_at = datetime.now(timezone.utc)
        m = re.search(r"1795-(\d+)", Path(path).stem)
        if m:
            created_at = datetime.fromtimestamp(int(m.group(1)), tz=timezone.utc)
        return Transcript(
            audio_path=Path(path),
            text=text,
            start=0.0,
            end=0.0,
            duration_s=0.0,
            language="en",
            created_at=created_at,
        )
