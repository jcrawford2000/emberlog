# emberlog/transcriber/faster_whisper.py
from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from faster_whisper import WhisperModel

from emberlog.models import Transcript

logger = logging.getLogger("emberlog.transcriber.FasterWhisperTranscriber")


def _bool_env(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.lower() in ("1", "true", "yes", "y", "on")


@dataclass
class WhisperConfig:
    model_name: str = os.getenv("WHISPER_MODEL", "medium.en")
    device: str = os.getenv("WHISPER_DEVICE", "cuda")  # "cuda" | "cpu"
    compute_type: str = os.getenv(
        "WHISPER_COMPUTE_TYPE", "float16"
    )  # "float16" on GPU, "int8" or "float32" as needed
    vad_filter: bool = _bool_env("WHISPER_VAD_FILTER", True)
    vad_parameters: dict[str, object] = json.loads(
        os.getenv("WHISPER_VAD_PARAMETERS", "{'min_silence_duration_ms': 250}")
    )
    beam_size: int = int(os.getenv("WHISPER_BEAM_SIZE", "5"))
    language: Optional[str] = os.getenv("WHISPER_LANGUAGE")  # e.g., "en"
    best_of: int = int(os.getenv("WHISPER_BEST_OF", "8"))
    temperature: float = float(os.getenv("WHISPER_TEMPERATURE", "0.0"))
    initial_prompt: str = os.getenv(
        "WHISPER_INITIAL_PROMPT",
        "Phoenix metro fire dispatch. Terms: K-Deck, Battalion, Engine, Ladder, Ladder Tender, Rescue, Medic, HazMat. Street names: Civic Center Plaza, Watson, Yuma, Buckeye. Spell out channels like 'K-Deck 10'.",
    )
    no_speech_threshold: float = float(os.getenv("WHISPER_NO_SPEECH_THRESHOLD", "0.3"))
    log_prob_threshold: float = float(os.getenv("WHISPER_LOG_PROB_THRESHOLD", "-1.2"))
    compression_ratio_threshold: float = float(
        os.getenv("WHISPER_COMPRESSION_RATIO_THRESHOLD", "2.8")
    )


class FasterWhisperTranscriber:
    """
    Async Emberlog transcriber using faster-whisper.
    Implements: async def transcribe(path: Path) -> Transcript
    """

    def __init__(self, cfg: Optional[WhisperConfig] = None):
        self.cfg = cfg or WhisperConfig()
        logger.info(
            f"Loading Whisper model: {self.cfg.model_name} "
            f"(device={self.cfg.device}, compute_type={self.cfg.compute_type})"
        )
        # Model is threadsafe to call from a worker thread per faster-whisper docs.
        self.model = WhisperModel(
            self.cfg.model_name,
            device=self.cfg.device,
            compute_type=self.cfg.compute_type,
        )

    async def transcribe(self, path: Path) -> Transcript:
        # Offload CPU/GPU-bound work to a thread to avoid blocking the event loop.
        return await asyncio.to_thread(self._do_transcribe, Path(path))

    def _do_transcribe(self, path: Path) -> Transcript:
        audio_path = str(path)
        logger.info(f"Transcribing audio: {audio_path}")

        segments_iter, info = self.model.transcribe(
            audio_path,
            vad_filter=self.cfg.vad_filter,
            vad_parameters=self.cfg.vad_parameters,
            beam_size=self.cfg.beam_size,
            best_of=self.cfg.best_of,
            initial_prompt=self.cfg.initial_prompt,
            condition_on_previous_text=False,  # short one-shot clips do better
            temperature=self.cfg.temperature,  # deterministic
            no_speech_threshold=self.cfg.no_speech_threshold,  # keep short headers
            log_prob_threshold=self.cfg.log_prob_threshold,  # don’t prune too aggressively
            compression_ratio_threshold=self.cfg.compression_ratio_threshold,  # avoid over-pruning
        )

        seg_texts: List[str] = []
        start: Optional[float] = None
        end: Optional[float] = None

        for seg in segments_iter:
            # seg.text includes a leading space; normalize
            text_piece = (seg.text or "").strip()
            if text_piece:
                seg_texts.append(text_piece)
            if start is None:
                start = float(seg.start) if seg.start is not None else 0.0
            if seg.end is not None:
                end = float(seg.end)

        text = " ".join(seg_texts).strip()
        duration_s = (
            float(getattr(info, "duration", 0.0))
            if getattr(info, "duration", None) is not None
            else ((end or 0.0) - (start or 0.0))
        )
        created_at = datetime.now(timezone.utc)

        # Build your Transcript. If your dataclass lacks created_at/segments, this still works.
        try:
            t = Transcript(
                duration_s=duration_s or 0.0,
                start=start or 0.0,
                end=end or 0.0,
                language=(getattr(info, "language", None) or self.cfg.language or "en"),
                audio_path=path,
                text=text,
            )
            # Optional convenience fields if present on your model:
            if hasattr(t, "created_at") and getattr(t, "created_at") is None:
                setattr(t, "created_at", created_at)
            if hasattr(t, "segments") and getattr(t, "segments") is None:
                # Store lightweight segments if you choose later. For now, skip to keep files smaller.
                setattr(t, "segments", None)
            return t
        except TypeError:
            # Older/strict Transcript signature
            return Transcript(
                duration_s=duration_s or 0.0,
                start=start or 0.0,
                end=end or 0.0,
                language=(getattr(info, "language", None) or self.cfg.language or "en"),
                audio_path=path,
                text=text,
            )
