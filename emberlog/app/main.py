"""Application entry-point for the Ember Log pipeline.

Starts the directory watcher and a pool of asynchronous workers that consume
audio jobs, transcribe them, and write results. Includes clean shutdown on
SIGINT/SIGTERM and drains the queue before exiting.
"""

from __future__ import annotations

import asyncio
import signal
from collections.abc import Iterable

from emberlog.config.config import get_settings
from emberlog.queue.memory import InMemoryJobQueue
from emberlog.utils.logger import get_logger
from emberlog.versioning import get_app_version
from emberlog.watch.watcher import DirectoryWatcher, WatchConfig
from emberlog.worker.consumer import Worker

settings = get_settings()
log = get_logger("Main", settings.log_level)
ver = get_app_version()


def _exts_from_settings(raw: str | tuple[str, ...]) -> set[str]:
    """Parse a comma-separated extension string (e.g., '.wav,.mp3')."""
    if isinstance(raw, str):
        exts = [e.strip() for e in raw.split(",") if e.strip()]
    elif isinstance(raw, Iterable):
        exts = [e.strip() for e in raw if isinstance(e, str) and e.strip()]
    else:
        exts = []
    return {e.lower() if e.startswith(".") else f".{e.lower()}" for e in exts}


async def _run() -> None:
    """Main async supervisor: watcher + workers + graceful shutdown."""
    log.info("Starting main thread")
    q = InMemoryJobQueue(maxsize=settings.queue_maxsize)
    watch_cfg = WatchConfig(
        inbox=settings.inbox_dir,
        exts=_exts_from_settings(settings.audio_extensions),
        scan_existing=settings.scan_existing_on_start,
    )
    watcher = DirectoryWatcher(watch_cfg, q)
    await watcher.start()

    # Spin up workers
    workers = [Worker(q, f"W{i+1}") for i in range(settings.concurrency)]
    tasks = [asyncio.create_task(w.run()) for w in workers]

    stop_event = asyncio.Event()

    def _handle_stop(*_args) -> None:
        """Signal handler to initiate graceful shutdown."""
        if not stop_event.is_set():
            log.info("Shutdown signal received. Stopping…")
            stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_stop)
        except NotImplementedError:
            # Windows or restricted environments
            pass

    await stop_event.wait()
    await watcher.stop()
    await q.join()
    for t in tasks:
        t.cancel()
    log.info("All done, bye.")


def main() -> None:
    """Synchronous entry point for `poetry run emberlog`."""
    log.info(f"Ember Log {ver} Starting")
    asyncio.run(_run())


if __name__ == "__main__":
    main()
