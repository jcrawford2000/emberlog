from __future__ import annotations

import asyncio
from pathlib import Path

from emberlog.io.base import Sink, SinkResult
from emberlog.models.job import Job
from emberlog.models.transcript import Transcript
from emberlog.queue.memory import InMemoryJobQueue
from emberlog.state.processed_index import ProcessedIndex
from emberlog.worker.consumer import Worker

THREE_DISPATCHES = (
    "Engine 154. K-Deck 6. Assault. 1234 West Main Street. Engine 154. K-Deck 6. "
    "Rescue 12. K-Deck 8. Fall injury. 500 East Camelback Road. Rescue 12. K-Deck 8. "
    "Ladder 4. K-Deck 9. Ill person. 77 North 7th Avenue. Ladder 4. K-Deck 9."
)


class FakeTranscriber:
    def __init__(self, text: str):
        self.text = text

    async def transcribe(self, path: Path) -> Transcript:
        return Transcript(audio_path=path, text=self.text, start=0.0, end=40.0)


class RecordingSink(Sink):
    def __init__(self):
        self.incidents: list[dict] = []

    async def process(self, *, transcript, incident, audio_path, out_dir, context=None):
        self.incidents.append(incident)
        return SinkResult(ok=True)


def _setup(tmp_path: Path, text: str):
    inbox, processed = tmp_path / "inbox", tmp_path / "processed"
    wav = inbox / "2026" / "11" / "22" / "1795-1795387110.805_769868750.0-call_1.wav"
    wav.parent.mkdir(parents=True)
    wav.write_bytes(b"RIFFfake")
    idx = ProcessedIndex(tmp_path / "state.sqlite", inbox_root=inbox, processed_root=processed)
    sink = RecordingSink()
    worker = Worker(InMemoryJobQueue(), "T", transcriber=FakeTranscriber(text), sink=sink, idx=idx)
    return worker, sink, wav, processed / wav.relative_to(inbox)


def test_all_dispatches_written_then_audio_moved_once(tmp_path: Path) -> None:
    worker, sink, wav, moved = _setup(tmp_path, THREE_DISPATCHES)

    asyncio.run(worker.process(Job(path=wav)))

    assert [d["dispatch_index"] for d in sink.incidents] == [1, 2, 3]
    assert {d["dispatch_count"] for d in sink.incidents} == {3}
    assert not wav.exists()
    assert moved.exists()


def test_no_dispatches_leaves_audio_in_inbox(tmp_path: Path) -> None:
    worker, sink, wav, moved = _setup(tmp_path, "")

    asyncio.run(worker.process(Job(path=wav)))

    assert sink.incidents == []
    assert wav.exists()
    assert not moved.exists()
