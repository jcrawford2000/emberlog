"""
Eval harness scorer — pure, deterministic, no audio / GPU / network / clock.

Input:  corpus.json  (frozen ground truth, never modified)
        system_output.json  (produced by runner.py)

Output: three printed tables + metrics.json + failures.csv

Usage:
    python scorer.py \\
        --corpus  corpus/corpus.json \\
        --output  runs/2026-06-01/system_output.json \\
        --metrics runs/2026-06-01/metrics.json \\
        --failures runs/2026-06-01/failures.csv

Corpus JSON schema
------------------
Array of objects, one per audio file:
{
  "audio_ref":             str,   # unique key (e.g. filename stem)
  "audio_quality":         str,   # "ok" | "unintelligible"
  "expected_dispatch_count": int,
  "dispatches": [          # ground-truth per dispatch, in order
    {
      "truth_transcript":  str,   # what Whisper should ideally produce
      "special_call":      bool,
      "units":             [str],
      "channel":           str | null,
      "incident_type":     str | null,
      "address":           str | null
    }
  ]
}

System output JSON schema
-------------------------
Array of objects produced by runner.py, one per audio_ref:
{
  "audio_ref":             str,
  "mode":                  str,   # "end-to-end" | "parser-isolated" | "splitter-isolated"
  "splitter_strategy":     str | null,  # "text" | "tone" | null
  "produced_dispatch_count": int,
  "run_transcript":        str | null,  # full Whisper text (end-to-end text strategy)
  "tone_runs":             [...] | null,
  "dispatches": [          # produced dispatches, in order
    {
      "dispatch_text":     str,
      "transcript_text":   str | null,  # per-clip transcript (tone strategy)
      "special_call":      bool,
      "units":             [str],
      "channel":           str | null,
      "incident_type":     str | null,
      "address":           str | null
    }
  ]
}
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from normalize import (
    norm_address,
    norm_channel,
    norm_incident_type,
    norm_units,
    wer,
)


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass
class SplitResult:
    audio_ref: str
    expected: int
    produced: int

    @property
    def correct(self) -> bool:
        return self.expected == self.produced

    @property
    def direction(self) -> str:
        if self.produced < self.expected:
            return "under"
        if self.produced > self.expected:
            return "over"
        return "correct"


@dataclass
class DispatchResult:
    audio_ref: str
    dispatch_index: int
    split_correct: bool
    audio_quality: str
    truth_transcript: str
    produced_transcript: str
    field_results: dict[str, bool] = field(default_factory=dict)

    @property
    def wer_value(self) -> float:
        return wer(self.truth_transcript, self.produced_transcript)

    @property
    def missed_fields(self) -> list[str]:
        return [f for f, ok in self.field_results.items() if not ok]

    @property
    def severity(self) -> float:
        """Higher = worse. Used to sort failures.csv worst-first."""
        return len(self.missed_fields) * 10 + self.wer_value


# ---------------------------------------------------------------------------
# Field comparison
# ---------------------------------------------------------------------------

PARSE_FIELDS = ["special_call", "units", "channel", "incident_type", "address"]


def _compare_fields(truth: dict, system: dict) -> dict[str, bool]:
    results: dict[str, bool] = {}

    # special_call: boolean equality
    results["special_call"] = bool(truth.get("special_call")) == bool(
        system.get("special_call")
    )

    # units: order-insensitive, case/whitespace-insensitive
    results["units"] = norm_units(truth.get("units") or []) == norm_units(
        system.get("units") or []
    )

    # channel: normalized equality
    results["channel"] = norm_channel(truth.get("channel")) == norm_channel(
        system.get("channel")
    )

    # incident_type: case/whitespace only
    results["incident_type"] = norm_incident_type(
        truth.get("incident_type")
    ) == norm_incident_type(system.get("incident_type"))

    # address: directionals + suffix synonyms, case/punct-insensitive
    results["address"] = norm_address(truth.get("address")) == norm_address(
        system.get("address")
    )

    return results


# ---------------------------------------------------------------------------
# Core scoring
# ---------------------------------------------------------------------------


def score(
    corpus: list[dict],
    system_output: list[dict],
) -> tuple[list[SplitResult], list[DispatchResult]]:
    """
    Compare system_output against corpus. Returns (split_results, dispatch_results).
    Both lists are in corpus-iteration order.
    """
    by_audio_ref = {rec["audio_ref"]: rec for rec in system_output}
    split_results: list[SplitResult] = []
    dispatch_results: list[DispatchResult] = []

    for corpus_rec in corpus:
        aref = corpus_rec["audio_ref"]
        sys_rec = by_audio_ref.get(aref)
        quality = corpus_rec.get("audio_quality", "ok")
        expected_count = corpus_rec.get("expected_dispatch_count", len(corpus_rec.get("dispatches", [])))
        truth_dispatches = corpus_rec.get("dispatches", [])
        mode = (sys_rec or {}).get("mode", "end-to-end")

        if sys_rec is None:
            # Missing from system output — treat as zero dispatches produced
            split_results.append(SplitResult(aref, expected_count, 0))
            continue

        produced_count = sys_rec.get("produced_dispatch_count", len(sys_rec.get("dispatches", [])))

        if mode != "parser-isolated":
            split_results.append(SplitResult(aref, expected_count, produced_count))

        split_correct = (expected_count == produced_count)
        sys_dispatches = sys_rec.get("dispatches", [])

        # splitter-isolated only scores dispatch count; skip per-dispatch analysis
        if mode == "splitter-isolated":
            continue

        for i, truth_d in enumerate(truth_dispatches):
            sys_d = sys_dispatches[i] if i < len(sys_dispatches) else {}

            # For text strategy: dispatch_text is the split substring of the full transcript.
            # For tone strategy: transcript_text is the per-clip Whisper output.
            if mode == "end-to-end":
                produced_text = sys_d.get("transcript_text") or sys_d.get("dispatch_text") or ""
            else:
                # parser-isolated: truth transcript is fed in as dispatch_text
                produced_text = sys_d.get("dispatch_text") or sys_d.get("transcript_text") or ""

            truth_transcript = truth_d.get("truth_transcript", "")
            field_results = _compare_fields(truth_d, sys_d)

            dispatch_results.append(
                DispatchResult(
                    audio_ref=aref,
                    dispatch_index=i,
                    split_correct=split_correct,
                    audio_quality=quality,
                    truth_transcript=truth_transcript,
                    produced_transcript=produced_text,
                    field_results=field_results,
                )
            )

    return split_results, dispatch_results


# ---------------------------------------------------------------------------
# Metrics computation
# ---------------------------------------------------------------------------


def compute_metrics(
    split_results: list[SplitResult],
    dispatch_results: list[DispatchResult],
) -> dict:
    # --- Splitting ---
    total_splits = len(split_results)
    correct_splits = sum(1 for r in split_results if r.correct)
    under_splits = sum(1 for r in split_results if r.direction == "under")
    over_splits = sum(1 for r in split_results if r.direction == "over")
    split_pct = correct_splits / total_splits if total_splits else 0.0

    # --- Transcription (WER) ---
    # Exclude unintelligible clips from headline; report separately
    wer_eligible = [
        r for r in dispatch_results if r.audio_quality != "unintelligible" and r.truth_transcript
    ]
    wer_unintelligible = [
        r for r in dispatch_results if r.audio_quality == "unintelligible" and r.truth_transcript
    ]

    def _mean_wer(rs: list[DispatchResult]) -> Optional[float]:
        vals = [r.wer_value for r in rs]
        return sum(vals) / len(vals) if vals else None

    headline_wer = _mean_wer(wer_eligible)
    unintelligible_wer = _mean_wer(wer_unintelligible)

    # --- Parsing (per-field) ---
    # Only over correctly-split clips with audio_quality != unintelligible
    parse_eligible = [
        r
        for r in dispatch_results
        if r.split_correct and r.audio_quality != "unintelligible" and r.field_results
    ]
    total_parse = len(parse_eligible)

    field_acc: dict[str, Optional[float]] = {}
    for f in PARSE_FIELDS:
        hits = sum(1 for r in parse_eligible if r.field_results.get(f, False))
        field_acc[f] = hits / total_parse if total_parse else None

    return {
        "splitting": {
            "total": total_splits,
            "correct": correct_splits,
            "correct_pct": round(split_pct * 100, 2),
            "under": under_splits,
            "over": over_splits,
        },
        "transcription": {
            "eligible_clips": len(wer_eligible),
            "headline_wer": round(headline_wer * 100, 3) if headline_wer is not None else None,
            "unintelligible_clips": len(wer_unintelligible),
            "unintelligible_wer": round(unintelligible_wer * 100, 3) if unintelligible_wer is not None else None,
        },
        "parsing": {
            "eligible_clips": total_parse,
            "fields": {
                f: round(v * 100, 2) if v is not None else None
                for f, v in field_acc.items()
            },
        },
    }


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


def _pct(v: Optional[float]) -> str:
    return f"{v:.1f}%" if v is not None else "n/a"


def print_tables(metrics: dict, file=sys.stdout) -> None:
    m = metrics
    sp = m["splitting"]
    tr = m["transcription"]
    pa = m["parsing"]

    sep = "-" * 56

    # Table 1: Splitting
    print(sep, file=file)
    print("SPLITTING", file=file)
    print(sep, file=file)
    print(f"  {'Total audio clips':<30} {sp['total']}", file=file)
    print(f"  {'Correct split':<30} {sp['correct']}  ({_pct(sp['correct_pct'])})", file=file)
    print(f"  {'Under-split (missed dispatch)':<30} {sp['under']}", file=file)
    print(f"  {'Over-split (false boundary)':<30} {sp['over']}", file=file)
    print(file=file)

    # Table 2: Transcription
    print(sep, file=file)
    print("TRANSCRIPTION (WER)", file=file)
    print(sep, file=file)
    print(f"  {'Eligible clips':<30} {tr['eligible_clips']}", file=file)
    print(f"  {'Headline WER':<30} {_pct(tr['headline_wer'])}", file=file)
    print(f"  {'Unintelligible clips':<30} {tr['unintelligible_clips']}", file=file)
    if tr["unintelligible_wer"] is not None:
        print(f"  {'Unintelligible WER':<30} {_pct(tr['unintelligible_wer'])}", file=file)
    print(file=file)

    # Table 3: Parsing
    print(sep, file=file)
    print("PARSING (field accuracy, correctly-split non-unintelligible clips)", file=file)
    print(sep, file=file)
    print(f"  {'Eligible clips':<30} {pa['eligible_clips']}", file=file)
    for fname, val in pa["fields"].items():
        print(f"  {fname:<30} {_pct(val)}", file=file)
    print(sep, file=file)


# ---------------------------------------------------------------------------
# failures.csv
# ---------------------------------------------------------------------------


def write_failures_csv(
    dispatch_results: list[DispatchResult],
    out_path: Path,
) -> None:
    """One row per dispatch, sorted worst-first by severity (missed fields + WER)."""
    rows = sorted(dispatch_results, key=lambda r: -r.severity)

    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "audio_ref",
                "dispatch_index",
                "split_correct",
                "audio_quality",
                "wer",
                "missed_fields",
                "produced_transcript",
                "truth_transcript",
            ],
        )
        writer.writeheader()
        for r in rows:
            writer.writerow(
                {
                    "audio_ref": r.audio_ref,
                    "dispatch_index": r.dispatch_index,
                    "split_correct": r.split_correct,
                    "audio_quality": r.audio_quality,
                    "wer": round(r.wer_value * 100, 2),
                    "missed_fields": "|".join(r.missed_fields),
                    "produced_transcript": r.produced_transcript,
                    "truth_transcript": r.truth_transcript,
                }
            )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Score system_output.json against corpus.json.")
    p.add_argument("--corpus", type=Path, required=True, help="Path to corpus.json")
    p.add_argument("--output", type=Path, required=True, help="Path to system_output.json")
    p.add_argument("--metrics", type=Path, required=True, help="Where to write metrics.json")
    p.add_argument(
        "--failures", type=Path, default=None, help="Where to write failures.csv (optional)"
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()

    corpus = json.loads(args.corpus.read_text())
    system_output = json.loads(args.output.read_text())

    split_results, dispatch_results = score(corpus, system_output)
    metrics = compute_metrics(split_results, dispatch_results)

    print_tables(metrics)

    args.metrics.parent.mkdir(parents=True, exist_ok=True)
    args.metrics.write_text(json.dumps(metrics, indent=2))
    print(f"\nmetrics.json → {args.metrics}")

    if args.failures:
        args.failures.parent.mkdir(parents=True, exist_ok=True)
        write_failures_csv(dispatch_results, args.failures)
        print(f"failures.csv → {args.failures}")


if __name__ == "__main__":
    main()
