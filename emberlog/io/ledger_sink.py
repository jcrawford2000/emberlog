# emberlog/sinks/ledger_sink.py
from __future__ import annotations

from pathlib import Path

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

        inserted, rowid, digest = self.ledger.insert_dispatch(
            audio_path=audio_path,
            out_path=out_path,
            started_s=getattr(transcript, "start", None),
            ended_s=getattr(transcript, "end", None),
            channel=getattr(incident, "channel", None) if incident else None,
            units=getattr(incident, "units", None) if incident else None,
            type_=getattr(incident, "type", None) if incident else None,
            address=getattr(incident, "address", None) if incident else None,
            cleaned_text=cleaned_text,
        )
        return SinkResult(
            ok=True, extra={"inserted": inserted, "rowid": rowid, "sha": digest}
        )
