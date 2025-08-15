"""Model Definition Class"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field


class Transcript(BaseModel):
    """Transcript Model Definition"""

    audio_path: Path
    text: str
    duration_s: float | None = None
    language: str = "en"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
