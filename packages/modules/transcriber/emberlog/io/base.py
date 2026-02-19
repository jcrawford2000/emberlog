# emberlog/sinks/base.py
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, Optional, Any


@dataclass(frozen=True)
class SinkResult:
    ok: bool
    out_path: Optional[Path] = None
    # Use default_factory so the dict is never None, and never shared across instances
    extra: dict[str, Any] = field(default_factory=dict)


class Sink(Protocol):
    async def process(
        self,
        *,
        transcript: Any,
        incident: Any,
        audio_path: Path,
        out_dir: Path,
        context: dict[str, Any] | None = None,
    ) -> SinkResult: ...
