"""Abstract queue interface for Ember Log.

Defines the minimal asynchronous interface consumed by workers and producers.
"""

import abc

from emberlog.models.job import Job


class JobQueue(abc.ABC):
    """Abstract base class for an async job queue."""

    @abc.abstractmethod
    async def put(self, job: Job) -> None:
        """Enqueue a job (awaits if the queue is full)."""

    @abc.abstractmethod
    async def get(self) -> Job:
        """Dequeue the next job (awaits if the queue is empty)."""

    @abc.abstractmethod
    def task_done(self) -> None:
        """Signal that the most recently gotten job has been processed."""

    @abc.abstractmethod
    def qsize(self) -> int:
        """Return the approximate current queue size."""

    @abc.abstractmethod
    async def join(self) -> None:
        """Block until all items in the queue have been processed."""
