"""
Eval harness bootstrap — MUST be imported before any emberlog.* module.

WHY THIS MATTERS
----------------
`emberlog.config.config` runs `Settings()` at module load, which:
  1. Calls `get_settings()` decorated with @lru_cache, freezing Settings on first import.
  2. Runs `mkdir` on `/data/emberlog/{inbox,outbox}` and the ledger path unconditionally.

Any `emberlog.*` import that transitively touches `emberlog.config.config` will trigger
these side effects with whatever env vars are set at that moment.

REQUIRED USAGE PATTERN
-----------------------
    import bootstrap                          # <-- ALWAYS FIRST
    bootstrap.setup(workspace=Path("/tmp/eval_scratch"))
    # Now safe to import any emberlog.* module.
    from emberlog.transcriber.whisper_fast import ...
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def setup(workspace: Path | None = None) -> Path:
    """
    Redirect EMBERLOG_* paths to a scratch workspace and validate prerequisites.

    Call this ONCE before importing any emberlog module. Returns the workspace path.
    """
    if workspace is None:
        workspace = Path(tempfile.mkdtemp(prefix="emberlog_eval_"))
    else:
        workspace = Path(workspace)
        workspace.mkdir(parents=True, exist_ok=True)

    scratch_inbox = workspace / "inbox"
    scratch_outbox = workspace / "outbox"
    scratch_ledger = workspace / "ledger.jsonl"

    scratch_inbox.mkdir(exist_ok=True)
    scratch_outbox.mkdir(exist_ok=True)

    # Set env vars BEFORE any emberlog import so get_settings() sees them on first call.
    os.environ.setdefault("EMBERLOG_INBOX_DIR", str(scratch_inbox))
    os.environ.setdefault("EMBERLOG_OUTBOX_DIR", str(scratch_outbox))
    os.environ.setdefault("EMBERLOG_LEDGER_PATH", str(scratch_ledger))

    _check_ffmpeg()

    return workspace


def _check_ffmpeg() -> None:
    """Fail fast with a clear message if ffmpeg is not on PATH."""
    if shutil.which("ffmpeg") is None:
        print(
            "ERROR: ffmpeg not found on PATH.\n"
            "The transcriber shells out to ffmpeg for tone-trimming before Whisper.\n"
            "Install it: sudo apt-get install ffmpeg  (or brew install ffmpeg on macOS)",
            file=sys.stderr,
        )
        sys.exit(1)


def ffmpeg_version() -> str:
    """Return ffmpeg version string for manifest logging."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        first_line = result.stdout.splitlines()[0] if result.stdout else "unknown"
        return first_line
    except Exception:
        return "unknown"
