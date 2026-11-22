"""Transcriber backend that calls a whisper.cpp `whisper-server` over HTTP.

The GPU work happens in the server process (e.g. whisper.cpp built with
Vulkan on an Intel Arc GPU), so this module needs no CUDA or ML dependencies.

Start the server with VAD enabled, for example:

    whisper-server -m models/ggml-large-v3.bin --host 127.0.0.1 --port 8080 \
        --vad -vm models/ggml-silero-v5.1.2.bin

Per-request decoding parameters come from the existing EMBERLOG_WHISPER_*
settings, so the faster_whisper and whisper_cpp backends share one config.
"""

from __future__ import annotations

import ast
import asyncio
import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from emberlog.config.config import get_settings
from emberlog.models import Transcript
from emberlog.transcriber.audio import trim_dispatch_tones

logger = logging.getLogger("emberlog.transcriber.WhisperCppTranscriber")

# Minimum run of consecutive words shared with the initial prompt for a
# sentence to be treated as the model echoing the prompt (a known Whisper
# failure mode on near-silent audio).
PROMPT_ECHO_NGRAM = 4


def _vad_min_silence_ms(raw: str | None) -> int:
    if raw:
        for parse in (json.loads, ast.literal_eval):
            try:
                val = parse(raw)
            except (ValueError, SyntaxError):
                continue  # not this format; try the next parser / use default
            if isinstance(val, dict) and "min_silence_duration_ms" in val:
                return int(val["min_silence_duration_ms"])
    return 250


@dataclass
class WhisperCppConfig:
    server_url: str
    timeout_s: float
    language: str
    beam_size: int
    best_of: int
    temperature: float
    initial_prompt: str
    no_speech_threshold: float
    log_prob_threshold: float
    vad: bool
    vad_min_silence_ms: int
    extra_params: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_settings(cls, settings: Any = None) -> WhisperCppConfig:
        s = settings or get_settings()
        return cls(
            server_url=s.whisper_cpp_url.rstrip("/"),
            timeout_s=s.whisper_cpp_timeout_s,
            language=s.whisper_language,
            beam_size=s.whisper_beam_size,
            best_of=s.whisper_best_of,
            temperature=s.whisper_temperature,
            initial_prompt=s.whisper_initial_prompt,
            no_speech_threshold=s.whisper_no_speech_threshold,
            log_prob_threshold=s.whisper_log_prob_threshold,
            vad=s.whisper_vad_filter,
            vad_min_silence_ms=_vad_min_silence_ms(s.whisper_vad_parameters),
        )

    def form_params(self) -> dict[str, str]:
        params = {
            "response_format": "verbose_json",
            "language": self.language,
            "temperature": str(self.temperature),
            # No temperature fallback, matching faster-whisper with temperature=0.0
            "temperature_inc": "0.0",
            "beam_size": str(self.beam_size),
            "best_of": str(self.best_of),
            "prompt": self.initial_prompt,
            "no_speech_thold": str(self.no_speech_threshold),
            "logprob_thold": str(self.log_prob_threshold),
            "vad": "true" if self.vad else "false",
            "vad_min_silence_duration_ms": str(self.vad_min_silence_ms),
        }
        params.update(self.extra_params)
        return params


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def strip_prompt_echo(text: str, prompt: str, n: int = PROMPT_ECHO_NGRAM) -> str:
    """Remove sentences that repeat a run of >= n words from the initial prompt."""
    pw = _words(prompt)
    if len(pw) < n or not text:
        return text
    prompt_grams = {tuple(pw[i : i + n]) for i in range(len(pw) - n + 1)}
    kept = []
    for sentence in re.split(r"(?<=[.!?])\s+", text.strip()):
        sw = _words(sentence)
        grams = {tuple(sw[i : i + n]) for i in range(len(sw) - n + 1)}
        if grams & prompt_grams:
            logger.warning("Dropping prompt echo from transcript: %r", sentence)
            continue
        kept.append(sentence)
    return " ".join(kept).strip()


class WhisperCppTranscriber:
    """Async Emberlog transcriber backed by whisper.cpp's whisper-server.

    Implements: async def transcribe(path: Path) -> Transcript
    """

    def __init__(
        self,
        cfg: WhisperCppConfig | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        trim: Callable[[Path], Path] = trim_dispatch_tones,
    ):
        self.cfg = cfg or WhisperCppConfig.from_settings()
        self._client = client or httpx.AsyncClient(timeout=self.cfg.timeout_s)
        self._trim = trim
        logger.info("Using whisper.cpp server at %s", self.cfg.server_url)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def transcribe(self, path: Path) -> Transcript:
        path = Path(path)
        logger.info("[%s] Transcribing audio: %s", path.stem, path)
        # ffmpeg and file I/O are blocking; keep them off the event loop.
        trimmed = await asyncio.to_thread(self._trim, path)
        try:
            audio = await asyncio.to_thread(trimmed.read_bytes)
        finally:
            trimmed.unlink(missing_ok=True)
        resp = await self._client.post(
            f"{self.cfg.server_url}/inference",
            files={"file": (trimmed.name, audio, "audio/wav")},
            data=self.cfg.form_params(),
        )

        if resp.status_code == 400:
            # whisper-server rejects clips too short to decode; that is "no speech",
            # not an error worth retrying.
            logger.warning(
                "[%s] whisper-server rejected clip (400: %s); treating as no speech",
                path.stem,
                resp.text[:200],
            )
            return Transcript(audio_path=path, text="", language=self.cfg.language)
        # Connection errors and 5xx propagate so the worker's retry logic applies.
        resp.raise_for_status()
        return self._to_transcript(path, resp.json())

    def _to_transcript(self, path: Path, data: dict[str, Any]) -> Transcript:
        segments = data.get("segments") or []
        if segments:
            # Concatenate as-is: whisper.cpp segment boundaries can fall inside a
            # word, and each segment's text already carries its own leading space
            # at word boundaries. Joining with " " would split words ("c actus").
            raw_text = "".join(s.get("text") or "" for s in segments)
        else:
            raw_text = data.get("text") or ""
        raw_text = re.sub(r"\s+", " ", raw_text)
        text = strip_prompt_echo(raw_text.strip(), self.cfg.initial_prompt)

        start = end = None
        if segments:
            start = float(segments[0].get("start") or 0.0)
            end = float(segments[-1].get("end") or 0.0)
        duration = data.get("duration")
        return Transcript(
            audio_path=path,
            text=text,
            start=start,
            end=end,
            duration_s=float(duration) if duration is not None else None,
            language=data.get("language") or self.cfg.language,
        )
