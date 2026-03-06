from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import soundfile as sf

try:
    from scipy.signal import resample_poly
except Exception:
    resample_poly = None

from faster_whisper import WhisperModel


@dataclass
class ToneConfig:
    sample_rate: int = 16000
    frame_ms: int = 50
    hop_ms: int = 10
    tone_hz: float = 660.0
    tone_tol_hz: float = 15.0
    tone_score_thresh: float = 0.70  # ratio of power@tone / energy
    min_tone_sec: float = 1.8
    max_tone_sec: float = 2.4
    post_tone_gap_sec: float = 0.70
    pre_next_tone_pad_sec: float = 0.10
    min_dispatch_sec: float = 0.8
    amp_gate: float = 5e-5
    merge_gap_sec: float = 0.20


class ToneSplitter:
    def __init__(self, cfg: ToneConfig):
        self.cfg = cfg

    @staticmethod
    def _goertzel_power(frame: np.ndarray, freq_hz: float, sr: int) -> float:
        n = len(frame)
        k = int(0.5 + (n * freq_hz) / sr)
        omega = (2.0 * np.pi * k) / n
        coeff = 2.0 * np.cos(omega)
        s_prev = 0.0
        s_prev2 = 0.0
        for x in frame:
            s = x + coeff * s_prev - s_prev2
            s_prev2, s_prev = s_prev, s
        return float(s_prev2**2 + s_prev**2 - coeff * s_prev * s_prev2)

    @staticmethod
    def _frame_energy(frame: np.ndarray) -> float:
        return float(np.mean(frame * frame) + 1e-12)

    def _tone_score(self, frame: np.ndarray, sr: int) -> float:
        # Average a tiny 3-bin band to tolerate slight drift
        p0 = self._goertzel_power(frame, self.cfg.tone_hz, sr)
        if self.cfg.tone_tol_hz > 0:
            p_lo = self._goertzel_power(
                frame, max(10.0, self.cfg.tone_hz - self.cfg.tone_tol_hz), sr
            )
            p_hi = self._goertzel_power(
                frame, self.cfg.tone_hz + self.cfg.tone_tol_hz, sr
            )
            p = (p_lo + p0 + p_hi) / 3.0
        else:
            p = p0
        e = self._frame_energy(frame)
        return float(p / (e + 1e-12))

    def _ensure_sr(self, audio: np.ndarray, sr: int) -> Tuple[np.ndarray, int]:
        if sr == self.cfg.sample_rate:
            return audio, sr
        if resample_poly is None:
            # Fallback: let Faster-Whisper resample internally; but accuracy is better if we resample here.
            return audio, sr
        # Resample to cfg.sample_rate using polyphase (good quality)
        from math import gcd

        g = gcd(sr, self.cfg.sample_rate)
        up = self.cfg.sample_rate // g
        down = sr // g
        out = resample_poly(audio, up, down).astype(np.float32)
        return out, self.cfg.sample_rate

    def split_file(
        self, wav_path: Path, save_dir: Optional[Path] = None
    ) -> Tuple[List[Path], List[Tuple[float, float, float]]]:
        """
        Returns (clip_paths, tone_runs)
        tone_runs: list of (start_s, end_s, duration_s) for detected tones
        """
        audio, sr = sf.read(str(wav_path), always_2d=False)
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)
        audio = audio.astype(np.float32)
        audio, sr = self._ensure_sr(audio, sr)

        frame = int(sr * self.cfg.frame_ms / 1000)
        hop = int(sr * self.cfg.hop_ms / 1000)
        n = len(audio)
        if n < frame:
            return [wav_path], []

        idxs = np.arange(0, n - frame + 1, hop, dtype=int)
        tone_mask = np.zeros(len(idxs), dtype=bool)

        # Score frames
        scores = np.empty(len(idxs), dtype=np.float32)
        for i, start in enumerate(idxs):
            fr = audio[start : start + frame]
            if np.max(np.abs(fr)) < self.cfg.amp_gate:
                scores[i] = 0.0
                continue
            scores[i] = self._tone_score(fr, sr)

        # Initial mask by threshold
        tone_mask = scores >= self.cfg.tone_score_thresh

        # Group consecutive tone frames into runs
        runs = []
        i = 0
        while i < len(tone_mask):
            if not tone_mask[i]:
                i += 1
                continue
            j = i + 1
            while j < len(tone_mask) and tone_mask[j]:
                j += 1
            runs.append((i, j))  # frame indices [i, j)
            i = j

        # Merge runs with tiny gaps (merge_gap_sec)
        merged = []
        merge_gap_frames = int(self.cfg.merge_gap_sec / (self.cfg.hop_ms / 1000.0))
        for k, (a0, a1) in enumerate(runs):
            if not merged:
                merged.append([a0, a1])
                continue
            b0, b1 = merged[-1]
            if a0 - b1 <= merge_gap_frames:
                merged[-1][1] = a1
            else:
                merged.append([a0, a1])

        # Convert to time and filter by tone duration
        tone_runs: List[Tuple[float, float, float]] = []
        for a0, a1 in merged:
            i0 = int(a0)
            i1 = int(a1) - 1

            start_s = float(idxs[i0]) / float(sr)
            end_s = float(idxs[i1] + frame) / float(sr)
            dur = float(end_s - start_s)
            if self.cfg.min_tone_sec <= dur <= self.cfg.max_tone_sec:
                tone_runs.append((start_s, end_s, dur))

        # Build dispatch clips between tones
        clips: List[Path] = []
        if save_dir:
            save_dir.mkdir(parents=True, exist_ok=True)

        for idx, (ts, te, _) in enumerate(tone_runs):
            start = te + self.cfg.post_tone_gap_sec
            if idx + 1 < len(tone_runs):
                end = max(start, tone_runs[idx + 1][0] - self.cfg.pre_next_tone_pad_sec)
            else:
                end = n / sr

            if (end - start) < self.cfg.min_dispatch_sec:
                continue

            s_idx = int(start * sr)
            e_idx = int(end * sr)
            clip = audio[s_idx:e_idx]

            if save_dir:
                out_path = save_dir / f"{wav_path.stem}.dispatch{idx+1}.wav"
            else:
                tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                out_path = Path(tmp.name)
                tmp.close()

            sf.write(str(out_path), clip, sr)
            clips.append(out_path)

        # If no tones detected, just pass the original through (single dispatch)
        if not clips:
            return [wav_path], tone_runs

        return clips, tone_runs


