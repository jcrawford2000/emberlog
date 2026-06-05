# Emberlog Eval Harness

Measures the real transcriber → splitter → parser pipeline against a frozen
ground-truth corpus, attributing failures to the correct stage.

This is a **dev/eval tool only**. It deploys nowhere. Dependency direction is
strictly `eval → components`, never the reverse.

---

## Files

| File | Role |
|---|---|
| `bootstrap.py` | Env setup — **must be imported first** |
| `normalize.py` | Single normalization source (scorer + runner both import this) |
| `runner.py` | GPU pipeline runner → `system_output.json` + `manifest.json` |
| `scorer.py` | Pure scorer → three tables + `metrics.json` + `failures.csv` |
| `smoke_test.py` | No-GPU correctness test for scorer logic |
| `corpus/corpus.json` | Frozen ground truth — never edit this to improve a number |
| `baseline_metrics.json` | Reference metrics from the first clean baseline run |

---

## CRITICAL: Import ordering requirement

`emberlog.config.config` runs side effects at module load:
- Creates `/data/emberlog/{inbox,outbox}` directories
- Freezes `get_settings()` via `@lru_cache`

**`bootstrap.setup()` must execute before any `emberlog.*` import.**

`runner.py` handles this automatically when invoked as a script. If you write
any script that imports runner, put this at the top:

```python
import bootstrap
bootstrap.setup(workspace=Path("/tmp/my_scratch"))
# Now safe to import emberlog modules
from emberlog.transcriber.whisper_fast import ...
```

The runner also checks that `ffmpeg` is on PATH and exits with a clear error
if it is not (the transcriber shells out to ffmpeg for tone trimming).

---

## Corpus format

`corpus/corpus.json` has the shape produced by the labeling tool:

```json
{
  "_meta": { ... },
  "clips": [
    {
      "audio_ref": "1795-1780086990...-call_76187",
      "audio_filename": "1795-1780086990...-call_76187.wav",
      "audio_quality": "ok",
      "system_output": { ... },
      "verified": {
        "transcript": "Special Call Rescue 74 K-Deck 8 Fall Injury 420 East South Fork Drive Rescue 74 K-Deck 8 Engine 2840 K-Deck 7 Fall Injury ...",
        "expected_dispatch_count": 2,
        "dispatches": [
          {
            "dispatch_transcript": "Special Call Rescue 74 K-Deck 8 Fall Injury 420 East South Fork Drive Rescue 74 K-Deck 8",
            "special_call": true,
            "units": ["Rescue 74"],
            "channel": "K-Deck 8",
            "incident_type": "Fall Injury",
            "address": "420 E South Fork Dr"
          }
        ],
        "notes": ""
      }
    }
  ]
}
```

`corpus_io.load_corpus()` normalizes this into the internal record format used
by both runner and scorer. It also tolerates a bare array of flat records.

### The two-field transcript model

There are **two** distinct transcript fields with different jobs. They are
never interchangeable:

| Field | Location | Used for |
|---|---|---|
| `verified.transcript` | clip level | **WER truth only.** One acoustic utterance. Includes preambles, `[unintelligible]` sentinels. Scored ONCE per clip against the system's Whisper output. |
| `verified.dispatches[i].dispatch_transcript` | per dispatch | **Parser feed only** in parser-isolated mode. The clean, single-dispatch span passed to `clean_transcript`. Never used for WER. |

Critical consequences:
- Per-dispatch transcripts are NOT required to concatenate back to the clip
  transcript. Don't assume they do.
- On single-dispatch clips the two fields often contain identical text. That
  coincidence is fine — same words, different roles.
- If `dispatch_transcript` is missing or empty on a multi-dispatch clip, that
  dispatch is **excluded from parse scoring** and counted as skipped — never
  zero-scored. The `metrics.json` reports `skipped_dispatches: N`.

`audio_quality` values: `"ok"` or `"unintelligible"`. Unintelligible clips are
excluded from the headline WER and parsing tables; they are counted and
reported separately.

**The corpus is frozen truth. Never edit it to make a number look better —
that is a finding, not a fix.**

---

## Running the harness

### Prerequisites

- GPU node (blackpearl) with CUDA, or set `--device cpu` for CPU fallback
- `ffmpeg` on PATH: `sudo apt-get install ffmpeg`
- Python env with the transcriber package installed:
  `cd packages/modules/transcriber && pip install -e .`

### Step 0: Smoke test (no GPU required)

Verifies scorer logic before running any real audio.

```bash
cd packages/eval
python smoke_test.py
```

All tests should pass. If they do not, the scoring diff logic is broken —
do not trust any numbers from the harness until this is green.

### Step 1: End-to-end run (text splitter)

```bash
python runner.py \
  --corpus   corpus/corpus.json \
  --audio-dir /path/to/audio \
  --out-dir  runs/baseline_text \
  --mode     end-to-end \
  --strategy text \
  --device   cuda \
  --model    large-v3
```

### Step 2: Score

```bash
python scorer.py \
  --corpus   corpus/corpus.json \
  --output   runs/baseline_text/system_output.json \
  --metrics  runs/baseline_text/metrics.json \
  --failures runs/baseline_text/failures.csv
```

### Step 3: End-to-end run (tone splitter) and score

