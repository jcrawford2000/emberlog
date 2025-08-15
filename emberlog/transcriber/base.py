"""Abstract Interface for Transcribers"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from emberlog.models import Transcript


class Transcriber(ABC):
    """Abstract Transcriber Class"""

    @abstractmethod
    def transcribe(self, audio_path: Path) -> Transcript: ...
