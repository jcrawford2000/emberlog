"""Factory helpers for creating transcriber backends.

Backends must implement an *async* `transcribe(path: Path) -> Transcript`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from emberlog.transcriber.dummy import DummyTranscriber
from emberlog.transcriber.stub import StubFixtureTranscriber

# Importing Transcript only for type hints; avoid cycles at runtime if needed.
try:
    from emberlog.models import (
        Transcript,
    )  # works with either models.py or models/__init__.py
except Exception:  # pragma: no cover
    Transcript = object  # type: ignore[misc]


class Transcriber(Protocol):
    """Protocol that all transcribers must satisfy."""

    async def transcribe(self, path: Path) -> Transcript: ...  # type: ignore

    # Keep the signature consistent across backends.


def create(name: str = "dummy") -> Transcriber:
    """Create a transcriber by name."""
    name = (name or "dummy").lower()
    if name == "dummy":
        return DummyTranscriber()
    if name == "stub":
        return StubFixtureTranscriber(Path("samples/transcripts"))
    if name == "faster_whisper":
        from emberlog.transcriber.whisper_fast import FasterWhisperTranscriber

        return FasterWhisperTranscriber()
    raise ValueError(f"Unknown transcriber backend: {name}")


def from_settings(settings) -> Transcriber:
    """Create a transcriber using Settings (expects `transcriber_backend`)."""
    backend = getattr(settings, "transcriber_backend", "dummy")
    return create(backend)
