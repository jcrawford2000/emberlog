from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from emberlog.io.local_sink import LocalSink  # wherever your LocalSink lives

from .base import Sink, SinkResult


class JsonFileSink(Sink):
    """
    Writes the per-dispatch JSON using the provided LocalSink (atomic write).
    Returns out_path and cleaned_text in SinkResult.extra for downstream sinks.
    """

    def __init__(
        self, local: LocalSink, naming: str = "{stem}.json", subdir: str | None = None
    ):
        """
        local: required LocalSink(base_dir=...) that performs atomic writes.
        naming: filename pattern relative to base_dir (default uses audio stem).
        subdir: optional subdirectory under base_dir, e.g. "dispatches/2025/08/25"
        """
        self.local = local
        self.naming = naming
        self.subdir = Path(subdir) if subdir else None
        self.logger = logging.getLogger("emberlog.io.json_sink")

    def _relpath_for(self, audio_path: Path) -> Path:
        ap = audio_path if isinstance(audio_path, Path) else Path(audio_path)
        name = self.naming.format(stem=ap.stem)
        return (self.subdir / name) if self.subdir else Path(name)

    async def process(
        self,
        *,
        transcript: Any,
        incident: Any,
        audio_path: Path,
        out_dir: Path,  # kept for Sink signature compatibility; not used here
        context: dict[str, Any] | None = None,
    ) -> SinkResult:
        # Build the payload exactly once
        self.logger.debug(
            "Processing:\n\ttranscript:%s\n\tincident:%s\n\taudio_path:%s\n\tout_dir:%s\n\tcontext:%s",
            transcript,
            incident,
            audio_path,
            out_dir,
            context,
        )
        payload = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "audio_path": str(audio_path),
            "transcript": getattr(transcript, "text", None),
            "start": getattr(transcript, "start", None),
            "end": getattr(transcript, "end", None),
            "incident": (
                incident.model_dump()
                if hasattr(incident, "model_dump")
                else dict(incident or {})
            ),
        }

        rel = self._relpath_for(audio_path)
        out_path = self.local.write_json(
            rel, payload
        )  # atomic write via your LocalSink

        return SinkResult(
            ok=True,
            out_path=out_path,
            extra={
                "cleaned_text": payload["transcript"] or "",
            },
        )