# ---------------------------
# Faster-Whisper runner
# ---------------------------


@dataclass
class WhisperConfig:
    model: str = os.getenv("EMBERLOG_WHISPER_MODEL", "large-v3")
    device: str = os.getenv(
        "EMBERLOG_WHISPER_DEVICE", "cuda"
    )  # "cuda" or "cpu"
    compute_type: str = os.getenv(
        "EMBERLOG_WHISPER_COMPUTE_TYPE", "float16"
    )  # e.g. float16, int8_float16
    beam_size: int = int(os.getenv("EMBERLOG_WHISPER_BEAM_SIZE", "10"))
    best_of: int = int(os.getenv("EMBERLOG_WHISPER_BEST_OF", "10"))
    temperature: float = float(os.getenv("EMBERLOG_WHISPER_TEMPERATURE", "0.0"))
    vad_filter: bool = bool(
        int(os.getenv("EMBERLOG_WHISPER_VAD_FILTER", "1"))
    )
    word_timestamps: bool = bool(
        int(os.getenv("EMBERLOG_WHISPER_WORD_TIMESTAMPS", "0"))
    )
    initial_prompt: Optional[str] = os.getenv(
        "EMBERLOG_WHISPER_INITIAL_PROMPT", None
    )
    condition_on_previous_text: bool = False
    no_speech_threshold: Optional[float] = None
    log_prob_threshold: Optional[float] = None
    compression_ratio_threshold: Optional[float] = None


class WhisperRunner:
    def __init__(self, cfg: WhisperConfig):
        self.cfg = cfg
        self.model = WhisperModel(
            cfg.model,
            device=cfg.device,
            compute_type=cfg.compute_type,
        )

    def transcribe_one(self, wav_path: Path) -> dict:
        segments, info = self.model.transcribe(
            str(wav_path),
            task="transcribe",
            vad_filter=self.cfg.vad_filter,
            beam_size=self.cfg.beam_size,
            best_of=self.cfg.best_of,
            temperature=self.cfg.temperature,
            word_timestamps=self.cfg.word_timestamps,
            initial_prompt=self.cfg.initial_prompt,
            condition_on_previous_text=self.cfg.condition_on_previous_text,
            no_speech_threshold=self.cfg.no_speech_threshold,
            log_prob_threshold=self.cfg.log_prob_threshold,
            compression_ratio_threshold=self.cfg.compression_ratio_threshold,
        )

        segs: list[dict] = []
        text_accum: list[str] = []
        for s in segments:
            seg: dict = {
                "start": float(s.start),
                "end": float(s.end),
                "text": s.text.strip(),
                "avg_logprob": float(getattr(s, "avg_logprob", 0.0)),
                "no_speech_prob": float(getattr(s, "no_speech_prob", 0.0)),
                "temperature": float(getattr(s, "temperature", self.cfg.temperature)),
            }

            words = getattr(s, "words", None)

            if self.cfg.word_timestamps and words:
                seg["words"] = [
                    {"start": float(w.start), "end": float(w.end), "word": w.word}
                    for w in words
                ]
            segs.append(seg)
            text_accum.append(seg["text"])

        return {
            "path": str(wav_path),
            "language": getattr(info, "language", "en"),
            "duration": float(getattr(info, "duration", 0.0)),
            "segments": segs,
            "text": " ".join(text_accum).strip(),
        }


