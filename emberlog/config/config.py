"""Configuration Class for centralized configuration (via .env file)"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Iterable

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="EMBERLOG_", extra="ignore"
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
