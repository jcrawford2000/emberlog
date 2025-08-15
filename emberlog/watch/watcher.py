"""Filesystem watcher that enqueues new audio files.

Uses watchdog to monitor the inbox directory (recursively). New or moved files
with configured audio extensions are enqueued only after they appear "stable"
(file size unchanged across a few checks) to avoid partial reads.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from watchdog.events import FileCreatedEvent, FileMovedEvent, FileSystemEventHandler
from watchdog.observers import Observer as WatchdogObserver

from emberlog.config.config import get_settings
from emberlog.models.job import Job
from emberlog.queue.types import JobQueue
from emberlog.utils.logger import get_logger

settings = get_settings()
log = get_logger(settings.log_level)

STABILITY_CHECK_SECS = 1.0
STABILITY_ITERATIONS = 3


def _coerce_path(p: Any) -> Path:
    """Coerce str | bytes | os.PathLike to pathlib.Path.

    Watchdog event paths are annotated as str | bytes. Path() does not accept
    bytes directly (expects str or PathLike[str]). Decode bytes using UTF‑8
    with 'surrogateescape' to preserve undecodable bytes on POSIX.
    """
    if isinstance(p, Path):
        return p
    if isinstance(p, bytes):
        return Path(p.decode("utf-8", errors="surrogateescape"))
    return Path(os.fspath(p))


@dataclass
class WatchConfig:
    """Configuration for directory watching.

    Attributes:
        inbox: Root directory to watch.
        exts: Set of lowercase file extensions to accept (e.g., {'.wav', '.mp3'}).
        scan_existing: If True, enqueue matching files found at startup.
    """

    inbox: Path
    exts: set[str]
    scan_existing: bool = True


class _Handler(FileSystemEventHandler):
    """Internal watchdog handler that forwards stable files into the queue."""

    def __init__(self, q: JobQueue, exts: set[str], loop: asyncio.AbstractEventLoop):
        """Initialize the handler.

        Args:
            q: Target job queue.
            exts: Allowed file extensions.
            loop: The main asyncio event loop to schedule coroutines on.
        """
        self.q = q
        self.exts = exts
        self.loop = loop

    def _matches(self, p: Path) -> bool:
        return (p.suffix.lower() in self.exts) and p.is_file()

    def on_created(self, event) -> None:
        if isinstance(event, FileCreatedEvent):
            p = _coerce_path(event.src_path)
            if self._matches(p):
                asyncio.run_coroutine_threadsafe(
                    _enqueue_when_stable(self.q, p), self.loop
                )

    def on_moved(self, event) -> None:
        if isinstance(event, FileMovedEvent):
            p = _coerce_path(event.dest_path)
            if self._matches(p):
                asyncio.run_coroutine_threadsafe(
                    _enqueue_when_stable(self.q, p), self.loop
                )


async def _enqueue_when_stable(q: JobQueue, path: Path) -> None:
    """Wait until file size is stable across a few checks, then enqueue."""
    try:
        last = -1
        stable_count = 0
        while stable_count < STABILITY_ITERATIONS:
            size = path.stat().st_size
            stable_count = stable_count + 1 if size == last else 0
            last = size
            await asyncio.sleep(STABILITY_CHECK_SECS)
        await q.put(Job(path=path))
    except FileNotFoundError:
        # File disappeared before we could queue it—ignore.
        return


async def scan_existing(inbox: Path, exts: set[str], q: JobQueue) -> None:
    """Scan existing files at startup and enqueue those that match."""
    for p in sorted(inbox.rglob("*")):
        if p.is_file() and p.suffix.lower() in exts:
            await _enqueue_when_stable(q, p)


class DirectoryWatcher:
    """High-level controller for starting/stopping a watchdog observer."""

    def __init__(self, cfg: WatchConfig, q: JobQueue):
        """Initialize the watcher with configuration and a queue target."""
        self.cfg = cfg
        self.q = q
        # Annotate as Optional[Observer] — Pylance thinks Observer is a variable, so we ignore the error.
        self.observer: Optional[WatchdogObserver] = None  # type: ignore

    async def start(self) -> None:
        """Start the watcher (and optionally enqueue existing files)."""
        if self.cfg.scan_existing:
            log.info(f"Scanning existing files in {self.cfg.inbox}")
            await scan_existing(self.cfg.inbox, self.cfg.exts, self.q)

        loop = asyncio.get_running_loop()
        handler = _Handler(self.q, self.cfg.exts, loop)

        # Bind to a local non-optional variable before using methods.
        obs = WatchdogObserver()
        self.observer = obs
        obs.schedule(handler, str(self.cfg.inbox), recursive=True)
        obs.start()
        log.info(f"Watching {self.cfg.inbox} for {sorted(self.cfg.exts)}")

    async def stop(self) -> None:
        """Stop the watcher and join the observer thread."""
        obs = self.observer
        if obs is not None:
            obs.stop()
            obs.join(timeout=5)
            log.info("Watcher stopped.")
            self.observer = None
