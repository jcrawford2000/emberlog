from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from emberlog.config.config import get_settings
from emberlog.io.base import Sink, SinkResult
from emberlog.models.job import Job
from emberlog.models.transcript import Transcript
from emberlog.queue.memory import InMemoryJobQueue
from emberlog.segmentation.transmissions import (
    Transmission,
    cut_transmission,
    dispatch_text,
    load_transmissions,
)
from emberlog.state.processed_index import ProcessedIndex
from emberlog.worker import consumer
from emberlog.worker.consumer import Worker

STEM = "1795-1795388969.243_769868750.0-call_224526"

# Shape of a real trunk-recorder call JSON (trimmed to the fields we use).
SIDECAR = {
    "talkgroup": 1795,
    "call_length": 40,
    "freqList": [
        {"freq": 769868750, "time": 1795388969, "pos": 0.0, "len": 12.78},
        {"freq": 769868750, "time": 1795388982, "pos": 12.78, "len": 0.54},
        {"freq": 769868750, "time": 1795388983, "pos": 13.32, "len": 13.5},
        {"freq": 769868750, "time": 1795388997, "pos": 26.82, "len": 5.4},
    ],
    "srcList": [
        {"src": 100026, "time": 1795388969, "pos": 0.0},
        {"src": -1, "time": 1795388982, "pos": 12.78},
        {"src": 100026, "time": 1795388983, "pos": 13.32},
        {"src": 100139, "time": 1795388997, "pos": 26.82},
    ],
}

# What the backend "hears" for each transmission (by index).
TX_TEXT = {
    1: "Engine 706, K-Deck 9, Ill person, 25516 West Magnolia Street, Engine 706, K-Deck 9.",
    2: "",  # 0.54 s key-up: must be skipped before transcription
    3: "Engine 572, K-Deck 7, Snake removal, 500 West Reading Drive, Engine 572, K-Deck 7.",
    4: "Engine 40, you're clearing on channel 1. Please switch over to your channel.",
}


def test_load_transmissions(tmp_path: Path) -> None:
    f = tmp_path / f"{STEM}.json"
    f.write_text(json.dumps(SIDECAR))
    txs = load_transmissions(f)
    assert txs == [
        Transmission(1, 0.0, 12.78, 100026, 1795388969),
        Transmission(2, 12.78, 0.54, -1, 1795388982),
        Transmission(3, 13.32, 13.5, 100026, 1795388983),
        Transmission(4, 26.82, 5.4, 100139, 1795388997),
    ]


@pytest.mark.parametrize(
    "content",
    [None, "not json", json.dumps({"freqList": []}), json.dumps({"freqList": [{"pos": 0}]})],
)
def test_load_transmissions_unusable(tmp_path: Path, content: str | None) -> None:
    f = tmp_path / "x.json"
    if content is not None:
        f.write_text(content)
    assert load_transmissions(f) is None


@pytest.mark.parametrize(
    "text,expected",
    [
        (TX_TEXT[1], TX_TEXT[1]),
        (TX_TEXT[4], None),
        ("1630 hours, Phoenix Fire Regional Dispatch.", None),
        ("", None),
        # Real whisper.cpp output for dispatches whose channel came out loosely
        (
            "Rest Hunter course: Engine 55. Fire to A-10.",
            "Rest Hunter course: Engine 55. Fire to A-10.",
        ),
        (
            "Engine 331 and Medic 331, K-Deck. Code: 13091, Waker Boulevard. Engine 31 and Medic 331, K-Deck.",
            "Engine 331 and Medic 331, K-Deck. Code: 13091, Waker Boulevard. Engine 31 and Medic 331, K-Deck.",
        ),
        ("Engine 19, you can stay in service.", None),
        (
            "Engine 151, HazMat 157, Fire Channel Way 6, Carbon Monoxide Alarm Indication.",
            "Engine 151, HazMat 157, Fire Channel Way 6, Carbon Monoxide Alarm Indication.",
        ),
        ("Engine 40, you're clearing on channel 1. Please switch to your channel.", None),
        (
            (
                "Engine 302, you're on channel 1 if you could go to your trail channel. "
                "Engine 302, you're on channel 1 if you could go to K-6."
            ),
            None,
        ),
        ("If you're clearing on channel 1, if you can go over to K-7, please. Thank you.", None),
        ("Clearing on K-1s, switch over to K-8.", None),
        (
            "Engine 38 and Ladder 43. Fire Channel A8. Dryer fire.",
            "Engine 38 and Ladder 43. Fire Channel A8. Dryer fire.",
        ),
        # Channels that only read as K-Deck after the region's channel corrections
        (
            "Engine 31, K-7. Injured person: 15046, North 54th Street. Engine 31, K-7.",
            "Engine 31, K-7. Injured person: 15046, North 54th Street. Engine 31, K-7.",
        ),
        (
            "N-603, Rescue 602, Deck 7, Seizure, North 80th Street, Engine 603, Deck 7.",
            "N-603, Rescue 602, Deck 7, Seizure, North 80th Street, Engine 603, Deck 7.",
        ),
    ],
)
def test_dispatch_text(text: str, expected: str | None) -> None:
    assert dispatch_text(text) == expected


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_cut_transmission(tmp_path: Path) -> None:
    src = tmp_path / f"{STEM}.wav"
    subprocess.run(
        ["ffmpeg", "-f", "lavfi", "-i", "sine=d=6", "-ar", "8000", str(src)],
        capture_output=True,
        check=True,
    )
    out = cut_transmission(src, Transmission(2, 1.5, 2.0), tmp_path)
    assert out.name == f"{STEM}-tx2.wav"
    dur = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert abs(float(dur) - 2.0) < 0.1


