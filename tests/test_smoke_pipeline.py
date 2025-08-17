"""End-to-end smoke test for the watcher + queue + dummy transcriber."""

from __future__ import annotations

import asyncio
import contextlib
from importlib import reload
from pathlib import Path

import pytest

# Import app modules
import emberlog.config as cfg


@pytest.mark.asyncio
async def test_pipeline_smoke(tmp_path: Path, monkeypatch):
    """Spin up watcher + worker, drop a .wav file, expect a .json in outbox."""
    inbox = tmp_path / "inbox"
    outbox = tmp_path / "outbox"
    print(f"Inbox:{inbox}\nOutbox:{outbox}")
    inbox.mkdir()
    outbox.mkdir()

    # Point settings at our temp dirs
    monkeypatch.setenv("EMBERLOG_INBOX_DIR", str(inbox))
    monkeypatch.setenv("EMBERLOG_OUTBOX_DIR", str(outbox))
    monkeypatch.setenv("EMBERLOG_SCAN_EXISTING_ON_START", "true")
    monkeypatch.setenv("EMBERLOG_TRANSCRIBER_BACKEND", "dummy")
    # Optional: lower log noise
    monkeypatch.setenv("EMBERLOG_LOG_LEVEL", "DEBUG")

    # Reload settings so env vars take effect
    reload(cfg)
    from emberlog.config.config import get_settings

    settings = get_settings()
    from emberlog.queue.memory import InMemoryJobQueue
    from emberlog.watch.watcher import DirectoryWatcher, WatchConfig
    from emberlog.worker.consumer import Worker

    # In code, audio_extensions might be tuple or str. Force it here:
    try:
        # Pydantic v2 settings objects are mutable by default.
        settings.audio_extensions = (".wav",)
    except Exception:
        pass

    q = InMemoryJobQueue()

    # Build watcher and worker
    exts = {".wav"}
    watch_cfg = WatchConfig(inbox=inbox, exts=exts, scan_existing=True)
    watcher = DirectoryWatcher(watch_cfg, q)
    worker = Worker(q, "W1")

    # Create a file BEFORE watcher starts
    f = inbox / "testfile.wav"
    f.write_bytes(b"\x00\x00")  # contents don't matter for dummy backend

    # Run watcher + worker concurrently
    worker_task = asyncio.create_task(worker.run())
    await watcher.start()

    # Wait for the queue to drain; give it a small timeout cushion
    try:
        # The stability checker runs ~3 seconds; give it a bit more than that.
        await asyncio.wait_for(q.join(), timeout=10.0)
    finally:
        # Stop watcher and cancel worker cleanly
        await watcher.stop()
        worker_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await worker_task

    # Assert the outbox file exists
    out_json = outbox / "testfile.json"
    assert out_json.exists(), f"Expected output {out_json} not found"
    data = out_json.read_text(encoding="utf-8")
    assert "Test Call" in data
