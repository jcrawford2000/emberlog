"""Queue consumer (worker) that runs the transcriber.

Each worker pulls Jobs from the queue, runs the configured transcriber
(Dummy for now), and writes the result into the outbox as JSON.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from emberlog.cleaning.cleaner import clean_transcript
from emberlog.config.config import get_settings
from emberlog.io.base import Sink
from emberlog.io.composite import CompositeSink
from emberlog.io.json_sink import JsonFileSink
from emberlog.io.ledger_sink import LedgerSink
from emberlog.io.local_sink import LocalSink
from emberlog.models.job import Job
from emberlog.models.transcript import Transcript
from emberlog.queue.types import JobQueue
from emberlog.segmentation.splitter import Segment as Seg
from emberlog.segmentation.splitter import split_transcript
from emberlog.segmentation.transmissions import (
    cut_transmission,
    dispatch_text,
    load_transmissions,
    sidecar_path,
)
from emberlog.state.processed_index import ProcessedIndex
from emberlog.transcriber import factory
from emberlog.transcriber.base import Transcriber
from emberlog.versioning import get_app_version


class Worker:
    """Asynchronous queue consumer that processes audio jobs."""

    def __init__(
        self,
        q: JobQueue,
        name: str,
        *,
        transcriber: Optional[Transcriber] = None,
        sink: Optional[Sink] = None,
        idx: Optional[ProcessedIndex] = None,
        include_api_sink: bool | None = None,
    ):
        """Create a worker bound to a queue.

        Args:
            q: The shared job queue.
            name: A human-friendly worker name for logging.
        """
        settings = get_settings()
        self.settings = settings
        self.logger = logging.getLogger("emberlog.worker.Worker")
        if sink is None:
            local_sink = LocalSink(settings.outbox_dir)
            json_sink = JsonFileSink(local_sink, naming="{stem}.json")
            ledger_sink = LedgerSink()
            sinks = [json_sink, ledger_sink]
            if include_api_sink is None:
                include_api_sink = settings.api_sink_enabled
            if include_api_sink:
                from emberlog.io.api_sink import ApiSink

                sinks.append(ApiSink())
            else:
                self.logger.warning("API sink disabled; writing outbox and ledger only")
            self.sink = CompositeSink(sinks)
        else:
            self.sink = sink

        self.q = q
        self.name = name
        self.transcriber = transcriber or factory.from_settings(settings)
        self.logger.debug(f"Worker[{self.name}] Initializing")
        self.idx = idx or ProcessedIndex(
            Path(settings.outbox_dir) / ".state",
            inbox_root=Path(settings.inbox_dir),
            processed_root=Path("/data/emberlog/processed"),
        )

    async def run(self) -> None:
        """Continuously consume jobs and process them until cancelled."""
        self.logger.debug(f"Worker[{self.name}] Started")
        while True:
            job: Job = await self.q.get()
            try:
                self.logger.debug(f"Worker[{self.name}] Processing Job")
                await self.process(job)
            except Exception as e:  # pylint: disable=broad-except
                job.attempts += 1
                self.logger.exception(
                    "[%s] Job %s failed (%s/%s): %s",
                    self.name,
                    job.id,
                    job.attempts,
                    job.max_attempts,
                    e,
                )
                if job.attempts < job.max_attempts:
                    self.logger.warning(f"Worker[{self.name}] Sleeping")
                    await asyncio.sleep(job.attempts**2)  # simple backoff
                    self.logger.warning(
                        f"Worker[{self.name}] Retrying [{job.attempts}/{job.max_attempts}]"
                    )
                    await self.q.put(job)
            finally:
                self.q.task_done()

    async def process(self, job: Job) -> None:
        """Transcribe one call, split it into dispatches and write each one."""
        p: Path = job.path
        pieces: list[_Piece] | None = None
        if self.settings.split_mode == "transmissions":
            pieces = await self._pieces_from_transmissions(p)
        if pieces is None:
            pieces = await self._pieces_from_text(p)

        if not pieces:
            # Left in the inbox (unchanged behaviour); log so it's visible.
            self.logger.warning(
                "[%s] [%s] No dispatches found; leaving in inbox", self.name, p.stem
            )
            return

        created_at = datetime.now(timezone.utc)
        for i, piece in enumerate(pieces, start=1):
            await self._write_dispatch(p, piece, i, len(pieces), created_at)

        # Mark once, after every dispatch is written: marking moves the audio to
        # processed/, so doing it per dispatch made dispatch 2 fail and dropped 3+.
        self.idx.mark_processed(p)
        self._move_sidecar(p)

    async def _pieces_from_text(self, p: Path) -> list[_Piece]:
        """Transcribe the whole call and split on channel bookends in the text."""
        self.logger.info("[%s] [%s] Transcribing: %s", self.name, p.stem, p)
        transcript = await self.transcriber.transcribe(p)
        self.logger.debug("[%s] Transcript:%s", p.stem, transcript)
        if hasattr(transcript, "segments"):
            # STT returned a list/generator of segments
            segments = [
                Seg(start=s.start, end=s.end, text=s.text) for s in transcript.segments
            ]
        else:
            # Single blob (your dummy Transcript)
            segments = [
                Seg(
                    # Transcript fields exist but may be None (e.g. whisper.cpp
                    # returns no segments for a key-up with no speech).
                    start=float(getattr(transcript, "start", None) or 0.0),
                    end=float(
                        getattr(transcript, "end", None)
                        or getattr(transcript, "duration_s", None)
                        or 0.0
                    ),
                    text=str(transcript.text or ""),
                )
            ]
        self.logger.debug("[%s] Transcript Segments:\n\t%s", p.stem, segments)
        dispatches = split_transcript(segments, p)
        self.logger.debug("[%s] Transcript has %s dispatches", p.stem, len(dispatches))
        if not dispatches:
            self.logger.info(
                "[%s] [%s] Text splitter found no dispatches in: %r",
                self.name,
                p.stem,
                str(transcript.text or "")[:200],
            )
        language = getattr(transcript, "language", "en")
        dispatched_at = _dispatched_at_from_name(p)
        return [
            _Piece(text=d.text, dispatched_at=dispatched_at, language=language)
            for d in dispatches
        ]

    async def _pieces_from_transmissions(self, p: Path) -> list[_Piece] | None:
        """One dispatch per console transmission, using the trunk-recorder sidecar.

        Returns None when there is no usable sidecar, so the caller falls back
        to the text splitter.
        """
        sidecar = sidecar_path(p)
        txs = load_transmissions(sidecar)
        waited = 0.0
        while txs is None and waited < self.settings.sidecar_wait_s:
            await asyncio.sleep(1.0)
            waited += 1.0
            txs = load_transmissions(sidecar)
        if txs is None:
            self.logger.info(
                "[%s] [%s] No usable sidecar %s; using text splitter",
                self.name,
                p.stem,
                sidecar.name,
            )
            return None

        self.logger.info(
            "[%s] [%s] Transcribing %d transmission(s): %s",
            self.name,
            p.stem,
            len(txs),
            p,
        )
        pieces: list[_Piece] = []
        for tx in txs:
            if tx.length < self.settings.transmission_min_s:
                self.logger.debug(
                    "[%s] tx%d skipped: %.2fs < %.2fs (src %s)",
                    p.stem,
                    tx.index,
                    tx.length,
                    self.settings.transmission_min_s,
                    tx.src,
                )
                continue
            cut = await asyncio.to_thread(cut_transmission, p, tx)
            try:
                transcript = await self.transcriber.transcribe(cut)
            finally:
                cut.unlink(missing_ok=True)
                with contextlib.suppress(OSError):
                    cut.parent.rmdir()
            text = dispatch_text(str(transcript.text or ""))
            if text is None:
                self.logger.info(
                    "[%s] tx%d (src %s, %.1fs) is not a dispatch: %r",
                    p.stem,
                    tx.index,
                    tx.src,
                    tx.length,
                    str(transcript.text or "")[:200],
                )
                continue
            pieces.append(
                _Piece(
                    text=text,
                    dispatched_at=(
                        datetime.fromtimestamp(tx.time)
                        if tx.time
                        else _dispatched_at_from_name(p)
                    ),
                    language=getattr(transcript, "language", "en"),
                    transmission={
                        "index": tx.index,
                        "pos": tx.pos,
                        "len": tx.length,
                        "src": tx.src,
                    },
                )
            )
        return pieces

    async def _write_dispatch(
        self, p: Path, piece: _Piece, i: int, count: int, created_at: datetime
    ) -> None:
        self.logger.debug("[%s] Cleaning Transcript", p.stem)
        t = Transcript(
            audio_path=p,
            text=piece.text,
            language=piece.language,
            created_at=created_at,
        )
        clean = clean_transcript(t)
        self.logger.debug("[%s] Cleaner Results:%s", p.stem, clean)

        rel_dir = Path(f"{created_at.year}/{created_at.month}/{created_at.day}")
        name = f"{p.stem}-dispatch{i:02d}.json" if count > 1 else f"{p.stem}.json"
        relpath = rel_dir / name
        doc = {
            "source_audio": str(p),
            "dispatch_index": i,
            "dispatch_count": count,
            "original_text": piece.text,
            "dispatched_at": piece.dispatched_at,
            "special_call": clean.special_call,
            "units": clean.units,
            "channel": clean.channel,
            "incident_type": clean.incident_type,
            "address": clean.address,
            "cleaned_text": clean.text,
            "clean_stats": vars(clean.stats),
            "created_at": created_at,  # serialized via default=str in sink
            "language": piece.language,
            "version": (get_app_version() if "get_app_version" in globals() else None),
            "split_mode": "transmissions" if piece.transmission else "text",
        }
        if piece.transmission:
            doc["transmission"] = piece.transmission
        self.logger.debug("[%s] Payload:\n%s", p.stem, doc)
        sink_transcript = Transcript(
            audio_path=p,
            text=doc["cleaned_text"],
            language=piece.language,
            created_at=created_at,
        )
        self.logger.debug("[%s] Writing to Sink", p.stem)
        await self.sink.process(
            transcript=sink_transcript,
            incident=doc,
            audio_path=p,
            out_dir=relpath,
            context={"cleaned_text": doc["cleaned_text"]},
        )
        self.logger.info("[%s] [%s] Wrote %s", self.name, p.stem, relpath)

    def _move_sidecar(self, p: Path) -> None:
        """Move the call's sidecar JSON next to the audio in processed/."""
        sidecar = sidecar_path(p)
        if not sidecar.exists():
            return
        try:
            rel = sidecar.relative_to(self.idx.inbox_root)
        except ValueError:
            rel = Path(sidecar.name)
        dest = self.idx.processed_root / rel
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(sidecar), str(dest))
        except OSError:
            self.logger.warning("[%s] Could not move sidecar %s", p.stem, sidecar)


@dataclass
class _Piece:
    """One dispatch's text plus the metadata needed to write it."""

    text: str
    dispatched_at: datetime | None
    language: str = "en"
    transmission: dict | None = None


_TS_RE = re.compile(r"/1795-(\d+)")


def _dispatched_at_from_name(p: Path) -> datetime | None:
    """Call start time from the trunk-recorder file name (1795-<epoch>...)."""
    m = _TS_RE.search(str(p))
    return datetime.fromtimestamp(int(m.group(1))) if m else None