class PerTransmissionTranscriber:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def transcribe(self, path: Path) -> Transcript:
        self.calls.append(path.name)
        if "-tx" in path.stem:
            text = TX_TEXT[int(path.stem.rsplit("-tx", 1)[1])]
        else:  # whole-call transcription (text splitter fallback)
            text = TX_TEXT[1] + " " + TX_TEXT[3]
        return Transcript(audio_path=path, text=text, start=0.0, end=12.0)


class RecordingSink(Sink):
    def __init__(self) -> None:
        self.incidents: list[dict] = []

    async def process(self, *, transcript, incident, audio_path, out_dir, context=None):
        self.incidents.append(incident)
        return SinkResult(ok=True)


@pytest.fixture
def transmissions_mode(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "split_mode", "transmissions")
    monkeypatch.setattr(s, "sidecar_wait_s", 0.0)

    def fake_cut(audio: Path, tx: Transmission, out_dir=None) -> Path:
        d = Path(audio).parent / f".cut-{tx.index}"
        d.mkdir()
        out = d / f"{Path(audio).stem}-tx{tx.index}.wav"
        out.write_bytes(b"RIFFcut")
        return out

    monkeypatch.setattr(consumer, "cut_transmission", fake_cut)


def _setup(tmp_path: Path, with_sidecar: bool):
    inbox, processed = tmp_path / "inbox", tmp_path / "processed"
    wav = inbox / "2026" / "11" / "22" / f"{STEM}.wav"
    wav.parent.mkdir(parents=True)
    wav.write_bytes(b"RIFFfake")
    if with_sidecar:
        wav.with_suffix(".json").write_text(json.dumps(SIDECAR))
    idx = ProcessedIndex(tmp_path / "state.sqlite", inbox_root=inbox, processed_root=processed)
    sink, tr = RecordingSink(), PerTransmissionTranscriber()
    worker = Worker(InMemoryJobQueue(), "T", transcriber=tr, sink=sink, idx=idx)
    return worker, sink, tr, wav, processed / wav.relative_to(inbox)


def test_one_dispatch_per_console_transmission(tmp_path: Path, transmissions_mode) -> None:
    worker, sink, tr, wav, moved = _setup(tmp_path, with_sidecar=True)

    asyncio.run(worker.process(Job(path=wav)))

    # tx2 is too short to transcribe; tx4 is transcribed but isn't a dispatch.
    assert tr.calls == [f"{STEM}-tx1.wav", f"{STEM}-tx3.wav", f"{STEM}-tx4.wav"]
    assert [d["original_text"] for d in sink.incidents] == [TX_TEXT[1], TX_TEXT[3]]
    assert [d["units"] for d in sink.incidents] == [["Engine 706"], ["Engine 572"]]
    assert [d["dispatch_index"] for d in sink.incidents] == [1, 2]
    assert {d["dispatch_count"] for d in sink.incidents} == {2}
    assert {d["split_mode"] for d in sink.incidents} == {"transmissions"}
    assert [d["transmission"]["index"] for d in sink.incidents] == [1, 3]
    assert sink.incidents[1]["transmission"]["src"] == 100026
    assert sink.incidents[1]["dispatched_at"] == datetime.fromtimestamp(1795388983)
    # Audio and sidecar both move to processed/; no temp cuts are left behind.
    assert not wav.exists() and moved.exists()
    assert not wav.with_suffix(".json").exists() and moved.with_suffix(".json").exists()
    assert not list(wav.parent.glob(".cut-*"))


def test_falls_back_to_text_splitter_without_sidecar(tmp_path: Path, transmissions_mode) -> None:
    worker, sink, tr, wav, moved = _setup(tmp_path, with_sidecar=False)

    asyncio.run(worker.process(Job(path=wav)))

    assert tr.calls == [f"{STEM}.wav"]
    assert len(sink.incidents) == 2
    assert {d["split_mode"] for d in sink.incidents} == {"text"}
    assert "transmission" not in sink.incidents[0]
    assert moved.exists()


def test_text_mode_ignores_sidecar(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "split_mode", "text")
    worker, sink, tr, wav, moved = _setup(tmp_path, with_sidecar=True)

    asyncio.run(worker.process(Job(path=wav)))

    assert tr.calls == [f"{STEM}.wav"]
    assert {d["split_mode"] for d in sink.incidents} == {"text"}
    # The sidecar still travels with the audio.
    assert moved.with_suffix(".json").exists()
