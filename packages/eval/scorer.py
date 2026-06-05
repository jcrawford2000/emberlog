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

WER is scored ONCE per CLIP against verified.transcript (clip-level truth).
verified.dispatches[i].dispatch_transcript is NEVER used for WER — it is
only used for parser-isolated field scoring. See corpus_io.py for the
two-field transcript model.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from corpus_io import load_corpus
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
class ClipWerResult:
    """WER scored ONCE per clip against the clip-level transcript (verified.transcript)."""
    audio_ref: str
    audio_quality: str
    clip_transcript: str      # truth (verified.transcript)
    produced_transcript: str  # system hypothesis (run_transcript or joined per-clip texts)

    @property
    def wer_value(self) -> float:
        return wer(self.clip_transcript, self.produced_transcript)


@dataclass
class DispatchResult:
    """Field accuracy for one dispatch. WER lives on ClipWerResult, not here."""
    audio_ref: str
    dispatch_index: int
    split_correct: bool
    audio_quality: str
    dispatch_transcript: str    # truth dispatch text (for failures.csv reference)
    produced_dispatch_text: str # what the system produced for this dispatch
    field_results: dict[str, bool] = field(default_factory=dict)
    clip_wer: float = 0.0       # denormalized from ClipWerResult for sort/display

    @property
    def missed_fields(self) -> list[str]:
        return [f for f, ok in self.field_results.items() if not ok]

    @property
    def severity(self) -> float:
        """Higher = worse. Drives worst-first sort in failures.csv."""
        return len(self.missed_fields) * 10 + self.clip_wer


# ---------------------------------------------------------------------------
# Field comparison
# ---------------------------------------------------------------------------

PARSE_FIELDS = ["special_call", "units", "channel", "incident_type", "address"]


def _compare_fields(truth: dict, system: dict) -> dict[str, bool]:
    results: dict[str, bool] = {}

    results["special_call"] = bool(truth.get("special_call")) == bool(
        system.get("special_call")
    )

    results["units"] = norm_units(truth.get("units") or []) == norm_units(
        system.get("units") or []
    )

    results["channel"] = norm_channel(truth.get("channel")) == norm_channel(
        system.get("channel")
    )

    results["incident_type"] = norm_incident_type(
        truth.get("incident_type")
    ) == norm_incident_type(system.get("incident_type"))

    results["address"] = norm_address(truth.get("address")) == norm_address(
        system.get("address")
    )

    return results


# ---------------------------------------------------------------------------
# Core scoring
# ---------------------------------------------------------------------------


def _produced_clip_transcript(sys_rec: dict) -> str:
    """
    Reconstruct the system's best hypothesis for the full clip transcript.

    - text strategy: run_transcript is the full Whisper output for the clip.
    - tone strategy: per-clip transcript_texts joined in dispatch order.
    - parser-isolated / splitter-isolated: no produced transcript → "".
    """
    mode = sys_rec.get("mode", "end-to-end")
    if mode != "end-to-end":
        return ""
    strategy = sys_rec.get("splitter_strategy", "text")
    if strategy == "text":
        return sys_rec.get("run_transcript") or ""
    # tone: join per-clip transcript_text values in order
    return " ".join(
        d.get("transcript_text", "")
        for d in sys_rec.get("dispatches", [])
        if d.get("transcript_text")
    )


def score(
    corpus: list[dict],
    system_output: list[dict],
) -> tuple[list[SplitResult], list[ClipWerResult], list[DispatchResult], int]:
    """
    Compare system_output against corpus.

    Returns:
        split_results:    one per audio clip (except parser-isolated)
        clip_wer_results: one per audio clip with a produced transcript
        dispatch_results: one per scored dispatch (field accuracy)
        n_skipped:        dispatches excluded due to missing dispatch_transcript
    """
    by_audio_ref = {rec["audio_ref"]: rec for rec in system_output}
    split_results: list[SplitResult] = []
    clip_wer_results: list[ClipWerResult] = []
    dispatch_results: list[DispatchResult] = []
    n_skipped = 0

    for corpus_rec in corpus:
        aref = corpus_rec["audio_ref"]
        sys_rec = by_audio_ref.get(aref)
        quality = corpus_rec.get("audio_quality", "ok")
        expected_count = corpus_rec.get("expected_dispatch_count", len(corpus_rec.get("dispatches", [])))
        truth_dispatches = corpus_rec.get("dispatches", [])
        clip_transcript = corpus_rec.get("clip_transcript", "")
        mode = (sys_rec or {}).get("mode", "end-to-end")

        if sys_rec is None:
            split_results.append(SplitResult(aref, expected_count, 0))
            continue

        produced_count = sys_rec.get("produced_dispatch_count", len(sys_rec.get("dispatches", [])))

        if mode != "parser-isolated":
            split_results.append(SplitResult(aref, expected_count, produced_count))

        split_correct = (expected_count == produced_count)
        # In parser-isolated mode, split accuracy is not being measured.
        # All labeled dispatches are eligible for parse scoring regardless.
        parse_split_correct = True if mode == "parser-isolated" else split_correct

        # --- Clip-level WER (end-to-end mode only) ---
        produced_clip_tx = _produced_clip_transcript(sys_rec)
        if mode == "end-to-end" and clip_transcript:
            clip_wer_rec = ClipWerResult(
                audio_ref=aref,
                audio_quality=quality,
                clip_transcript=clip_transcript,
                produced_transcript=produced_clip_tx,
            )
            clip_wer_results.append(clip_wer_rec)
            clip_wer_val = clip_wer_rec.wer_value
        else:
            clip_wer_val = 0.0

        # --- splitter-isolated: count only, no per-dispatch analysis ---
        if mode == "splitter-isolated":
            continue

        # --- Per-dispatch field accuracy ---
        sys_dispatches = sys_rec.get("dispatches", [])

        for i, truth_d in enumerate(truth_dispatches):
            sys_d = sys_dispatches[i] if i < len(sys_dispatches) else {}

            dispatch_tx = truth_d.get("dispatch_transcript", "")

            # Skip dispatches without a dispatch_transcript (not yet labeled).
            # Do NOT zero-score them — that would bias field accuracy downward.
            if not dispatch_tx.strip():
                n_skipped += 1
                continue

            produced_dispatch_text = sys_d.get("dispatch_text") or sys_d.get("transcript_text") or ""
            field_results = _compare_fields(truth_d, sys_d)

            dispatch_results.append(
                DispatchResult(
                    audio_ref=aref,
                    dispatch_index=i,
                    split_correct=parse_split_correct,
                    audio_quality=quality,
                    dispatch_transcript=dispatch_tx,
                    produced_dispatch_text=produced_dispatch_text,
                    field_results=field_results,
                    clip_wer=clip_wer_val,
                )
            )

    return split_results, clip_wer_results, dispatch_results, n_skipped


