from __future__ import annotations

import json
from pathlib import Path

import pytest

from emberlog.io.json_sink import JsonFileSink
from emberlog.io.local_sink import LocalSink


@pytest.mark.asyncio
async def test_json_sink_accepts_string_transcript(tmp_path: Path) -> None:
    sink = JsonFileSink(LocalSink(tmp_path), naming="{stem}.json")
    audio_path = Path("1795-1-call.wav")
    res = await sink.process(
        transcript="cleaned transcript text",
        incident={"channel": "K-Deck 1"},
        audio_path=audio_path,
        out_dir=Path("ignored"),
    )
    assert res.ok is True
    assert res.out_path is not None
    assert res.extra["cleaned_text"] == "cleaned transcript text"

    payload = json.loads(res.out_path.read_text(encoding="utf-8"))
    assert payload["transcript"] == "cleaned transcript text"
    assert payload["audio_path"].endswith("1795-1-call.wav")
