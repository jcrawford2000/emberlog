"""Dummy transcriber backend for wiring and tests.

Returns a deterministic transcript without touching any audio. Useful for
plumbing the watcher/queue/worker flow end-to-end.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from emberlog.config.config import get_settings

# Import your real Transcript model (works whether it's models.py or models package)
from emberlog.models import Transcript  # noqa: F401  (used in type hints)
from emberlog.utils.logger import get_logger

settings = get_settings()
log = get_logger(settings.log_level)


class DummyTranscriber:
    """A no-op transcriber that fabricates a transcript for a given file."""

    async def transcribe(self, path: Path) -> Transcript:
        """Async shim that delegates to the sync implementation.

        Args:
            path: Path to the audio file (ignored in dummy).

        Returns:
            Transcript: A fabricated transcript object.
        """
        # Yield control so this behaves nicely alongside real async backends.
        await asyncio.sleep(0)
        return self._transcribe_impl(path)

    # --- your existing sync logic can live here, unchanged ---
    def _transcribe_impl(self, path: Path) -> Transcript:
        """Synchronous implementation that builds a fake transcript."""
        # If you already had code building a Transcript, keep it here.
        # Example stub below—replace with your existing fields/shape.
        # NOTE: This assumes a pydantic model with fields `source` and `text`.
        return Transcript(
            duration_s=10,
            language="en",
            audio_path=path,
            text="Engine 703 K-Deck 10 Test Call 700 North Watson Engine 703 K-Deck 10",
        )
