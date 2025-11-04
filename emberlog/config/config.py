"""Configuration Class for centralized configuration (via .env file)"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Iterable

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Settings Class for centralized configuration"""

    # Directories
    inbox_dir: Path = Path("/data/emberlog/inbox")
    outbox_dir: Path = Path("/data/emberlog/outbox")

    # JSON Lines ledger file path
    ledger_path: Path = Path("/data/emberlog/ledger.jsonl")

    # File handling
    # Allow CSV via env like EMBERLOG_AUDIO_EXTENSIONS=.wav,.mp3
    audio_extensions: tuple[str, ...] = (".wav", ".mp3")
    api_base_url: str = "http://localhost:8080/api/v1"

    # Concurrency
    concurrency: int = 2
    max_workers: int = 2

    # Queueing
    queue_maxsize: int = 0  # 0 = unbounded

    # Scanning
    scan_existing_on_start: bool = True

    # Transcriber backend: "dummy" or future options
    transcriber_backend: str = "dummy"

    # Logging
    log_level: str = "INFO"

    # Whisper Settings
    whisper_mode = "fast"
    whisper_model = "large-v3"
    whisper_device = "cuda"
    whisper_compute_type = "float16"
    whisper_vad_filter = True
    whisper_vad_parameters = "{'min_silence_duration_ms': 250}"
    whisper_beam_size = 5
    whisper_language = "en"
    whisper_best_of = 8
    whisper_temperature = 0.0
    whisper_initial_prompt = "Phoenix metro fire dispatch. Terms: K-Deck, Battalion, Engine, Ladder, Ladder Tender, Rescue, Medic, HazMat. Street names: Civic Center Plaza, Watson, Yuma, Buckeye. Spell out channels like 'K-Deck 10'."
    whisper_no_speech_threshold = 0.3
    whisper_log_prob_threshold = -1.2
    whisper_compression_ratio_threshold = 2.8
    whisper_word_timestamps = False

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", env_prefix="EMBERLOG_", extra="ignore"
    )

    @field_validator("inbox_dir", "outbox_dir", "ledger_path", mode="before")
    @classmethod
    def expand_path(cls, v):
        """Field Validator for Paths"""
        return Path(v).expanduser().resolve()

    @field_validator("audio_extensions", mode="before")
    @classmethod
    def parse_exts(cls, v: Iterable[str] | str):
        if isinstance(v, str):
            # normalize CSV string, ignore spaces
            items = [s.strip().lower() for s in v.split(",") if s.strip()]
            return tuple(items) if items else (".wav", ".mp3")
        return tuple(v) if v else (".wav", ".mp3")


settings = Settings()
# Ensure Directories Exist
settings.inbox_dir.mkdir(parents=True, exist_ok=True)
settings.outbox_dir.mkdir(parents=True, exist_ok=True)
settings.ledger_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
