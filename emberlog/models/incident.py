"""Model Definition Class"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field


class Incident(BaseModel):
    """Incident Model Definition"""

    incident_type: str | None = None
    address: str | None = None
    channel: str | None = None
    units: list[str] = Field(default_factory=list)
    raw_text: str
    audio_path: Path
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
