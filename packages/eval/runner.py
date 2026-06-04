"""
Eval harness runner — GPU/code-touching piece.

IMPORT ORDER IS CRITICAL
------------------------
bootstrap.setup() MUST be called before any emberlog.* import.
This file does NOT import emberlog at module level for that reason.
All emberlog imports happen inside _lazy_imports() which is called
after bootstrap.setup() has been invoked.

Usage:
    python runner.py \\
        --corpus     corpus/corpus.json \\
        --audio-dir  /data/audio \\
        --out-dir    runs/2026-06-01 \\
        --strategy   text \\
        --mode       end-to-end \\
        --device     cuda \\
        --model      large-v3

Modes:
    end-to-end        audio → transcribe → split → parse  (real-world number)
    parser-isolated   truth transcripts → parse only       (highest diagnostic value)
    splitter-isolated truth transcripts → split count only (both strategies)

Strategies (for end-to-end and splitter-isolated):
    text   live pipeline path: transcript text → split_transcript → parse
    tone   ToneSplitter → per-clip wav → transcribe each → parse each

Output files in --out-dir:
    system_output.json   (input to scorer.py)
    manifest.json        (run provenance — no manifest = unattributable run)
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# BOOTSTRAP — must happen before any emberlog import
# ---------------------------------------------------------------------------

# bootstrap is in the same directory; add it to path if needed
sys.path.insert(0, str(Path(__file__).parent))
import bootstrap  # noqa: E402
from corpus_io import load_corpus  # noqa: E402


# ---------------------------------------------------------------------------
# Lazy emberlog imports (called after bootstrap.setup())
# ---------------------------------------------------------------------------

_imports_done = False
FasterWhisperTranscriber = None
WhisperConfig = None
Segment = None
split_transcript = None
ToneSplitter = None
ToneConfig = None
clean_transcript = None
Transcript = None


def _lazy_imports() -> None:
    global _imports_done
    global FasterWhisperTranscriber, WhisperConfig
    global Segment, split_transcript
    global ToneSplitter, ToneConfig
    global clean_transcript, Transcript

    if _imports_done:
        return

    # These imports trigger emberlog.config.config — bootstrap must have run first.
    from emberlog.transcriber.whisper_fast import (  # noqa: PLC0415
        FasterWhisperTranscriber as _FWT,
        WhisperConfig as _WC,
    )
    from emberlog.segmentation.splitter import (  # noqa: PLC0415
        Segment as _Seg,
        split_transcript as _st,
    )
    from emberlog.utils.transcribe import (  # noqa: PLC0415
        ToneSplitter as _TS,
        ToneConfig as _TC,
    )
    from emberlog.cleaning.cleaner import clean_transcript as _ct  # noqa: PLC0415
    from emberlog.models.transcript import Transcript as _Tr  # noqa: PLC0415

    FasterWhisperTranscriber = _FWT
    WhisperConfig = _WC
    Segment = _Seg
    split_transcript = _st
    ToneSplitter = _TS
    ToneConfig = _TC
    clean_transcript = _ct
    Transcript = _Tr
    _imports_done = True


# ---------------------------------------------------------------------------
# Run config
# ---------------------------------------------------------------------------


@dataclass
class RunConfig:
    mode: str = "end-to-end"          # end-to-end | parser-isolated | splitter-isolated
    strategy: str = "text"             # text | tone
    model_name: str = "large-v3"
    device: str = "cuda"
    compute_type: str = "float16"
    initial_prompt: Optional[str] = None
    beam_size: int = 5
    best_of: int = 8
    temperature: float = 0.0
    vad_filter: bool = True
    language: str = "en"
    no_speech_threshold: float = 0.3
    log_prob_threshold: float = -1.2
    compression_ratio_threshold: float = 2.8
    tone_config: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Manifest helpers
# ---------------------------------------------------------------------------


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()[:16]}"


def _hash_str(s: str) -> str:
    return f"sha256:{hashlib.sha256(s.encode()).hexdigest()[:16]}"


def _git_commit() -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent,
        )
        return r.stdout.strip() if r.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def build_manifest(cfg: RunConfig, corpus_path: Path) -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": cfg.mode,
        "splitter_strategy": cfg.strategy if cfg.mode != "parser-isolated" else None,
        "model_name": cfg.model_name,
        "device": cfg.device,
        "compute_type": cfg.compute_type,
        "initial_prompt_hash": _hash_str(cfg.initial_prompt or ""),
        "parser": "clean_transcript",
        "git_commit": _git_commit(),
        "ffmpeg_version": bootstrap.ffmpeg_version(),
        "corpus_hash": _hash_file(corpus_path),
    }


# ---------------------------------------------------------------------------
# Parser helper (shared across modes)
# ---------------------------------------------------------------------------


def _run_parser(dispatch_text: str, audio_path: Path, transcript_text: Optional[str] = None) -> dict:
    """Wrap dispatch_text in a Transcript and run clean_transcript."""
    t = Transcript(audio_path=audio_path, text=dispatch_text)
    result = clean_transcript(t)
    out = {
        "dispatch_text": dispatch_text,
        "transcript_text": transcript_text,
        "special_call": result.special_call,
        "units": result.units,
        "channel": result.channel,
        "incident_type": result.incident_type,
        "address": result.address,
    }
    return out


# ---------------------------------------------------------------------------
# End-to-end: text strategy
# ---------------------------------------------------------------------------


async def _run_e2e_text(
    corpus_rec: dict,
    audio_path: Path,
    transcriber,
) -> dict:
    transcript = await transcriber.transcribe(audio_path)
    duration = transcript.duration_s or 0.0

    segments = [Segment(start=0.0, end=duration, text=transcript.text)]
    dispatches_raw = split_transcript(segments, audio_path)

    dispatches_out = []
    for d in dispatches_raw:
        parsed = _run_parser(d.text, audio_path, transcript_text=None)
        dispatches_out.append(parsed)

    return {
        "audio_ref": corpus_rec["audio_ref"],
        "mode": "end-to-end",
        "splitter_strategy": "text",
        "produced_dispatch_count": len(dispatches_out),
        "run_transcript": transcript.text,
        "tone_runs": None,
        "dispatches": dispatches_out,
    }


# ---------------------------------------------------------------------------
# End-to-end: tone strategy
# ---------------------------------------------------------------------------


async def _run_e2e_tone(
    corpus_rec: dict,
    audio_path: Path,
    transcriber,
    tone_cfg_overrides: dict,
    clip_dir: Path,
) -> dict:
    tone_cfg_kwargs = {**tone_cfg_overrides}
    tc = ToneConfig(**tone_cfg_kwargs)
    splitter = ToneSplitter(tc)

    sub_dir = clip_dir / corpus_rec["audio_ref"]
    clips, tone_runs = splitter.split_file(audio_path, save_dir=sub_dir)

    dispatches_out = []
    for clip_path in clips:
        clip_transcript = await transcriber.transcribe(clip_path)
        parsed = _run_parser(
            clip_transcript.text, audio_path, transcript_text=clip_transcript.text
        )
        dispatches_out.append(parsed)

    tone_runs_serializable = [
        {"start_s": s, "end_s": e, "dur_s": d} for s, e, d in tone_runs
    ]

    return {
        "audio_ref": corpus_rec["audio_ref"],
        "mode": "end-to-end",
        "splitter_strategy": "tone",
        "produced_dispatch_count": len(dispatches_out),
        "run_transcript": None,
        "tone_runs": tone_runs_serializable,
        "dispatches": dispatches_out,
    }


# ---------------------------------------------------------------------------
# Parser-isolated mode
# ---------------------------------------------------------------------------


def _run_parser_isolated(corpus_rec: dict) -> dict:
    """
    Feed dispatch_transcript (per-dispatch parser-feed text) to the parser only.
    No audio, no Whisper, no splitting.

    Dispatches with an empty dispatch_transcript are skipped — they are not yet
    labeled for multi-dispatch clips. They are NOT zero-scored; the scorer
    excludes and counts them separately.
    """
    truth_dispatches = corpus_rec.get("dispatches", [])
    audio_ref = corpus_rec["audio_ref"]
    # Sentinel path — used only for logging inside clean_transcript
    sentinel_path = Path(f"{audio_ref}.wav")

    dispatches_out = []
    for td in truth_dispatches:
        dispatch_tx = td.get("dispatch_transcript", "")
        if not dispatch_tx.strip():
            # Missing label — skip, don't feed empty text to parser
            continue
        parsed = _run_parser(dispatch_tx, sentinel_path, transcript_text=dispatch_tx)
        dispatches_out.append(parsed)

    return {
        "audio_ref": audio_ref,
        "mode": "parser-isolated",
        "splitter_strategy": None,
        "produced_dispatch_count": len(dispatches_out),
        "run_transcript": None,
        "tone_runs": None,
        "dispatches": dispatches_out,
    }


# ---------------------------------------------------------------------------
# Splitter-isolated mode
# ---------------------------------------------------------------------------


def _run_splitter_isolated_text(corpus_rec: dict) -> dict:
    """Feed combined truth transcripts to text splitter; score count only."""
    truth_dispatches = corpus_rec.get("dispatches", [])
    audio_ref = corpus_rec["audio_ref"]

    # Combine all truth transcripts as if they were one Whisper output
    combined = " ".join(td.get("truth_transcript", "") for td in truth_dispatches)
    audio_path = Path(f"{audio_ref}.wav")

    segments = [Segment(start=0.0, end=999.0, text=combined)]
    dispatches_raw = split_transcript(segments, audio_path)

    return {
        "audio_ref": audio_ref,
        "mode": "splitter-isolated",
        "splitter_strategy": "text",
        "produced_dispatch_count": len(dispatches_raw),
        "run_transcript": combined,
        "tone_runs": None,
        "dispatches": [],
    }


def _run_splitter_isolated_tone(
    corpus_rec: dict,
    audio_path: Path,
    tone_cfg_overrides: dict,
    clip_dir: Path,
) -> dict:
    """Run ToneSplitter on audio; score count only — no transcription needed."""
    tc = ToneConfig(**tone_cfg_overrides)
    splitter = ToneSplitter(tc)

    sub_dir = clip_dir / corpus_rec["audio_ref"]
    clips, tone_runs = splitter.split_file(audio_path, save_dir=sub_dir)

    tone_runs_serializable = [
        {"start_s": s, "end_s": e, "dur_s": d} for s, e, d in tone_runs
    ]

    return {
        "audio_ref": corpus_rec["audio_ref"],
        "mode": "splitter-isolated",
        "splitter_strategy": "tone",
        "produced_dispatch_count": len(clips),
        "run_transcript": None,
        "tone_runs": tone_runs_serializable,
        "dispatches": [],
    }


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


async def run(
    corpus: list[dict],
    audio_dir: Path,
    cfg: RunConfig,
    out_dir: Path,
) -> list[dict]:
    _lazy_imports()

    clip_dir = out_dir / "_tone_clips"
    results: list[dict] = []

    transcriber = None
    if cfg.mode in ("end-to-end",) and cfg.strategy in ("text", "tone"):
        whisper_cfg = WhisperConfig(
            model_name=cfg.model_name,
            device=cfg.device,
            compute_type=cfg.compute_type,
            initial_prompt=cfg.initial_prompt or "",
            beam_size=cfg.beam_size,
            best_of=cfg.best_of,
            temperature=cfg.temperature,
            vad_filter=cfg.vad_filter,
            language=cfg.language,
            no_speech_threshold=cfg.no_speech_threshold,
            log_prob_threshold=cfg.log_prob_threshold,
            compression_ratio_threshold=cfg.compression_ratio_threshold,
        )
        transcriber = FasterWhisperTranscriber(cfg=whisper_cfg)

    for corpus_rec in corpus:
        aref = corpus_rec["audio_ref"]
        audio_file = corpus_rec.get("audio_file", f"{aref}.wav")
        audio_path = audio_dir / audio_file

        print(f"[runner] {aref}  mode={cfg.mode}  strategy={cfg.strategy}", flush=True)

        try:
            if cfg.mode == "end-to-end":
                if not audio_path.exists():
                    print(f"  WARNING: audio not found: {audio_path}", flush=True)
                    continue
                if cfg.strategy == "text":
                    rec = await _run_e2e_text(corpus_rec, audio_path, transcriber)
                else:
                    rec = await _run_e2e_tone(
                        corpus_rec, audio_path, transcriber, cfg.tone_config, clip_dir
                    )

            elif cfg.mode == "parser-isolated":
                rec = _run_parser_isolated(corpus_rec)

            elif cfg.mode == "splitter-isolated":
                if cfg.strategy == "text":
                    rec = _run_splitter_isolated_text(corpus_rec)
                else:
                    if not audio_path.exists():
                        print(f"  WARNING: audio not found: {audio_path}", flush=True)
                        continue
                    rec = _run_splitter_isolated_tone(
                        corpus_rec, audio_path, cfg.tone_config, clip_dir
                    )
            else:
                raise ValueError(f"Unknown mode: {cfg.mode!r}")

        except Exception as exc:
            print(f"  ERROR processing {aref}: {exc}", file=sys.stderr, flush=True)
            rec = {
                "audio_ref": aref,
                "mode": cfg.mode,
                "splitter_strategy": cfg.strategy,
                "produced_dispatch_count": 0,
                "run_transcript": None,
                "tone_runs": None,
                "dispatches": [],
                "error": str(exc),
            }

        results.append(rec)
        expected = corpus_rec.get("expected_dispatch_count", "?")
        produced = rec.get("produced_dispatch_count", 0)
        print(f"  dispatches: expected={expected}  produced={produced}", flush=True)

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run eval pipeline and emit system_output.json.")
    p.add_argument("--corpus", type=Path, required=True)
    p.add_argument("--audio-dir", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--mode", choices=["end-to-end", "parser-isolated", "splitter-isolated"],
                   default="end-to-end")
    p.add_argument("--strategy", choices=["text", "tone"], default="text")
    p.add_argument("--model", default="large-v3")
    p.add_argument("--device", default="cuda")
    p.add_argument("--compute-type", default="float16")
    p.add_argument("--initial-prompt", default=None)
    p.add_argument("--beam-size", type=int, default=5)
    p.add_argument("--best-of", type=int, default=8)
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--workspace", type=Path, default=None,
                   help="Scratch dir for EMBERLOG_* paths (default: system tempdir)")
    return p.parse_args()


def main() -> None:
    args = _parse_args()

    # MUST happen before any emberlog import — bootstrap.setup() sets env vars
    bootstrap.setup(workspace=args.workspace)

    corpus = load_corpus(args.corpus)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    cfg = RunConfig(
        mode=args.mode,
        strategy=args.strategy,
        model_name=args.model,
        device=args.device,
        compute_type=args.compute_type,
        initial_prompt=args.initial_prompt,
        beam_size=args.beam_size,
        best_of=args.best_of,
        temperature=args.temperature,
    )

    manifest = build_manifest(cfg, args.corpus)
    manifest_path = args.out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"manifest.json → {manifest_path}")

    results = asyncio.run(run(corpus, args.audio_dir, cfg, args.out_dir))

    out_path = args.out_dir / "system_output.json"
    out_path.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nsystem_output.json → {out_path}")
    print(f"Processed {len(results)} audio records.")


if __name__ == "__main__":
    main()
