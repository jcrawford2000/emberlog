"""Application entry-point for the Ember Log pipeline.

Starts the directory watcher and a pool of asynchronous workers that consume
audio jobs, transcribe them, and write results. Includes clean shutdown on
SIGINT/SIGTERM and drains the queue before exiting.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import signal
import shutil
from collections.abc import Iterable
from pathlib import Path

from emberlog.config.config import get_settings
from emberlog.io.composite import CompositeSink
from emberlog.io.json_sink import JsonFileSink
from emberlog.io.ledger_sink import LedgerSink
from emberlog.io.local_sink import LocalSink
from emberlog.ledger.ledger import Ledger
from emberlog.queue.memory import InMemoryJobQueue
from emberlog.state.processed_index import ProcessedIndex
from emberlog.transcriber.stub import StubFixtureTranscriber

# from emberlog.utils.logger import get_logger
from emberlog.utils.loggersetup import configure_logging
from emberlog.versioning import get_app_version
from emberlog.watch.watcher import DirectoryWatcher, WatchConfig
from emberlog.worker.consumer import Worker

log = logging.getLogger("emberlog.app.Main")


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
    settings = get_settings()
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="emberlog")
    sub = parser.add_subparsers(dest="command")
    demo = sub.add_parser("demo", help="Run deterministic local demo and exit.")
    demo.add_argument(
        "--samples-inbox",
        type=Path,
        default=Path("samples/inbox"),
        help="Path to demo inbox wav fixtures.",
    )
    demo.add_argument(
        "--samples-transcripts",
        type=Path,
        default=Path("samples/transcripts"),
        help="Path to transcript fixture text files.",
    )
    demo.add_argument(
        "--out-root",
        type=Path,
        default=Path("out/demo"),
        help="Demo output root directory.",
    )
    demo.add_argument(
        "--with-api",
        action="store_true",
        help="Also include API sink during demo run.",
    )
    return parser


async def _run_demo(
    *,
    samples_inbox: Path,
    samples_transcripts: Path,
    out_root: Path,
    with_api: bool = False,
) -> int:
    """Run a deterministic fixture-backed pipeline once and exit."""
    samples_inbox = samples_inbox.resolve()
    samples_transcripts = samples_transcripts.resolve()
    out_root = out_root.resolve()
    run_inbox = out_root / "inbox"
    json_out = out_root / "json"
    processed_root = out_root / "processed"
    ledger_db = out_root / "ledger.sqlite"
    processed_db = out_root / "processed.sqlite"

    if run_inbox.exists():
        shutil.rmtree(run_inbox)
    run_inbox.mkdir(parents=True, exist_ok=True)
    staged_dir = run_inbox / "2025" / "1" / "1"
    staged_dir.mkdir(parents=True, exist_ok=True)
    json_out.mkdir(parents=True, exist_ok=True)
    processed_root.mkdir(parents=True, exist_ok=True)
    ledger_db.parent.mkdir(parents=True, exist_ok=True)
    for wav in sorted(samples_inbox.glob("*.wav")):
        shutil.copy2(wav, staged_dir / wav.name)

    settings = get_settings()
    exts = _exts_from_settings(settings.audio_extensions)

    q = InMemoryJobQueue()
    idx = ProcessedIndex(
        processed_db,
        inbox_root=run_inbox,
        processed_root=processed_root,
    )

    watcher = DirectoryWatcher(
        WatchConfig(inbox=run_inbox, exts=exts, scan_existing=True),
        q,
        idx=idx,
    )

    sinks = [JsonFileSink(LocalSink(json_out), naming="{stem}.json"), LedgerSink(Ledger(ledger_db))]
    if with_api:
        from emberlog.io.api_sink import ApiSink

        sinks.insert(0, ApiSink())

    worker = Worker(
        q,
        "DemoW1",
        transcriber=StubFixtureTranscriber(samples_transcripts),
        sink=CompositeSink(sinks),
        idx=idx,
        include_api_sink=with_api,
    )
    worker_task = asyncio.create_task(worker.run())
    await watcher.start()
    # Demo mode is one-shot: process startup scan only, then stop watching.
    await watcher.stop()
    await q.join()
    worker_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await worker_task
    return 0


def main(argv: list[str] | None = None) -> int:
    """Synchronous entry point for `poetry run emberlog`."""
    try:
        configure_logging()
    except Exception:
        logging.basicConfig(level=logging.INFO)
    ver = get_app_version()
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "demo":
        log.info("Ember Log %s demo mode starting", ver)
        return asyncio.run(
            _run_demo(
                samples_inbox=args.samples_inbox,
                samples_transcripts=args.samples_transcripts,
                out_root=args.out_root,
                with_api=args.with_api,
            )
        )
    log.info("Ember Log %s starting", ver)
    asyncio.run(_run())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
