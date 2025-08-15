"""Job model for Ember Log's processing queue.

Defines a `Job` representing a single audio file to be processed by the
transcription pipeline. Jobs track attempts for simple retry/backoff logic.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field


class Job(BaseModel):
    """A unit of work representing an audio file to process.

    Attributes:
        id: Unique identifier for the job.
        path: Filesystem path to the audio file.
        created_at: UTC timestamp when the job was created/enqueued.
        attempts: Number of processing attempts so far.
        max_attempts: Maximum attempts before the job is abandoned.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    path: Path
    created_at: datetime = Field(default_factory=datetime.utcnow)
    attempts: int = 0
    max_attempts: int = 3

    class Config:
        """Job Config"""

        arbitrary_types_allowed = True
