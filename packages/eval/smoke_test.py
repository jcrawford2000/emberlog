"""
Smoke test: scorer on corpus + copy-of-truth system_output → ~100% split, ~0 WER, ~100% fields.

Proves the diff logic is correct before any real number is trusted.
Run with:
    python smoke_test.py

No audio, GPU, or network required. Pure scorer logic only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from corpus_io import load_corpus
from scorer import score, compute_metrics, print_tables, PARSE_FIELDS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        print(f"FAIL: {msg}")
        sys.exit(1)


def _approx_eq(a: float | None, b: float, tol: float = 1.0) -> bool:
    if a is None:
        return False
    return abs(a - b) <= tol


# ---------------------------------------------------------------------------
# Pre-normalized corpus (internal format — used by existing tests)
# These bypass corpus_io.load_corpus() and feed the scorer directly.
# ---------------------------------------------------------------------------

CORPUS_INTERNAL = [
    {
        "audio_ref": "test_single",
        "audio_quality": "ok",
        "expected_dispatch_count": 1,
        "clip_transcript": "K-Deck 8 Difficulty breathing 4210 North 154th Drive Engine 12 Rescue 3 K-Deck 8",
        "dispatches": [
            {
                "dispatch_transcript": "K-Deck 8 Difficulty breathing 4210 North 154th Drive Engine 12 Rescue 3 K-Deck 8",
                "special_call": False,
                "units": ["Engine 12", "Rescue 3"],
                "channel": "K-Deck 8",
                "incident_type": "Difficulty breathing",
                "address": "4210 N 154th Dr",
            }
        ],
    },
    {
        "audio_ref": "test_multi",
        "audio_quality": "ok",
        "expected_dispatch_count": 2,
        "clip_transcript": "K-Deck 9 Heart attack 350 West Van Buren Street Engine 5 K-Deck 9 Special call K-Deck 12 Structure fire 1000 North 3rd Street Battalion 6 Engine 8 Ladder 3 K-Deck 12",
        "dispatches": [
            {
                "dispatch_transcript": "K-Deck 9 Heart attack 350 West Van Buren Street Engine 5 K-Deck 9",
                "special_call": False,
                "units": ["Engine 5"],
                "channel": "K-Deck 9",
                "incident_type": "Heart attack",
                "address": "350 W Van Buren St",
            },
            {
                "dispatch_transcript": "Special call K-Deck 12 Structure fire 1000 North 3rd Street Battalion 6 Engine 8 Ladder 3 K-Deck 12",
                "special_call": True,
                "units": ["Battalion 6", "Engine 8", "Ladder 3"],
                "channel": "K-Deck 12",
                "incident_type": "Structure fire",
                "address": "1000 N 3rd St",
            },
        ],
    },
    {
        "audio_ref": "test_unintelligible",
        "audio_quality": "unintelligible",
        "expected_dispatch_count": 1,
        "clip_transcript": "inaudible",
        "dispatches": [
            {
                "dispatch_transcript": "inaudible",
                "special_call": False,
                "units": [],
                "channel": None,
                "incident_type": None,
                "address": None,
            }
        ],
    },
]


def _make_truth_output(mode: str = "end-to-end", strategy: str = "text") -> list[dict]:
    """Mirror corpus truth into system_output format (perfect run)."""
    results = []
    for rec in CORPUS_INTERNAL:
        dispatches_out = []
        for d in rec["dispatches"]:
            dispatches_out.append(
                {
                    "dispatch_text": d["dispatch_transcript"],
                    "transcript_text": d["dispatch_transcript"],
                    "special_call": d["special_call"],
                    "units": d["units"],
                    "channel": d["channel"],
                    "incident_type": d["incident_type"],
                    "address": d["address"],
                }
            )
        results.append(
            {
                "audio_ref": rec["audio_ref"],
                "mode": mode,
                "splitter_strategy": strategy if mode != "parser-isolated" else None,
                "produced_dispatch_count": rec["expected_dispatch_count"],
                "run_transcript": rec["clip_transcript"],
                "tone_runs": None,
                "dispatches": dispatches_out,
            }
        )
    return results


def _make_bad_output() -> list[dict]:
    """System output with deliberate errors for negative testing."""
    results = _make_truth_output()
    # test_single: wrong dispatch count (under-split)
    results[0]["produced_dispatch_count"] = 0
    results[0]["dispatches"] = []
    # test_multi: wrong channel + wrong units on dispatch 0
    results[1]["dispatches"][0]["channel"] = "K-Deck 5"
    results[1]["dispatches"][0]["units"] = []
    return results


# ---------------------------------------------------------------------------
# Test: perfect run → ~100% everywhere
# ---------------------------------------------------------------------------


def test_perfect_run() -> None:
    print("=== smoke test: perfect run ===")
    truth_output = _make_truth_output()
    split_results, clip_wer_results, dispatch_results, n_skipped = score(
        CORPUS_INTERNAL, truth_output
    )
    metrics = compute_metrics(split_results, clip_wer_results, dispatch_results, n_skipped)
    print_tables(metrics)

    sp = metrics["splitting"]
    tr = metrics["transcription"]
    pa = metrics["parsing"]

    _assert(sp["correct_pct"] == 100.0, f"splitting should be 100% but got {sp['correct_pct']}")
    _assert(sp["under"] == 0, f"under-split should be 0 but got {sp['under']}")
    _assert(sp["over"] == 0, f"over-split should be 0 but got {sp['over']}")

    # WER is per-clip: identical run_transcript → 0
    _assert(
        _approx_eq(tr["headline_wer"], 0.0, tol=0.1),
        f"headline WER should be ~0 but got {tr['headline_wer']}",
    )
    _assert(tr["unintelligible_clips"] == 1, "should have 1 unintelligible clip")

    # All parse fields should be 100%
    for fname in PARSE_FIELDS:
        val = pa["fields"].get(fname)
        _assert(
            _approx_eq(val, 100.0, tol=0.1),
            f"field {fname} should be ~100% but got {val}",
        )

    _assert(n_skipped == 0, f"should have 0 skipped but got {n_skipped}")
    print("PASS: perfect run\n")


# ---------------------------------------------------------------------------
# Test: bad run → splitting and field errors detected
# ---------------------------------------------------------------------------


def test_bad_run() -> None:
    print("=== smoke test: bad run (deliberate errors) ===")
    bad_output = _make_bad_output()
    split_results, clip_wer_results, dispatch_results, n_skipped = score(
        CORPUS_INTERNAL, bad_output
    )
    metrics = compute_metrics(split_results, clip_wer_results, dispatch_results, n_skipped)
    print_tables(metrics)

    sp = metrics["splitting"]
    pa = metrics["parsing"]

    _assert(sp["under"] >= 1, f"should have under-split >= 1 but got {sp['under']}")
    _assert(sp["correct_pct"] < 100.0, "should not be 100% splitting")

    chan_acc = pa["fields"].get("channel")
    _assert(
        chan_acc is not None and chan_acc < 100.0,
        f"channel accuracy should be <100% but got {chan_acc}",
    )
    print("PASS: bad run errors detected\n")


# ---------------------------------------------------------------------------
# Test: normalization variants
# ---------------------------------------------------------------------------


def test_normalization_variants() -> None:
    print("=== smoke test: normalization variants ===")
    from normalize import norm_channel, norm_units, norm_address, norm_incident_type, wer

    variants = ["K-Deck 8", "K-Dec 8", "KDEC8", "K Deck 8", "k deck 8"]
    normalized = [norm_channel(v) for v in variants]
    _assert(
        len(set(normalized)) == 1,
        f"channel variants should all normalize equal, got: {normalized}",
    )

    u1 = norm_units(["Engine 12", "Rescue 3"])
    u2 = norm_units(["Rescue 3", "Engine 12"])
    _assert(u1 == u2, "units should be order-insensitive")

    a1 = norm_address("4210 North 154th Drive")
    a2 = norm_address("4210 N 154th Dr")
    _assert(a1 == a2, f"address synonyms should normalize equal: {a1!r} vs {a2!r}")

    i1 = norm_incident_type("Difficulty Breathing")
    i2 = norm_incident_type("difficulty  breathing")
    _assert(i1 == i2, "incident_type normalization should be case/ws only")

    _assert(wer("hello world", "hello world") == 0.0, "identical WER should be 0")
    w = wer("hello world", "hello earth")
    _assert(_approx_eq(w * 100, 50.0), f"one sub in 2 tokens = 50% WER, got {w*100:.1f}")

    print("PASS: normalization variants\n")


# ---------------------------------------------------------------------------
# Test: parser-isolated mode
# ---------------------------------------------------------------------------


def test_parser_isolated() -> None:
    print("=== smoke test: parser-isolated mode ===")
    truth_output = _make_truth_output(mode="parser-isolated")
    split_results, clip_wer_results, dispatch_results, n_skipped = score(
        CORPUS_INTERNAL, truth_output
    )
    metrics = compute_metrics(split_results, clip_wer_results, dispatch_results, n_skipped)
    print_tables(metrics)

    _assert(
        metrics["splitting"]["total"] == 0,
        "parser-isolated should have no splitting rows",
    )
    # No clip WER (no Whisper output in parser-isolated)
    _assert(
        metrics["transcription"]["eligible_clips"] == 0,
        "parser-isolated should have no WER eligible clips",
    )
    # Fields should still be 100% (truth dispatch_transcript fed → perfect parse)
    for fname in PARSE_FIELDS:
        val = metrics["parsing"]["fields"].get(fname)
        if val is not None:
            _assert(
                _approx_eq(val, 100.0, tol=0.1),
                f"parser-isolated: field {fname} should be ~100% but got {val}",
            )
    print("PASS: parser-isolated\n")


# ---------------------------------------------------------------------------
# Test: splitter-isolated mode
# ---------------------------------------------------------------------------


def test_splitter_isolated() -> None:
    print("=== smoke test: splitter-isolated mode ===")
    truth_output = _make_truth_output(mode="splitter-isolated")
    for rec in truth_output:
        rec["dispatches"] = []
    split_results, clip_wer_results, dispatch_results, n_skipped = score(
        CORPUS_INTERNAL, truth_output
    )
    metrics = compute_metrics(split_results, clip_wer_results, dispatch_results, n_skipped)
    print_tables(metrics)

    _assert(metrics["splitting"]["total"] > 0, "splitter-isolated should score splits")
    _assert(
        metrics["transcription"]["eligible_clips"] == 0,
        "splitter-isolated should have 0 WER clips",
    )
    _assert(
        metrics["parsing"]["eligible_dispatches"] == 0,
        "splitter-isolated should have 0 parse eligible",
    )
    print("PASS: splitter-isolated\n")


# ---------------------------------------------------------------------------
# NEW: Test corpus_io.load_corpus against real {_meta, clips} shape
# ---------------------------------------------------------------------------


# (a) Single-dispatch clip with no explicit dispatch_transcript — synthesize from clip tx
CORPUS_REAL_SHAPE_SINGLE = {
    "_meta": {"generated_at": "2026-06-04T00:00:00Z"},
    "clips": [
        {
            "audio_ref": "real_single",
            "audio_filename": "real_single.wav",
            "audio_quality": "ok",
            "verified": {
                "transcript": "Engine 12 K-Deck 8 Ill Person 5100 West Camelback Road Engine 12 K-Deck 8",
                "expected_dispatch_count": 1,
                "dispatches": [
                    {
                        # No dispatch_transcript field — should be synthesized from clip transcript
                        "special_call": False,
                        "units": ["Engine 12"],
                        "channel": "K-Deck 8",
                        "incident_type": "Ill Person",
                        "address": "5100 W Camelback Rd",
                    }
                ],
                "notes": "",
            },
        }
    ],
}

# (b) Multi-dispatch clip with explicit dispatch_transcripts
CORPUS_REAL_SHAPE_MULTI = {
    "_meta": {},
    "clips": [
        {
            "audio_ref": "real_multi",
            "audio_filename": "real_multi.wav",
            "audio_quality": "ok",
            "verified": {
                "transcript": "Engine 5 K-Deck 9 Heart attack 350 West Van Buren Street Engine 5 K-Deck 9 Battalion 6 K-Deck 12 Structure fire 1000 North 3rd Street Battalion 6 K-Deck 12",
                "expected_dispatch_count": 2,
                "dispatches": [
                    {
                        "dispatch_transcript": "Engine 5 K-Deck 9 Heart attack 350 West Van Buren Street Engine 5 K-Deck 9",
                        "special_call": False,
                        "units": ["Engine 5"],
                        "channel": "K-Deck 9",
                        "incident_type": "Heart attack",
                        "address": "350 W Van Buren St",
                    },
                    {
                        "dispatch_transcript": "Battalion 6 K-Deck 12 Structure fire 1000 North 3rd Street Battalion 6 K-Deck 12",
                        "special_call": False,
                        "units": ["Battalion 6"],
                        "channel": "K-Deck 12",
                        "incident_type": "Structure fire",
                        "address": "1000 N 3rd St",
                    },
                ],
                "notes": "",
            },
        }
    ],
}

# (c) Multi-dispatch clip with one missing dispatch_transcript — excluded, not zero-scored
CORPUS_REAL_SHAPE_MISSING_DT = {
    "_meta": {},
    "clips": [
        {
            "audio_ref": "real_missing_dt",
            "audio_filename": "real_missing_dt.wav",
            "audio_quality": "ok",
            "verified": {
                "transcript": "Dispatch one text Dispatch two text",
                "expected_dispatch_count": 2,
                "dispatches": [
                    {
                        "dispatch_transcript": "Dispatch one text",
                        "special_call": False,
                        "units": [],
                        "channel": "K-Deck 8",
                        "incident_type": "Test incident",
                        "address": None,
                    },
                    {
                        # Missing dispatch_transcript — should be excluded + counted as skipped
                        "special_call": False,
                        "units": [],
                        "channel": "K-Deck 9",
                        "incident_type": "Another incident",
                        "address": None,
                    },
                ],
                "notes": "",
            },
        }
    ],
}


def test_corpus_io_single_dispatch_synthesis() -> None:
    """Single-dispatch clip with no dispatch_transcript → synthesized from clip transcript."""
    print("=== smoke test: corpus_io single-dispatch synthesis ===")
    import tempfile, json as _json

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        _json.dump(CORPUS_REAL_SHAPE_SINGLE, f)
        tmp_path = Path(f.name)

    corpus = load_corpus(tmp_path)
    _assert(len(corpus) == 1, "should load 1 clip")
    rec = corpus[0]
    _assert(rec["audio_ref"] == "real_single", "audio_ref mismatch")
    _assert(rec["audio_file"] == "real_single.wav", "audio_file mismatch")
    _assert(rec["clip_transcript"] != "", "clip_transcript should be populated")
    _assert(len(rec["dispatches"]) == 1, "should have 1 dispatch")

    # Synthesized dispatch_transcript should equal clip_transcript (single-dispatch)
    dt = rec["dispatches"][0]["dispatch_transcript"]
    _assert(
        dt == rec["clip_transcript"],
        f"synthesized dispatch_transcript should equal clip_transcript; got {dt!r}",
    )
    print("PASS: corpus_io single-dispatch synthesis\n")


def test_corpus_io_multi_dispatch_explicit() -> None:
    """Multi-dispatch clip with explicit dispatch_transcripts → passed through."""
    print("=== smoke test: corpus_io multi-dispatch explicit dispatch_transcripts ===")
    import tempfile, json as _json

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        _json.dump(CORPUS_REAL_SHAPE_MULTI, f)
        tmp_path = Path(f.name)

    corpus = load_corpus(tmp_path)
    rec = corpus[0]
    _assert(rec["expected_dispatch_count"] == 2, "expected_dispatch_count should be 2")
    _assert(len(rec["dispatches"]) == 2, "should have 2 dispatches")
    _assert(
        rec["dispatches"][0]["dispatch_transcript"].startswith("Engine 5"),
        "dispatch 0 transcript mismatch",
    )
    _assert(
        rec["dispatches"][1]["dispatch_transcript"].startswith("Battalion 6"),
        "dispatch 1 transcript mismatch",
    )
    # Clip transcript is independent — not a concat of dispatch transcripts necessarily
    _assert(rec["clip_transcript"] != "", "clip_transcript should be set")
    print("PASS: corpus_io multi-dispatch explicit dispatch_transcripts\n")


def test_missing_dispatch_transcript_excluded_not_zero_scored() -> None:
    """Multi-dispatch clip with one missing dispatch_transcript → skipped + counted, not zero-scored."""
    print("=== smoke test: missing dispatch_transcript excluded not zero-scored ===")
    import tempfile, json as _json

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        _json.dump(CORPUS_REAL_SHAPE_MISSING_DT, f)
        tmp_path = Path(f.name)

    corpus = load_corpus(tmp_path)
    rec = corpus[0]

    # dispatch 1 should have empty dispatch_transcript (multi-dispatch, no explicit label)
    _assert(
        rec["dispatches"][1].get("dispatch_transcript", "") == "",
        "dispatch 1 should have empty dispatch_transcript",
    )

    # Build a perfect system_output for the labeled dispatch
    system_output = [
        {
            "audio_ref": "real_missing_dt",
            "mode": "parser-isolated",
            "splitter_strategy": None,
            "produced_dispatch_count": 1,
            "run_transcript": None,
            "tone_runs": None,
            "dispatches": [
                {
                    "dispatch_text": "Dispatch one text",
                    "transcript_text": "Dispatch one text",
                    "special_call": False,
                    "units": [],
                    "channel": "K-Deck 8",
                    "incident_type": "Test incident",
                    "address": None,
                }
            ],
        }
    ]

    split_results, clip_wer_results, dispatch_results, n_skipped = score(corpus, system_output)
    metrics = compute_metrics(split_results, clip_wer_results, dispatch_results, n_skipped)

    # Dispatch 1 should be skipped (missing dispatch_transcript), not zero-scored
    _assert(n_skipped == 1, f"should have 1 skipped dispatch, got {n_skipped}")
    _assert(
        metrics["parsing"]["skipped_dispatches"] == 1,
        "metrics should report 1 skipped dispatch",
    )

    # Only 1 dispatch scored (dispatch 0) — and it should be correct
    _assert(
        metrics["parsing"]["eligible_dispatches"] == 1,
        f"should have 1 eligible dispatch, got {metrics['parsing']['eligible_dispatches']}",
    )

    # Channel for the labeled dispatch should be 100%
    chan_acc = metrics["parsing"]["fields"].get("channel")
    _assert(
        _approx_eq(chan_acc, 100.0, tol=0.1),
        f"channel should be 100% for the labeled dispatch, got {chan_acc}",
    )

    print_tables(metrics)
    print("PASS: missing dispatch_transcript excluded not zero-scored\n")


# ---------------------------------------------------------------------------
# Run all tests
# ---------------------------------------------------------------------------


def main() -> None:
    test_normalization_variants()
    test_perfect_run()
    test_bad_run()
    test_parser_isolated()
    test_splitter_isolated()
    test_corpus_io_single_dispatch_synthesis()
    test_corpus_io_multi_dispatch_explicit()
    test_missing_dispatch_transcript_excluded_not_zero_scored()
    print("All smoke tests passed.")


if __name__ == "__main__":
    main()
