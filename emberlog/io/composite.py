# emberlog/sinks/composite.py
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .base import Sink, SinkResult


class CompositeSink(Sink):
    def __init__(self, sinks: Iterable[Sink]):
        self.sinks = list(sinks)

    async def process(
        self, *, transcript, incident, audio_path: Path, out_dir: Path, context=None
    ) -> SinkResult:
        ctx: dict = dict(context or {})
        last_res: SinkResult | None = None

        for s in self.sinks:
            res = await s.process(
                transcript=transcript,
                incident=incident,
                audio_path=audio_path,
                out_dir=out_dir,
                context=ctx,
            )
            last_res = res
            if not res.ok:
                return res
            # Merge new context for downstream sinks
            if res.out_path:
                ctx["out_path"] = res.out_path
            if res.extra:
                ctx.update(res.extra)

        return last_res or SinkResult(ok=True)
