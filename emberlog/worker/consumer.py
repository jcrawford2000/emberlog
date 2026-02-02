"""Queue consumer (worker) that runs the transcriber.

Each worker pulls Jobs from the queue, runs the configured transcriber
(Dummy for now), and writes the result into the outbox as JSON.
"""

from __future__ import annotations

import asyncio
import logging
import re
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
        include_api_sink: bool = True,
    ):
        """Create a worker bound to a queue.

        Args:
            q: The shared job queue.
            name: A human-friendly worker name for logging.
        """
        settings = get_settings()
        self.logger = logging.getLogger("emberlog.worker.Worker")
        if sink is None:
            local_sink = LocalSink(settings.outbox_dir)
            json_sink = JsonFileSink(local_sink, naming="{stem}.json")
            ledger_sink = LedgerSink()
            sinks = [json_sink, ledger_sink]
            if include_api_sink:
                from emberlog.io.api_sink import ApiSink

                sinks.insert(0, ApiSink())
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
        """Run the transcriber and write output to the outbox."""
        p: Path = job.path
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
                    start=float(getattr(transcript, "start", 0.0)),
                    end=float(
                        getattr(
                            transcript, "end", getattr(transcript, "duration_s", 0.0)
                        )
                    ),
                    text=str(transcript.text or ""),
                )
            ]
        self.logger.debug("[%s] Transcript Segments:\n\t%s", p.stem, segments)
        dispatches = split_transcript(segments, p)
        self.logger.debug("[%s] Transcript has %s dispatches", p.stem, len(dispatches))

        created_at = getattr(transcript, "created_at", None) or datetime.now(
            timezone.utc
        )
        # Determine Dispatched time from filename
        ts_rs = re.compile(r"\/1795-(\d+)", re.I)
        audio_path = str(p)
        dispatch_ts = ts_rs.search(audio_path)
        dispatched_at = None
        if dispatch_ts and dispatch_ts.group(1):
            ts = int(dispatch_ts.group(1))
            dispatched_at = datetime.fromtimestamp(ts)
            self.logger.debug("[%s] Call Dispatched at %s", p.stem, dispatched_at)

        written_paths = []

        for i, d in enumerate(dispatches, start=1):
            # clean = clean_transcript - TODO: Implement clean_transcript
            self.logger.debug("[%s] Cleaning Transcript", p.stem)
            t = Transcript(
                audio_path=p,
                text=d.text,
                language=transcript.language,
                created_at=transcript.created_at,
            )
            clean = clean_transcript(t)
            self.logger.debug("[%s] Cleaner Results:%s", p.stem, clean)

            rel_dir = Path(f"{created_at.year}/{created_at.month}/{created_at.day}")
            base_name = p.stem
            name = (
                f"{base_name}-dispatch{i:02d}.json"
                if len(dispatches) > 1
                else f"{base_name}.json"
            )
            relpath = rel_dir / name
            # 4) payload
            doc = {
                "source_audio": str(p),
                "dispatch_index": i,
                "dispatch_count": len(dispatches),
                "original_text": d.text,
                "dispatched_at": dispatched_at,
                "special_call": clean.special_call,
                "units": clean.units,
                "channel": clean.channel,
                "incident_type": clean.incident_type,
                "address": clean.address,
                "cleaned_text": clean.text,
                "clean_stats": vars(clean.stats),
                "created_at": created_at,  # serialized via default=str in sink
                "language": getattr(transcript, "language", "en"),
                "version": (
                    get_app_version() if "get_app_version" in globals() else None
                ),
            }
            self.logger.debug("[%s] Payload:\n%s", p.stem, doc)
            sink_transcript = Transcript(
                audio_path=p,
                text=doc["cleaned_text"],
                language=getattr(transcript, "language", "en"),
                created_at=created_at,
                start=getattr(t, "start", None),
                end=getattr(t, "end", None),
            )
            # 5) write via sink
            self.logger.debug("[%s] Writing to Sink", p.stem)
            out_path = await self.sink.process(
                transcript=sink_transcript,
                incident=doc,
                audio_path=p,
                out_dir=relpath,
                context={"cleaned_text": doc["cleaned_text"]},
            )  # write_json(relpath, doc)
            written_paths.append(out_path)
            self.idx.mark_processed(p)
            self.logger.info("[%s] [%s] Wrote %s", self.name, p.stem, relpath)
