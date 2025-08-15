from __future__ import annotations

from emberlog.transcriber.dummy import DummyTranscriber

# from emberlog.transcriber.faster_whisper import FasterWhisperTranscriber  # later


def create(name: str = "dummy"):
    name = (name or "dummy").lower()
    if name == "dummy":
        return DummyTranscriber()
    elif name == "faster_whisper":
        raise RuntimeError(
            "Faster-Whisper backend not yet configured. "
            "Implement emberlog/transcriber/faster_whisper.py and enable here."
        )
    else:
        raise ValueError(f"Unknown transcriber backend: {name}")
