"""
Corpus loader — single shared module imported by runner.py and scorer.py.

Real corpus shape (authoritative):
    {
      "_meta": {...},
      "clips": [
        {
          "audio_ref": str,
          "audio_filename": str,
          "audio_quality": str,           # "ok" | "unintelligible"
          "system_output": {...},          # labeling provenance — IGNORED
          "verified": {
            "transcript": str,            # CLIP-LEVEL spoken transcript — WER TRUTH
            "expected_dispatch_count": int | null,
            "dispatches": [
              {
                "dispatch_transcript": str,  # per-dispatch parser-feed text
                "special_call": bool,
                "units": [...],
                "channel": str | null,
                "incident_type": str | null,
                "address": str | null
              }
            ],
            "notes": str
          }
        }
      ]
    }

Also tolerates a bare array of records (legacy / flat format).

THE TWO-FIELD TRANSCRIPT MODEL
-------------------------------
  verified.transcript  (clip-level) → WER TRUTH.
      One acoustic utterance. WER is scored ONCE per clip against this.
      Includes preambles ("1430 hours Phoenix Fire Regional Dispatch") and
      [unintelligible] sentinels. Never concatenated from per-dispatch texts.

  verified.dispatches[i].dispatch_transcript  → PARSER FEED TEXT.
      The clean, single-dispatch span passed to the parser in parser-isolated
      mode. Used ONLY to feed the parser. NEVER used for WER.

These are intentionally separate fields with different jobs.
"""

from __future__ import annotations

import json
from pathlib import Path


def load_corpus(path: Path) -> list[dict]:
    """
    Load corpus.json (object-with-clips OR bare array) → normalized record list.

    Each returned record has:
      audio_ref, audio_file, audio_quality,
      clip_transcript (WER truth — clip level),
      expected_dispatch_count,
      dispatches (list of per-dispatch dicts with dispatch_transcript + field truth)
    """
    raw = json.loads(Path(path).read_text())
    clips = raw["clips"] if isinstance(raw, dict) else raw
    return [_normalize_clip(c) for c in clips]


def _normalize_clip(c: dict) -> dict:
    v = c.get("verified", c)  # tolerate flat records without "verified" nesting
    dispatches = _normalize_dispatches(v)
    edc = v.get("expected_dispatch_count")
    if edc is None:
        edc = len(dispatches)
    return {
        "audio_ref": c["audio_ref"],
        "audio_file": (
            c.get("audio_filename") or c.get("audio_file") or f'{c["audio_ref"]}.wav'
        ),
        "audio_quality": c.get("audio_quality", v.get("audio_quality", "ok")),
        "clip_transcript": v.get("transcript", ""),  # WER TRUTH — clip level
        "expected_dispatch_count": edc,
        "dispatches": dispatches,
    }


def _normalize_dispatches(v: dict) -> list[dict]:
    raw_dispatches = [dict(d) for d in v.get("dispatches", [])]
    clip_tx = v.get("transcript", "")

    for d in raw_dispatches:
        # dispatch_transcript: explicit field wins.
        # For a single-dispatch clip with no explicit field: synthesize from clip transcript.
        # For multi-dispatch clip with no explicit field: leave "" (excluded downstream).
        if "dispatch_transcript" not in d or not d["dispatch_transcript"].strip():
            d["dispatch_transcript"] = clip_tx if len(raw_dispatches) == 1 else ""

    return raw_dispatches
