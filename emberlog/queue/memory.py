"""In-memory asyncio job queue implementation.

This is the default lightweight queue for local development and single-process
deployments. It wraps `asyncio.Queue` behind the `JobQueue` interface.
"""

import asyncio
from typing import Optional
from .types import JobQueue
from emberlog.models.job import Job


class InMemoryJobQueue(JobQueue):
    """A simple, process-local async queue backed by `asyncio.Queue`."""

    def __init__(self, maxsize: int = 0):
        """Create the queue.

        Args:
            maxsize: Maximum number of items allowed in the queue. 0 = unbounded.
        """
        self._q: asyncio.Queue[Job] = asyncio.Queue(maxsize=maxsize)

    async def put(self, job: Job) -> None:
        """Enqueue a job (awaits if full)."""
        await self._q.put(job)

    async def get(self) -> Job:
        """Dequeue a job (awaits if empty)."""
        return await self._q.get()

    def task_done(self) -> None:
        """Mark the last gotten job as processed."""
        self._q.task_done()

    def qsize(self) -> int:
        """Return the current queue size (approximate)."""
        return self._q.qsize()

    async def join(self) -> None:
        """Block until all items have been processed."""
        await self._q.join()
