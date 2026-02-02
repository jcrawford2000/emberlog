from __future__ import annotations

import sqlite3
import builtins
from pathlib import Path

from emberlog.app import main as app_main


def _fixture_count(transcripts_dir: Path) -> int:
    return len(list(transcripts_dir.glob("*.txt")))


def _ledger_count(db_path: Path) -> int:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute("SELECT COUNT(*) FROM dispatches")
        return int(cur.fetchone()[0])
    finally:
        conn.close()


def test_demo_mode_generates_json_and_ledger_rows(tmp_path: Path) -> None:
    samples_inbox = Path("samples/inbox").resolve()
    samples_transcripts = Path("samples/transcripts").resolve()
    out_root = tmp_path / "demo"
    expected = _fixture_count(samples_transcripts)

    rc = app_main.main(
        [
            "demo",
            "--samples-inbox",
            str(samples_inbox),
            "--samples-transcripts",
            str(samples_transcripts),
            "--out-root",
            str(out_root),
        ]
    )
    assert rc == 0

    json_files = list((out_root / "json").glob("*.json"))
    assert len(json_files) == expected
    assert _ledger_count(out_root / "ledger.sqlite") == expected


def test_demo_mode_is_idempotent(tmp_path: Path) -> None:
    samples_inbox = Path("samples/inbox").resolve()
    samples_transcripts = Path("samples/transcripts").resolve()
    out_root = tmp_path / "demo"

    first_rc = app_main.main(
        [
            "demo",
            "--samples-inbox",
            str(samples_inbox),
            "--samples-transcripts",
            str(samples_transcripts),
            "--out-root",
            str(out_root),
        ]
    )
    assert first_rc == 0
    first_count = _ledger_count(out_root / "ledger.sqlite")

    second_rc = app_main.main(
        [
            "demo",
            "--samples-inbox",
            str(samples_inbox),
            "--samples-transcripts",
            str(samples_transcripts),
            "--out-root",
            str(out_root),
        ]
    )
    assert second_rc == 0
    assert _ledger_count(out_root / "ledger.sqlite") == first_count


def test_demo_mode_does_not_construct_api_sink_by_default(
    tmp_path: Path, monkeypatch
) -> None:
    samples_inbox = Path("samples/inbox").resolve()
    samples_transcripts = Path("samples/transcripts").resolve()
    out_root = tmp_path / "demo"

    orig_import = builtins.__import__

    def _guarded_import(name, *args, **kwargs):
        if name == "emberlog.io.api_sink":
            raise AssertionError("ApiSink import should not occur in demo by default")
        return orig_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _guarded_import)
    rc = app_main.main(
        [
            "demo",
            "--samples-inbox",
            str(samples_inbox),
            "--samples-transcripts",
            str(samples_transcripts),
            "--out-root",
            str(out_root),
        ]
    )
    assert rc == 0
