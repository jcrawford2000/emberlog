from __future__ import annotations

from pathlib import Path

import pytest

from emberlog.io.ledger_sink import LedgerSink
from emberlog.io.composite import CompositeSink
from emberlog.ledger.ledger import Ledger
from emberlog.models.transcript import Transcript
from emberlog.io.base import SinkResult


@pytest.mark.asyncio
async def test_ledger_sink_reads_dict_incident_fields(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.sqlite")
    sink = LedgerSink(ledger)
    transcript = Transcript(audio_path=Path("x.wav"), text="cleaned", start=1.2, end=3.4)
    incident = {
        "channel": "K-Deck 9",
        "units": ["Engine 18", "Rescue 918"],
        "incident_type": "Internal bleeding",
        "address": "4135 North 27th Avenue",
    }

    res = await sink.process(
        transcript=transcript,
        incident=incident,
        audio_path=Path("audio.wav"),
        out_dir=Path("unused.json"),
        context={"out_path": Path("out.json"), "cleaned_text": "cleaned"},
    )

    assert res.ok is True
    row = ledger.get_recent(limit=1)[0]
    assert row.channel == "K-Deck 9"
    assert row.type == "Internal bleeding"
    assert row.address == "4135 North 27th Avenue"
    assert row.units_json is not None
    assert "Engine 18" in row.units_json


@pytest.mark.asyncio
async def test_ledger_sink_requires_context_fields(tmp_path: Path) -> None:
    sink = LedgerSink(Ledger(tmp_path / "ledger.sqlite"))
    res = await sink.process(
        transcript="ignored",
        incident={},
        audio_path=Path("audio.wav"),
        out_dir=Path("unused"),
        context={},
    )
    assert res.ok is False
    assert res.extra["reason"] == "ledger requires out_path and cleaned_text"


@pytest.mark.asyncio
async def test_composite_sink_runs_all_sinks_when_one_fails(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.sqlite")
    ok_sink = LedgerSink(ledger)

    class FailSink:
        async def process(self, *, transcript, incident, audio_path, out_dir, context=None):
            return SinkResult(ok=False, extra={"reason": "nope"})

    composite = CompositeSink([FailSink(), ok_sink])
    transcript = Transcript(audio_path=Path("x.wav"), text="cleaned")
    res = await composite.process(
        transcript=transcript,
        incident={"channel": "K-Deck 1"},
        audio_path=Path("audio.wav"),
        out_dir=Path("out.json"),
        context={"out_path": Path("out.json"), "cleaned_text": "cleaned"},
    )

    assert res.ok is True
    assert "sink_errors" in res.extra
    assert ledger.get_recent(limit=1)
