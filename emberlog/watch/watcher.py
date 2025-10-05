"""Filesystem watcher that enqueues new audio files.

Uses watchdog to monitor the inbox directory (recursively). New or moved files
with configured audio extensions are enqueued only after they appear "stable"
(file size unchanged across a few checks) to avoid partial reads.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

from watchdog.events import FileCreatedEvent, FileMovedEvent, FileSystemEventHandler
from watchdog.observers import Observer as WatchdogObserver

from emberlog.config.config import get_settings
from emberlog.models.job import Job
from emberlog.queue.types import JobQueue
from emberlog.state.processed_index import ProcessedIndex

settings = get_settings()
logger = logging.getLogger("emberlog.watch.watcher")

STABILITY_CHECK_SECS = 0.25
STABILITY_ITERATIONS = 1

# Accept YYYY/M/D with NO zero padding for M/D, anywhere under inbox
DATE_DIR_RE = re.compile(
    r"^(?P<y>\d{4})/(?P<m>[1-9]|1[0-2])/(?P<d>[1-9]|[12]\d|3[01])(?:/|$)"
)


def _exts_from_settings(raw: str | tuple[str, ...]) -> set[str]:
    """Parse a comma-separated extension string (e.g., '.wav,.mp3')."""
    if isinstance(raw, str):
        exts = [e.strip() for e in raw.split(",") if e.strip()]
    elif isinstance(raw, Iterable):
        exts = [e.strip() for e in raw if isinstance(e, str) and e.strip()]
    else:
        exts = []
    return {e.lower() if e.startswith(".") else f".{e.lower()}" for e in exts}


def is_in_dated_tree(inbox: Path, file_path: Path) -> bool:
    rel = file_path.relative_to(inbox).as_posix()
    return DATE_DIR_RE.match(rel) is not None


def iter_existing_audio(inbox: Path):
    # rglob all candidate files; cheap filter via extension + regex on relative path
    for p in inbox.rglob("*"):
        if (
            p.is_file()
            and p.suffix.lower() in _exts_from_settings(settings.audio_extensions)
            and is_in_dated_tree(inbox, p)
        ):
            yield p


def _coerce_path(p: Any) -> Path:
    """Coerce str | bytes | os.PathLike to pathlib.Path.

    Watchdog event paths are annotated as str | bytes. Path() does not accept
    bytes directly (expects str or PathLike[str]). Decode bytes using UTF‑8
    with 'surrogateescape' to preserve undecodable bytes on POSIX.
    """
    if isinstance(p, Path):
        logger.debug("Already a Path Object, returning.")
        return p
    if isinstance(p, bytes):
        logger.debug("Path was a Byte Array, coercing to a Path Object")
        return Path(p.decode("utf-8", errors="surrogateescape"))
    logger.debug("Path is a String or PathLike, coercing to a Path Object")
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

    def __init__(
        self,
        q: JobQueue,
        exts: set[str],
        loop: asyncio.AbstractEventLoop,
        inbox: Path,
        idx: "ProcessedIndex",
    ):
        """Initialize the handler.

        Args:
            q: Target job queue.
            exts: Allowed file extensions.
            loop: The main asyncio event loop to schedule coroutines on.
        """
        self.q = q
        self.exts = exts
        self.loop = loop
        self.inbox = inbox
        self.idx = idx
        self.logger = logging.getLogger("emberlog.watch._Handler")

    def _matches(self, p: Path) -> bool:
        logger.debug("Checking file for processing.")
        matches = False
        if p.is_file():
            logger.debug(f"{p} is a file")
            if p.suffix.lower() in self.exts:
                logger.debug(f"{p.suffix.lower()} is a valid extension")
                if is_in_dated_tree(self.inbox, p):
                    logger.debug(f"{p} is in a dated tree.")
                    matches = True
                else:
                    logger.debug(f"{p} is not in a dated tree")
            else:
                logger.debug(f"{p.suffix.lower()} is not a valid extension")
        else:
            logger.debug(f"{p} is not a file, no match")
        return matches

    def on_created(self, event) -> None:
        if isinstance(event, FileCreatedEvent):
            self.logger.debug(f"Detected FileCreatedEvent: {event.src_path}")
            p = _coerce_path(event.src_path)
            if self._matches(p):
                logger.debug("File is valid, enqueueing.")
                asyncio.run_coroutine_threadsafe(
                    _maybe_enqueue(self.idx, self.q, p), self.loop
                )
            else:
                logger.debug("File was not valid, skipping.")

    def on_moved(self, event) -> None:
        if isinstance(event, FileMovedEvent):
            self.logger.debug(f"Detected FileMovedEvent: {event.dest_path}")
            p = _coerce_path(event.dest_path)
            if self._matches(p):
                logger.debug("File is valid, enqueueing.")
                asyncio.run_coroutine_threadsafe(
                    _maybe_enqueue(self.idx, self.q, p), self.loop
                )
            else:
                logger.debug("File was not valid, skipping.")


async def _maybe_enqueue(idx: "ProcessedIndex", q: JobQueue, path: Path) -> None:
    # Runs on the asyncio loop thread — same thread where idx was created.
    try:
        if idx.is_processed(path):
            logger.debug(f"Already processed (skip): {path}")
            return
    except Exception:
        logger.exception("ProcessedIndex check failed", stacklevel=2)
        return
    await _enqueue_when_stable(q, path)


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
        logger.debug(f"File is stable, adding to queue ({path})")
        await q.put(Job(path=path))
    except FileNotFoundError:
        # File disappeared before we could queue it—ignore.
        return


async def scan_existing(
    inbox: Path, exts: set[str], q: JobQueue, idx: "ProcessedIndex"
) -> None:
    """Scan existing files at startup and enqueue those that match."""
    scanned = enq = skipped = 0
    for p in sorted(inbox.rglob("*")):
        if p.is_file() and p.suffix.lower() in exts and is_in_dated_tree(inbox, p):
            scanned += 1
            if idx.is_processed(p):
                skipped += 1
                continue
            await _enqueue_when_stable(q, p)
            enq += 1
    logger.info(
        f"Initial scan summary: scanned={scanned} enqueued={enq} skipped={skipped}"
    )


class DirectoryWatcher:
    """High-level controller for starting/stopping a watchdog observer."""

    def __init__(self, cfg: WatchConfig, q: JobQueue):
        """Initialize the watcher with configuration and a queue target."""
        self.logger = logging.getLogger("emberlog.watch.DirectoryWatcher")
        self.logger.debug("Initializing DirectoryWatcher")
        self.cfg = cfg
        self.q = q
        # Keep state outside the inbox; outbox/.state is a simple, durable spot
        self.idx = ProcessedIndex(Path(get_settings().outbox_dir) / ".state")
        # Annotate as Optional[Observer] — Pylance thinks Observer is a variable, so we ignore the error.
        self.observer: Optional[WatchdogObserver] = None  # type: ignore

    async def start(self) -> None:
        """Start the watcher (and optionally enqueue existing files)."""
        if self.cfg.scan_existing:
            self.logger.info(f"Scanning existing files in {self.cfg.inbox}")
            await scan_existing(self.cfg.inbox, self.cfg.exts, self.q, self.idx)

        loop = asyncio.get_running_loop()
        handler = _Handler(self.q, self.cfg.exts, loop, self.cfg.inbox, self.idx)

        # Bind to a local non-optional variable before using methods.
        obs = WatchdogObserver()
        self.observer = obs
        obs.schedule(handler, str(self.cfg.inbox), recursive=True)
        obs.start()
        self.logger.info(
            f"Watching {self.cfg.inbox} (recursive) for {sorted(self.cfg.exts)}"
        )

    async def stop(self) -> None:
        """Stop the watcher and join the observer thread."""
        obs = self.observer
        if obs is not None:
            obs.stop()
            obs.join(timeout=5)
            self.logger.info("Watcher stopped.")
            self.observer = None
