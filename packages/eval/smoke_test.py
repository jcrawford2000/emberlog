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

from scorer import score, compute_metrics, print_tables, PARSE_FIELDS


# ---------------------------------------------------------------------------
# Synthetic corpus (two audio files, one single-dispatch, one multi-dispatch)
# ---------------------------------------------------------------------------

CORPUS = [
    {
        "audio_ref": "test_single",
        "audio_quality": "ok",
        "expected_dispatch_count": 1,
        "dispatches": [
            {
                "truth_transcript": "K-Deck 8 Difficulty breathing 4210 North 154th Drive Engine 12 Rescue 3 K-Deck 8",
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
        "dispatches": [
            {
                "truth_transcript": "K-Deck 9 Heart attack 350 West Van Buren Street Engine 5 K-Deck 9",
                "special_call": False,
                "units": ["Engine 5"],
                "channel": "K-Deck 9",
                "incident_type": "Heart attack",
                "address": "350 W Van Buren St",
            },
            {
                "truth_transcript": "Special call K-Deck 12 Structure fire 1000 North 3rd Street Battalion 6 Engine 8 Ladder 3 K-Deck 12",
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
        "dispatches": [
            {
                "truth_transcript": "inaudible",
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
    for rec in CORPUS:
        dispatches_out = []
        for d in rec["dispatches"]:
            dispatches_out.append(
                {
                    "dispatch_text": d["truth_transcript"],
                    "transcript_text": d["truth_transcript"],
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
                "run_transcript": " ".join(
                    d["truth_transcript"] for d in rec["dispatches"]
                ),
                "tone_runs": None,
                "dispatches": dispatches_out,
            }
        )
    return results


def _make_bad_output() -> list[dict]:
    """System output with deliberate errors for negative testing."""
    results = _make_truth_output()
    # test_single: wrong dispatch count
    results[0]["produced_dispatch_count"] = 0
    results[0]["dispatches"] = []
    # test_multi: wrong channel + wrong units on dispatch 1
    results[1]["dispatches"][0]["channel"] = "K-Deck 5"
    results[1]["dispatches"][0]["units"] = []
    return results


# ---------------------------------------------------------------------------
# Assertions
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
# Test: perfect run → ~100% everywhere
# ---------------------------------------------------------------------------


def test_perfect_run() -> None:
    print("=== smoke test: perfect run ===")
    truth_output = _make_truth_output()
    split_results, dispatch_results = score(CORPUS, truth_output)
    metrics = compute_metrics(split_results, dispatch_results)
    print_tables(metrics)

    sp = metrics["splitting"]
    tr = metrics["transcription"]
    pa = metrics["parsing"]

    _assert(sp["correct_pct"] == 100.0, f"splitting should be 100% but got {sp['correct_pct']}")
    _assert(sp["under"] == 0, f"under-split should be 0 but got {sp['under']}")
    _assert(sp["over"] == 0, f"over-split should be 0 but got {sp['over']}")

    # WER should be 0 (identical transcripts)
    _assert(
        _approx_eq(tr["headline_wer"], 0.0, tol=0.1),
        f"headline WER should be ~0 but got {tr['headline_wer']}",
    )

    # unintelligible clip should be reported separately
    _assert(tr["unintelligible_clips"] == 1, "should have 1 unintelligible clip")

    # All fields should be 100%
    for fname in PARSE_FIELDS:
        val = pa["fields"].get(fname)
        _assert(
            _approx_eq(val, 100.0, tol=0.1),
            f"field {fname} should be ~100% but got {val}",
        )

    print("PASS: perfect run\n")


# ---------------------------------------------------------------------------
# Test: bad run → splitting and field errors are detected
# ---------------------------------------------------------------------------


def test_bad_run() -> None:
    print("=== smoke test: bad run (deliberate errors) ===")
    bad_output = _make_bad_output()
    split_results, dispatch_results = score(CORPUS, bad_output)
    metrics = compute_metrics(split_results, dispatch_results)
    print_tables(metrics)

    sp = metrics["splitting"]
    pa = metrics["parsing"]

    # test_single was under-split (produced 0 instead of 1)
    _assert(sp["under"] >= 1, f"should have under-split >= 1 but got {sp['under']}")
    _assert(sp["correct_pct"] < 100.0, "should not be 100% splitting")

    # channel was wrong for test_multi dispatch 0 — but that dispatch was correctly split
    # so it should show up as a field error
    chan_acc = pa["fields"].get("channel")
    _assert(
        chan_acc is not None and chan_acc < 100.0,
        f"channel accuracy should be <100% but got {chan_acc}",
    )

    print("PASS: bad run errors detected\n")


# ---------------------------------------------------------------------------
# Test: normalization variants → still correct
# ---------------------------------------------------------------------------


def test_normalization_variants() -> None:
    print("=== smoke test: normalization variants ===")
    from normalize import norm_channel, norm_units, norm_address, norm_incident_type, wer

    # Channel variants all equal
    variants = ["K-Deck 8", "K-Dec 8", "KDEC8", "K Deck 8", "k deck 8"]
    normalized = [norm_channel(v) for v in variants]
    _assert(
        len(set(normalized)) == 1,
        f"channel variants should all normalize equal, got: {normalized}",
    )

    # Units order-insensitive
    u1 = norm_units(["Engine 12", "Rescue 3"])
    u2 = norm_units(["Rescue 3", "Engine 12"])
    _assert(u1 == u2, "units should be order-insensitive")

    # Address synonym normalization
    a1 = norm_address("4210 North 154th Drive")
    a2 = norm_address("4210 N 154th Dr")
    _assert(a1 == a2, f"address synonyms should normalize equal: {a1!r} vs {a2!r}")

    # Incident type: case/whitespace only
    i1 = norm_incident_type("Difficulty Breathing")
    i2 = norm_incident_type("difficulty  breathing")
    _assert(i1 == i2, "incident_type normalization should be case/ws only")

    # WER: identical = 0
    _assert(wer("hello world", "hello world") == 0.0, "identical WER should be 0")
    # WER: one substitution in 2-token reference
    w = wer("hello world", "hello earth")
    _assert(_approx_eq(w * 100, 50.0), f"one sub in 2 tokens = 50% WER, got {w*100:.1f}")

    print("PASS: normalization variants\n")


# ---------------------------------------------------------------------------
# Test: parser-isolated mode scored correctly
# ---------------------------------------------------------------------------


def test_parser_isolated() -> None:
    print("=== smoke test: parser-isolated mode ===")
    truth_output = _make_truth_output(mode="parser-isolated")
    split_results, dispatch_results = score(CORPUS, truth_output)
    metrics = compute_metrics(split_results, dispatch_results)
    print_tables(metrics)

    # No splits scored in parser-isolated mode
    _assert(
        metrics["splitting"]["total"] == 0,
        "parser-isolated should have no splitting rows",
    )
    # Fields should still be 100%
    for fname in PARSE_FIELDS:
        val = metrics["parsing"]["fields"].get(fname)
        _assert(
            _approx_eq(val, 100.0, tol=0.1) if val is not None else True,
            f"parser-isolated: field {fname} should be ~100% but got {val}",
        )
    print("PASS: parser-isolated\n")


# ---------------------------------------------------------------------------
# Test: splitter-isolated mode scored correctly
# ---------------------------------------------------------------------------


def test_splitter_isolated() -> None:
    print("=== smoke test: splitter-isolated mode ===")
    truth_output = _make_truth_output(mode="splitter-isolated")
    # No parse fields in output
    for rec in truth_output:
        rec["dispatches"] = []
    split_results, dispatch_results = score(CORPUS, truth_output)
    metrics = compute_metrics(split_results, dispatch_results)
    print_tables(metrics)

    # Splits are scored
    _assert(metrics["splitting"]["total"] > 0, "splitter-isolated should score splits")
    # No parse fields (no eligible clips since dispatches list is empty)
    _assert(metrics["parsing"]["eligible_clips"] == 0, "splitter-isolated should have 0 parse eligible")
    print("PASS: splitter-isolated\n")


# ---------------------------------------------------------------------------
# Run all tests
# ---------------------------------------------------------------------------


def main() -> None:
    test_normalization_variants()
    test_perfect_run()
    test_bad_run()
    test_parser_isolated()
    test_splitter_isolated()
    print("All smoke tests passed.")


if __name__ == "__main__":
    main()
