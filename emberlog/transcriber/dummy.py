"""Dummy Transcription For Testing Purposes"""

from __future__ import annotations

from pathlib import Path

from emberlog.models import Transcript


class DummyTranscriber:
    """Dummy Class"""

    def transcribe(self, audio_path: Path) -> Transcript:
        """Dummy Transcriptions for Testing Purposes"""
        text = (
            f"Dispatch received for file: {audio_path.name}. "
            "Units: Engine 1, Ladder 1. Type: Test Call. "
            "Address: 123 Example St."
        )
        return Transcript(audio_path=audio_path, text=text, duration_s=None)