```bash
python runner.py \
  --corpus   corpus/corpus.json \
  --audio-dir /path/to/audio \
  --out-dir  runs/baseline_tone \
  --mode     end-to-end \
  --strategy tone \
  --device   cuda \
  --model    large-v3

python scorer.py \
  --corpus   corpus/corpus.json \
  --output   runs/baseline_tone/system_output.json \
  --metrics  runs/baseline_tone/metrics.json \
  --failures runs/baseline_tone/failures.csv
```

### Step 4: Isolation modes

**Parser-isolated** (highest diagnostic value — answers "is the parser broken
or just fed garbage from upstream?"):

```bash
python runner.py \
  --corpus   corpus/corpus.json \
  --audio-dir /path/to/audio \
  --out-dir  runs/parser_isolated \
  --mode     parser-isolated

python scorer.py \
  --corpus   corpus/corpus.json \
  --output   runs/parser_isolated/system_output.json \
  --metrics  runs/parser_isolated/metrics.json
```

The gap between `parser-isolated` field accuracy and `end-to-end` field
accuracy quantifies how much parse failure is actually transcription failure.

**Splitter-isolated (text):**

```bash
python runner.py \
  --corpus   corpus/corpus.json \
  --audio-dir /path/to/audio \
  --out-dir  runs/split_isolated_text \
  --mode     splitter-isolated \
  --strategy text

python scorer.py \
  --corpus   corpus/corpus.json \
  --output   runs/split_isolated_text/system_output.json \
  --metrics  runs/split_isolated_text/metrics.json
```

**Splitter-isolated (tone):**

```bash
python runner.py \
  --corpus   corpus/corpus.json \
  --audio-dir /path/to/audio \
  --out-dir  runs/split_isolated_tone \
  --mode     splitter-isolated \
  --strategy tone

python scorer.py \
  --corpus   corpus/corpus.json \
  --output   runs/split_isolated_tone/system_output.json \
  --metrics  runs/split_isolated_tone/metrics.json
```

---

## Stage-isolation modes

| Mode | What runs | What is scored |
|---|---|---|
| `end-to-end` | audio → Whisper → split → parse | splitting, WER, all fields |
| `parser-isolated` | truth transcripts → parse | field accuracy only |
| `splitter-isolated` | truth transcripts → split count (text); audio → tone detect → count (tone) | split count only |

---

## Workflow: baseline → gated fixes

This harness enforces a discipline. Follow it.

### 1. Establish baseline first

Before any pipeline fix, run all four combinations and commit the results:

```bash
# text end-to-end
# tone end-to-end
# parser-isolated
# splitter-isolated (text and tone)
```

Commit `runs/baseline_*/metrics.json` as `baseline_metrics.json` (one per
run). These are the reference all future fixes are measured against.

### 2. One fix at a time, each gated

For every change in `TASK_fix_list.md`:

1. Branch off `main`
2. Apply the single fix
3. Re-run the harness (same modes + both strategies)
4. Diff `metrics.json` vs baseline:

```bash
diff <(python -m json.tool baseline_metrics.json) \
     <(python -m json.tool runs/fix_foo/metrics.json)
```

A fix is accepted only if it improves its target metric AND regresses nothing
else (or the regression is understood and explicitly accepted). Record the
before/after diff in the PR description.

### 3. No blind "obviously correct" commits

The trailing-dispatch bug (`split_transcript()` drops the last dispatch every
time) is obviously correct to fix. It must still be measured. If the harness
cannot show the improvement, the fix does not merge.

### 4. Diffable metrics

`metrics.json` schema is stable so two runs diff cleanly:

```
split 83%→92%, address 62%→64%, WER 15.7%→15.5%
```

---

## Failures report

`failures.csv` has one row per dispatch, sorted worst-first by severity
(missed fields × 10 + WER). Columns:

| Column | Description |
|---|---|
| `audio_ref` | Audio file identifier |
| `dispatch_index` | Which dispatch within that audio (0-based) |
| `split_correct` | Whether the expected dispatch count matched |
| `audio_quality` | `ok` or `unintelligible` |
| `wer` | Word error rate % for this dispatch |
| `missed_fields` | Pipe-separated list of fields that didn't match |
| `produced_transcript` | What the system produced |
| `truth_transcript` | Ground truth |

The aggregate tables say "something regressed." This file says which clip and why.

---

## Manifest

Every runner invocation writes `manifest.json` alongside `system_output.json`.
A run without a manifest is unattributable — do not commit results without one.

```json
{
  "timestamp": "2026-06-01T12:00:00+00:00",
  "mode": "end-to-end",
  "splitter_strategy": "text",
  "model_name": "large-v3",
  "device": "cuda",
  "compute_type": "float16",
  "initial_prompt_hash": "sha256:abc123...",
  "parser": "clean_transcript",
  "git_commit": "d0848c1",
  "ffmpeg_version": "ffmpeg version 6.0",
  "corpus_hash": "sha256:def456..."
}
```

---

## Context (findings, not targets)

First manual 81-clip pass: splitting 83% (11 under / 2 over; ~22% multi-dispatch
audio); WER ~16%; fields special_call 97% / channel 99% / units 87% /
incident_type 65% / address 62%.

Known cause of the 11 under-splits: `split_transcript()` drops the trailing
dispatch on every multi-dispatch recording (the algorithm only emits a dispatch
when a channel repeats, so the final dispatch after the last boundary is
silently lost). This is tracked in `TASK_fix_list.md` and will be fixed
post-baseline, gated by this harness.

The tone splitter's inaccuracy reputation is unverified and stale. Run both
strategies and compare. Do not assume either is the winner before the numbers exist.