# ---------------------------
# CLI / Orchestration
# ---------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Tone-split + Faster-Whisper transcriber for Emberlog."
    )
    p.add_argument(
        "wav", type=Path, help="Input WAV file (may contain 1..N dispatches)."
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=Path("./_toneclips"),
        help="Where to write dispatch clips.",
    )
    # Tone params
    p.add_argument(
        "--tone-freq", type=float, default=float(os.getenv("TONE_FREQ", 660.0))
    )
    p.add_argument(
        "--tone-min-sec", type=float, default=float(os.getenv("TONE_MIN_SEC", 1.8))
    )
    p.add_argument(
        "--tone-max-sec", type=float, default=float(os.getenv("TONE_MAX_SEC", 2.4))
    )
    p.add_argument(
        "--post-gap-ms", type=int, default=int(os.getenv("POST_TONE_GAP_MS", 700))
    )
    p.add_argument(
        "--score-thresh",
        type=float,
        default=float(os.getenv("TONE_SCORE_THRESH", 0.70)),
    )
    # Whisper params
    p.add_argument(
        "--model", default=os.getenv("EMBERLOG_WHISPER_MODEL", "large-v3")
    )
    p.add_argument(
        "--device", default=os.getenv("EMBERLOG_WHISPER_DEVICE", "cuda")
    )
    p.add_argument(
        "--compute-type",
        default=os.getenv("EMBERLOG_WHISPER_COMPUTE_TYPE", "float16"),
    )
    p.add_argument(
        "--beam-size",
        type=int,
        default=int(os.getenv("EMBERLOG_WHISPER_BEAM_SIZE", "10")),
    )
    p.add_argument(
        "--best-of",
        type=int,
        default=int(os.getenv("EMBERLOG_WHISPER_BEST_OF", "10")),
    )
    p.add_argument(
        "--temperature",
        type=float,
        default=float(os.getenv("EMBERLOG_WHISPER_TEMPERATURE", "0.0")),
    )
    p.add_argument(
        "--word-timestamps", action="store_true", help="Enable word-level timestamps."
    )
    p.add_argument(
        "--prompt",
        default=os.getenv("EMBERLOG_WHISPER_INITIAL_PROMPT", None),
        help="Initial prompt text.",
    )
    # Output
    p.add_argument(
        "--jsonl",
        type=Path,
        default=Path("./_results.jsonl"),
        help="Write per-dispatch JSON lines.",
    )
    return p


def main():
    ap = build_arg_parser()
    args = ap.parse_args()

    tone_cfg = ToneConfig(
        sample_rate=16000,
        tone_hz=args.tone_freq,
        min_tone_sec=args.tone_min_sec,
        max_tone_sec=args.tone_max_sec,
        post_tone_gap_sec=args.post_gap_ms / 1000.0,
        tone_score_thresh=args.score_thresh,
    )
    splitter = ToneSplitter(tone_cfg)

    print(
        f"[tone] file={args.wav} hz={tone_cfg.tone_hz} "
        f"min={tone_cfg.min_tone_sec}s max={tone_cfg.max_tone_sec}s gap={tone_cfg.post_tone_gap_sec:.3f}s"
    )

    clips, tone_runs = splitter.split_file(args.wav, save_dir=args.out_dir)
    if tone_runs:
        for i, (ts, te, dur) in enumerate(tone_runs, 1):
            print(f"[tone] #{i}: {ts:.2f}s → {te:.2f}s  dur={dur:.2f}s")
    else:
        print("[tone] no tones found — treating entire file as single dispatch")

    print(f"[split] produced {len(clips)} clip(s) in {args.out_dir}")

    wcfg = WhisperConfig(
        model=args.model,
        device=args.device,
        compute_type=args.compute_type,
        beam_size=args.beam_size,
        best_of=args.best_of,
        temperature=args.temperature,
        word_timestamps=bool(args.word_timestamps),
        initial_prompt=args.prompt or None,
    )
    runner = WhisperRunner(wcfg)

    with args.jsonl.open("w", encoding="utf-8") as jf:
        for i, clip in enumerate(clips, 1):
            res = runner.transcribe_one(clip)
            # Pretty print console summary
            print(f"\n[dispatch {i}] {clip.name}")
            print(f"text: {res['text']}")
            if res["segments"]:
                avg_lp = np.mean([s.get("avg_logprob", 0.0) for s in res["segments"]])
                print(f"segments={len(res['segments'])} avg_logprob={avg_lp:.3f}")
            # Write full JSON line
            out = {
                "index": i,
                "clip": str(clip),
                "tone_runs": tone_runs,  # repeated for convenience
                "transcript": res,
                "params": {
                    "whisper": asdict(wcfg),
                    "tone": asdict(tone_cfg),
                },
            }
            jf.write(json.dumps(out, ensure_ascii=False) + "\n")

    print(f"\n[done] JSONL written to {args.jsonl}")


if __name__ == "__main__":
    sys.exit(main())