# ---------------------------------------------------------------------------
# Metrics computation
# ---------------------------------------------------------------------------


def compute_metrics(
    split_results: list[SplitResult],
    clip_wer_results: list[ClipWerResult],
    dispatch_results: list[DispatchResult],
    n_skipped: int = 0,
) -> dict:
    # --- Splitting ---
    total_splits = len(split_results)
    correct_splits = sum(1 for r in split_results if r.correct)
    under_splits = sum(1 for r in split_results if r.direction == "under")
    over_splits = sum(1 for r in split_results if r.direction == "over")
    split_pct = correct_splits / total_splits if total_splits else 0.0

    # --- Transcription (WER — per clip) ---
    wer_eligible = [r for r in clip_wer_results if r.audio_quality != "unintelligible"]
    wer_unintelligible = [r for r in clip_wer_results if r.audio_quality == "unintelligible"]

    def _mean_wer(rs: list[ClipWerResult]) -> Optional[float]:
        vals = [r.wer_value for r in rs]
        return sum(vals) / len(vals) if vals else None

    headline_wer = _mean_wer(wer_eligible)
    unintelligible_wer = _mean_wer(wer_unintelligible)

    # --- Parsing (per-field, per dispatch) ---
    # Only over correctly-split clips with audio_quality != unintelligible.
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
            "unintelligible_wer": (
                round(unintelligible_wer * 100, 3) if unintelligible_wer is not None else None
            ),
        },
        "parsing": {
            "eligible_dispatches": total_parse,
            "skipped_dispatches": n_skipped,
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

    print(sep, file=file)
    print("SPLITTING", file=file)
    print(sep, file=file)
    print(f"  {'Total audio clips':<30} {sp['total']}", file=file)
    print(f"  {'Correct split':<30} {sp['correct']}  ({_pct(sp['correct_pct'])})", file=file)
    print(f"  {'Under-split (missed dispatch)':<30} {sp['under']}", file=file)
    print(f"  {'Over-split (false boundary)':<30} {sp['over']}", file=file)
    print(file=file)

    print(sep, file=file)
    print("TRANSCRIPTION (WER — per clip)", file=file)
    print(sep, file=file)
    print(f"  {'Eligible clips':<30} {tr['eligible_clips']}", file=file)
    print(f"  {'Headline WER':<30} {_pct(tr['headline_wer'])}", file=file)
    print(f"  {'Unintelligible clips':<30} {tr['unintelligible_clips']}", file=file)
    if tr["unintelligible_wer"] is not None:
        print(f"  {'Unintelligible WER':<30} {_pct(tr['unintelligible_wer'])}", file=file)
    print(file=file)

    print(sep, file=file)
    print("PARSING (field accuracy, correctly-split non-unintelligible)", file=file)
    print(sep, file=file)
    print(f"  {'Eligible dispatches':<30} {pa['eligible_dispatches']}", file=file)
    if pa["skipped_dispatches"]:
        print(
            f"  {'Skipped (no dispatch_transcript)':<30} {pa['skipped_dispatches']}",
            file=file,
        )
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
    """One row per dispatch, sorted worst-first by severity (missed fields + clip WER)."""
    rows = sorted(dispatch_results, key=lambda r: -r.severity)

    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "audio_ref",
                "dispatch_index",
                "split_correct",
                "audio_quality",
                "clip_wer_pct",
                "missed_fields",
                "produced_dispatch_text",
                "dispatch_transcript",
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
                    "clip_wer_pct": round(r.clip_wer * 100, 2),
                    "missed_fields": "|".join(r.missed_fields),
                    "produced_dispatch_text": r.produced_dispatch_text,
                    "dispatch_transcript": r.dispatch_transcript,
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

    corpus = load_corpus(args.corpus)
    system_output = json.loads(args.output.read_text())

    split_results, clip_wer_results, dispatch_results, n_skipped = score(
        corpus, system_output
    )
    metrics = compute_metrics(split_results, clip_wer_results, dispatch_results, n_skipped)

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
