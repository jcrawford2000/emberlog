from __future__ import annotations

import pytest

from emberlog.config.config import get_settings
from emberlog.io.api_sink import ApiSink
from emberlog.queue.memory import InMemoryJobQueue
from emberlog.transcriber.dummy import DummyTranscriber
from emberlog.worker.consumer import Worker


def _has_api_sink(worker: Worker) -> bool:
    return any(isinstance(s, ApiSink) for s in worker.sink.sinks)


@pytest.mark.parametrize("enabled", [True, False])
def test_worker_follows_api_sink_setting(monkeypatch, tmp_path, enabled: bool) -> None:
    monkeypatch.setattr(get_settings(), "api_sink_enabled", enabled)
    w = Worker(InMemoryJobQueue(), "T", transcriber=DummyTranscriber(), idx=object())
    assert _has_api_sink(w) is enabled


def test_explicit_argument_overrides_setting(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "api_sink_enabled", True)
    w = Worker(
        InMemoryJobQueue(),
        "T",
        transcriber=DummyTranscriber(),
        idx=object(),
        include_api_sink=False,
    )
    assert not _has_api_sink(w)
