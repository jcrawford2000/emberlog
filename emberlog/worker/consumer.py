"""Queue consumer (worker) that runs the transcriber.

Each worker pulls Jobs from the queue, runs the configured transcriber
(Dummy for now), and writes the result into the outbox as JSON.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from emberlog.config.config import get_settings
from emberlog.models.job import Job
from emberlog.queue.types import JobQueue
from emberlog.state.processed_index import ProcessedIndex
from emberlog.transcriber import factory
from emberlog.utils.logger import get_logger

settings = get_settings()
log = get_logger("Worker", settings.log_level)


class Worker:
    """Asynchronous queue consumer that processes audio jobs."""

    def __init__(self, q: JobQueue, name: str):
        """Create a worker bound to a queue.

        Args:
            q: The shared job queue.
            name: A human-friendly worker name for logging.
        """
        self.q = q
        self.name = name
        self.transcriber = factory.from_settings(settings)
        log.debug(f"Worker[{self.name}] Initializing")
        self.idx = ProcessedIndex(Path(settings.outbox_dir) / ".state")

    async def run(self) -> None:
        """Continuously consume jobs and process them until cancelled."""
        log.debug(f"Worker[{self.name}] Started")
        while True:
            job: Job = await self.q.get()
            try:
                log.debug(f"Worker[{self.name}] Processing Job")
                await self.process(job)
            except Exception as e:  # pylint: disable=broad-except
                job.attempts += 1
                log.exception(
                    "[%s] Job %s failed (%s/%s): %s",
                    self.name,
                    job.id,
                    job.attempts,
                    job.max_attempts,
                    e,
                )
                if job.attempts < job.max_attempts:
                    log.warning(f"Worker[{self.name}] Sleeping")
                    await asyncio.sleep(job.attempts**2)  # simple backoff
                    log.warning(
                        f"Worker[{self.name}] Retrying [{job.attempts}/{job.max_attempts}]"
                    )
                    await self.q.put(job)
            finally:
                self.q.task_done()

    async def process(self, job: Job) -> None:
        """Run the transcriber and write output to the outbox."""
        p: Path = job.path
        log.info(f"[{self.name}] Transcribing: {p}")
        transcript = await self.transcriber.transcribe(p)
        log.debug(f"Transcript:{transcript}")
        out = Path(settings.outbox_dir)
        out.mkdir(parents=True, exist_ok=True)
        out_file = out / (p.stem + ".json")

        # Pydantic v2 model_dump; support plain dicts as well.
        data = (
            transcript.model_dump(mode="json")
            if hasattr(transcript, "model_dump")
            else transcript
        )

        out_file.write_text(
            (
                data
                if isinstance(data, str)
                else __import__("json").dumps(data, indent=2)
            ),
            encoding="utf-8",
        )
        self.idx.mark_processed(p)
        log.info(f"[{self.name}] Wrote {out_file}")
