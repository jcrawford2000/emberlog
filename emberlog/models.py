"""Model Definition Class"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field


class Transcript(BaseModel):
    """Transcript Model Definition"""

    audio_path: Path
    text: str
    duration_s: float | None = None
    language: str = "en"
    created_at: datetime = Field(default_factory=datetime.now)


class Incident(BaseModel):
    """Incident Model Definition"""

    incident_type: str | None = None
    address: str | None = None
    channel: str | None = None
    units: list[str] = []
    raw_text: str
    audio_path: Path
    created_at: datetime = Field(default_factory=datetime.now)
