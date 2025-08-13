"""Configuration Class for centralize configuration (via .env file)"""

from __future__ import annotations

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Directories
    inbox_dir: Path = Path("/data/emberlog/inbox")
    outbox_dir: Path = Path("/data/emberlog/outbox")
    # JSON Lines ledger file path
    ledger_path: Path = Path("/data/emberlog/ledger.jsonl")

    # File handling
    audio_extension: tuple[str, ...] = (".wav", ".mp3")

    # Concurrency
    max_workers: int = 2

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
        return Path(v).expanduser().resolve()


settings = Settings()
# Ensure Directories Exist
settings.inbox_dir.mkdir(parents=True, exist_ok=True)
settings.outbox_dir.mkdir(parents=True, exist_ok=True)
settings.ledger_path.mkdir(parents=True, exist_ok=True)
