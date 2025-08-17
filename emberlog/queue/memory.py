"""In-memory asyncio job queue implementation.

This is the default lightweight queue for local development and single-process
deployments. It wraps `asyncio.Queue` behind the `JobQueue` interface.
"""

import asyncio
import logging

from emberlog.config.config import get_settings
from emberlog.models.job import Job


from .types import JobQueue


class InMemoryJobQueue(JobQueue):
    """A simple, process-local async queue backed by `asyncio.Queue`."""

    def __init__(self, maxsize: int = 0):
        """Create the queue.

        Args:
            maxsize: Maximum number of items allowed in the queue. 0 = unbounded.
        """
        self.logger = logging.getLogger("emberlog.queue.InMemoryJobQueue")
        self.logger.debug(f"Creating Queue (maxsize={maxsize})")
        self._q: asyncio.Queue[Job] = asyncio.Queue(maxsize=maxsize)

    async def put(self, job: Job) -> None:
        """Enqueue a job (awaits if full)."""
        self.logger.debug(f"Adding job to queue")
        await self._q.put(job)

    async def get(self) -> Job:
        """Dequeue a job (awaits if empty)."""
        self.logger.debug("Dequeuing Job")
        return await self._q.get()

    def task_done(self) -> None:
        """Mark the last gotten job as processed."""
        self.logger.debug("Marking Task Done")
        self._q.task_done()

    def qsize(self) -> int:
        """Return the current queue size (approximate)."""
        return self._q.qsize()

    async def join(self) -> None:
        """Block until all items have been processed."""
        self.logger.debug("Queue Joined")
        await self._q.join()
