# emberlog/sinks/ledger_sink.py
from __future__ import annotations

from pathlib import Path
from typing import Any

from emberlog.ledger.ledger import Ledger

from .base import Sink, SinkResult


class LedgerSink(Sink):
    def __init__(self, ledger: Ledger | None = None):
        self.ledger = ledger or Ledger()

    async def process(
        self, *, transcript, incident, audio_path: Path, out_dir: Path, context=None
    ) -> SinkResult:
        ctx = context or {}
        out_path = ctx.get("out_path")
        cleaned_text = ctx.get("cleaned_text") or ""

        if out_path is None or not cleaned_text:
            return SinkResult(
                ok=False, extra={"reason": "ledger requires out_path and cleaned_text"}
            )

        def _field(obj: Any, key: str, default=None):
            if obj is None:
                return default
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        type_val = _field(incident, "incident_type")
        if type_val is None:
            type_val = _field(incident, "type")

        inserted, rowid, digest = self.ledger.insert_dispatch(
            audio_path=audio_path,
            out_path=out_path,
            started_s=getattr(transcript, "start", None),
            ended_s=getattr(transcript, "end", None),
            channel=_field(incident, "channel"),
            units=_field(incident, "units"),
            type_=type_val,
            address=_field(incident, "address"),
            cleaned_text=cleaned_text,
        )
        return SinkResult(
            ok=True, extra={"inserted": inserted, "rowid": rowid, "sha": digest}
        )
