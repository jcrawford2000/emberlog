# emberlog/sinks/composite.py
from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

from .base import Sink, SinkResult


class CompositeSink(Sink):

    def __init__(self, sinks: Iterable[Sink]):
        self.sinks = list(sinks)
        self.logger = logging.getLogger("emberlog.io.composite")

    async def process(
        self, *, transcript, incident, audio_path: Path, out_dir: Path, context=None
    ) -> SinkResult:
        ctx: dict = dict(context or {})
        last_res: SinkResult | None = None
        errors: list[dict] = []
        any_ok = False
        self.logger.debug(
            "Processing:\n\ttranscript:%s\n\tincident:%s\n\taudio_path:%s\n\tout_dir:%s\n\tcontext:%s",
            transcript,
            incident,
            audio_path,
            out_dir,
            context,
        )
        for s in self.sinks:
            try:
                res = await s.process(
                    transcript=transcript,
                    incident=incident,
                    audio_path=audio_path,
                    out_dir=out_dir,
                    context=ctx,
                )
            except Exception as exc:  # pylint: disable=broad-except
                self.logger.exception("Sink %s failed", s.__class__.__name__)
                errors.append(
                    {"sink": s.__class__.__name__, "reason": str(exc) or "exception"}
                )
                continue

            last_res = res
            if res.ok:
                any_ok = True
                # Merge new context for downstream sinks
                if res.out_path:
                    ctx["out_path"] = res.out_path
                if res.extra:
                    ctx.update(res.extra)
            else:
                errors.append(
                    {
                        "sink": s.__class__.__name__,
                        "reason": res.extra.get("reason") if res.extra else "failed",
                    }
                )

        extra = dict(ctx)
        if errors:
            extra["sink_errors"] = errors

        # ok when at least one sink succeeded, or when there were no sinks.
        return SinkResult(ok=any_ok or not self.sinks, out_path=ctx.get("out_path"), extra=extra)
