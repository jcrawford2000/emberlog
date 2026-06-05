# Pipeline Seam Review — Transcriber & Dispatch Parser

**Phase:** 1 (Review only — no code changes)
**Reviewer:** Blurryface (Claude Code, blackpearl)
**Commissioned by:** Clancy via Justin
**Date:** 2026-05-31

---

## Overview

The live pipeline has three logically distinct stages: **transcription**,
**splitting**, and **parsing**. This review maps each stage to its current
code, characterizes its I/O, identifies the boundaries between stages, and
assesses whether each can be called independently in-process from an eval
harness at `packages/eval/`.

---

## Stage 1 — Transcription

### Location

`packages/modules/transcriber/emberlog/transcriber/whisper_fast.py`
`packages/modules/transcriber/emberlog/transcriber/factory.py`
`packages/modules/transcriber/emberlog/transcriber/base.py`

The live pipeline also ships a **standalone dev tool** at
`packages/modules/transcriber/emberlog/utils/transcribe.py` that contains its
own `WhisperRunner` class and `ToneSplitter` (audio-based). This file is NOT
wired into the runtime pipeline; it is a self-contained CLI. It is catalogued
separately under Splitting below.

### Q1 — How is Whisper invoked?

`FasterWhisperTranscriber` is a pure Python class that holds a `WhisperModel`
in memory. Its public surface is:

```python
# whisper_fast.py:136
async def transcribe(self, path: Path) -> Transcript
```

Internally this calls `_do_transcribe(path)` via `asyncio.to_thread()` to keep
the event loop unblocked. There is no queue, no service process, no MQTT
connection, and no daemon thread required to invoke it. The class is
instantiated and called directly.

The runtime pipeline instantiates it via the factory:

```python
# factory.py:39-41
if name == "faster_whisper":
    from emberlog.transcriber.whisper_fast import FasterWhisperTranscriber
    return FasterWhisperTranscriber()
```

**Harness-callable today: YES.** No service dependency.

### Q2 — Where are Whisper parameters set? Can `initial_prompt` be injected per-call?

Parameters are defined in the `WhisperConfig` dataclass (`whisper_fast.py:49`).
All fields default to values drawn from `Settings` (a pydantic-settings class),
which reads from the `EMBERLOG_`-prefixed environment variables and a `.env`
file at `packages/modules/transcriber/.env`.

Relevant settings fields and their env var names:

| Field | Env var | Default |
|---|---|---|
| `whisper_model` | `EMBERLOG_WHISPER_MODEL` | `large-v3` |
| `whisper_device` | `EMBERLOG_WHISPER_DEVICE` | `cuda` |
| `whisper_compute_type` | `EMBERLOG_WHISPER_COMPUTE_TYPE` | `float16` |
| `whisper_vad_filter` | `EMBERLOG_WHISPER_VAD_FILTER` | `True` |
| `whisper_vad_parameters` | `EMBERLOG_WHISPER_VAD_PARAMETERS` | `{'min_silence_duration_ms': 250}` |
| `whisper_beam_size` | `EMBERLOG_WHISPER_BEAM_SIZE` | `5` |
| `whisper_language` | `EMBERLOG_WHISPER_LANGUAGE` | `en` |
| `whisper_best_of` | `EMBERLOG_WHISPER_BEST_OF` | `8` |
| `whisper_temperature` | `EMBERLOG_WHISPER_TEMPERATURE` | `0.0` |
| `whisper_initial_prompt` | `EMBERLOG_WHISPER_INITIAL_PROMPT` | Phoenix metro dispatch prompt (hardcoded string in config.py:58) |
| `whisper_no_speech_threshold` | `EMBERLOG_WHISPER_NO_SPEECH_THRESHOLD` | `0.3` |
| `whisper_log_prob_threshold` | `EMBERLOG_WHISPER_LOG_PROB_THRESHOLD` | `-1.2` |
| `whisper_compression_ratio_threshold` | `EMBERLOG_WHISPER_COMPRESSION_RATIO_THRESHOLD` | `2.8` |
| `whisper_word_timestamps` | `EMBERLOG_WHISPER_WORD_TIMESTAMPS` | `False` |

`initial_prompt` **can be injected per-call** by constructing an explicit
`WhisperConfig` and passing it to the transcriber constructor:

```python
cfg = WhisperConfig(initial_prompt="custom prompt here")
t = FasterWhisperTranscriber(cfg=cfg)
result = await t.transcribe(audio_path)
```

**Known gotcha:** `WhisperConfig` is a dataclass whose field defaults are
evaluated at **class definition time** from the module-level `settings =
get_settings()` object (`whisper_fast.py:51-88`). `get_settings()` is decorated
with `@lru_cache`, so the first import freezes the `Settings` instance. The
eval harness must either set env vars before importing this module, or pass
`WhisperConfig` with explicit field values to override the frozen defaults. The
latter is the cleaner path.

A second gotcha: importing `config.py` triggers `settings.inbox_dir.mkdir(...)`,
`outbox_dir.mkdir(...)`, and `ledger_path.parent.mkdir(...)` at module load
time (`config.py:87-89`), attempting to create `/data/emberlog/` directories.
This is a side effect of the module-level `settings = Settings()` instantiation
that runs unconditionally on import. The eval harness will need to either ensure
those paths are writable on blackpearl or set the env vars to redirect them to a
scratch directory before importing.

### Q3 — What does Whisper output?

`FasterWhisperTranscriber.transcribe()` returns a `Transcript` pydantic model
(`models/transcript.py:11`):

```python
class Transcript(BaseModel):
    audio_path: Path
    text: str          # joined segment texts (all segments collapsed to one string)
    start: float | None
    end: float | None
    duration_s: float | None
    language: str
    created_at: datetime
```

**Segments and confidence scores are discarded.** `_do_transcribe()` iterates
the faster-whisper segment generator (`whisper_fast.py:164-173`), accumulates
text strings, and joins them into a single `text` field. Neither
`avg_logprob`, `no_speech_prob`, per-segment timestamps, nor word-level data
are preserved in the returned `Transcript`.

The `Transcript` model has a `segments` attribute gated behind `hasattr` checks
in `_do_transcribe()` (`whisper_fast.py:195-197`), but the model definition does
NOT declare a `segments` field. The `hasattr` check never triggers meaningfully,
and `segments` is always set to `None` on the returned object.

**Net output:** raw text string + audio duration/language/timing bounds only.
No per-segment data reaches downstream stages.

Note: the standalone dev tool `utils/transcribe.py:WhisperRunner.transcribe_one()`
does return rich segment data (dict with `avg_logprob`, `no_speech_prob`,
`temperature`, optional word timestamps), but this is not used by the runtime
pipeline.

---

## Stage 2 — Splitting

There are **two distinct splitters** in the codebase with no shared ancestry.

### Splitter A — Text-based (live pipeline)

**Location:** `packages/modules/transcriber/emberlog/segmentation/splitter.py`

**Entry point:**
```python
def split_transcript(segments: Iterable[Segment], audio_path: Path) -> List[Dispatch]
```

**Called from:** `worker/consumer.py:131`

**Input:** `Iterable[Segment]` where `Segment` is a local dataclass:
```python
@dataclass
class Segment:
    start: float
    end: float
    text: str
```

In the live pipeline, the Worker synthesizes a **single** `Segment` from the
collapsed `Transcript.text` (`consumer.py:112-129`). Because `Transcript`
drops segments, the splitter never receives Whisper's natural segment
boundaries — it always operates on one long text blob.

**Output:** `List[Dispatch]`
```python
@dataclass
class Dispatch:
    audio_path: str
    text: str   # substring of the segment text
```

`Dispatch.text` is a substring of the input text delimited by the recognized
channel boundaries, not a separate audio clip or span reference.

**Q4 — Is the splitter a separable step?**

Yes. `split_transcript()` is a pure function (no I/O, no global state beyond
the compiled regex constants). It is importable and callable in isolation.
It is already a distinct step from parsing — it is called in the Worker before
`clean_transcript()` is ever invoked.

**Q5 — Current input/output summary:**

`Iterable[Segment]` (in practice, always a list of one) → `List[Dispatch]`
(substrings of the transcript text, one per detected dispatch boundary).

### Splitter B — Audio/tone-based (standalone dev tool)

**Location:** `packages/modules/transcriber/emberlog/utils/transcribe.py`

**Entry point:**
```python
def split_file(self, wav_path: Path, save_dir: Optional[Path] = None) -> Tuple[List[Path], List[Tuple[float, float, float]]]
```

Class: `ToneSplitter`, configured by `ToneConfig` dataclass.

**Input:** path to a WAV file.

**Output:** `(clip_paths, tone_runs)` where `clip_paths` is a list of paths to
WAV files written to disk (or tempfiles) and `tone_runs` is a list of
`(start_s, end_s, dur_s)` tuples for detected dispatch tones.

This splitter uses a Goertzel-algorithm tone detector to find 660 Hz dispatch
alert tones, then slices the audio at those boundaries. It writes clips to
disk and returns their paths. The CLI in `utils/transcribe.py:main()` then
passes those clip paths individually to `WhisperRunner.transcribe_one()`.

This splitter is **not wired into the live runtime pipeline** (`app/main.py`
and `worker/consumer.py` have no reference to it). It exists as a standalone
research/dev tool.

### Q6 — Why does `split_transcript()` under-split?

The text-based splitter keys on the pattern "the same channel string appears
twice consecutively." Phoenix Fire dispatch protocol voices the channel at the
start and at the end of each dispatch, so the expected pattern in a
two-dispatch recording is:

```
K-Deck 8 [content A] K-Deck 8 K-Deck 9 [content B] K-Deck 9
```

The algorithm (`splitter.py:76-105`) iterates `KDEC_RE` matches and uses
string equality on `occurance.group(0)` (the full match text) to detect the
"same channel repeated" condition. There are at least four independent reasons
it under-splits:

1. **Trailing dispatch is never emitted.** A dispatch boundary is only emitted
   inside the loop when the channel repeats. The text from `disp_start` to end
   of string after the last emitted boundary is never appended to `out`. In a
   recording with N dispatches, the final dispatch is silently dropped every
   time.

2. **Full-match string comparison is brittle.** `occurance.group(0)` is the
   raw matched text (e.g., `"K-Deck 8"` vs. `"K Deck 8"` vs. `"KDEC8"`).
   `KDEC_RE` accepts all of these forms, but the equality check `cur_chan !=
   occurance.group(0)` compares raw strings. Any Whisper transcription
   variation in the channel name prevents the "same channel repeated" condition
   from firing → the boundary is missed → the two dispatches are merged.

3. **Single-occurrence channels produce zero output.** If a dispatch's channel
   appears only once in the text (common for very short dispatches, or when
   Whisper drops one mention), the loop never sees a repeat and emits nothing
   for that dispatch.

4. **Segments are always collapsed to one.** Because `Transcript` discards
   Whisper's natural segment breaks, the Worker constructs `[Segment(text=full_text)]`
   and passes that single blob to `split_transcript()`. The splitter therefore
   can never benefit from segment timing even if the algorithm were fixed.

The 11:2 under-split ratio in the data is consistent with cause 1 (last
dispatch always dropped) combined with causes 2 and 3 (additional misses when
channel name varies or appears only once).

---

## Stage 3 — Parsing

### Location

`packages/modules/transcriber/emberlog/cleaning/cleaner.py`

### Q7 — Entry point and signature

```python
def clean_transcript(t: Transcript) -> CleanResult
```

**Input:** `Transcript` (pydantic model; requires `text: str` and
`audio_path: Path` — the other fields are unused by the parser).

**Output:** `CleanResult` dataclass:
```python
@dataclass
class CleanResult:
    text: str            # normalized transcript (replacements applied, whitespace collapsed)
    special_call: bool
    units: List[str]
    channel: Optional[str]
    incident_type: Optional[str]
    address: Optional[str]  # normalized address string
    stats: CleanStats
```

### Q8 — Is `incident_type` the fall-through sink?

**Yes, confirmed.** The extraction order in `clean_transcript()` (`cleaner.py:335-536`):

1. Apply normalization replacements (Italian→Battalion, K-Dec→K-Deck, etc.)
2. Strip punctuation, collapse whitespace
3. Check `^special call` prefix → `special_call` bool, remove prefix from working string `incident`
4. **Extract units** via `UNIT_PATTERNS` regexes → remove matched unit tokens from `incident`
5. **Extract channel** via `CHAN_RE` regex → remove from `incident`
6. **Extract address** (four cascading strategies):
   - 9xx incident code prefix pattern
   - `ADDR_RE` (number + compass + street name)
   - `INTERSECTION_RE` (street and/or street)
   - `FREEWAY_INTERSECTION_RE` (I-N at cross street)
   - Whatever text precedes the matched address span becomes `incident_type`
7. `incident_type = incident.strip()` — whatever remains after all the above

`incident_type` is strictly the fall-through remainder. It is not extracted by
any positive pattern; it is what's left after all other fields are peeled off.

The parser operates on the **dispatch-level text** (a `Dispatch.text` substring)
after splitting, so the per-field extraction happens independently on each
dispatch.

### Q9 — Does parser output conform to `dispatch.incident.created`?

**Not directly — there is a translation layer.** `CleanResult` is not the
event payload. The Worker bridges them in `consumer.py:169-188`:

```python
doc = {
    "source_audio": str(p),
    "dispatch_index": i,
    "dispatch_count": len(dispatches),
    "original_text": d.text,
    "dispatched_at": dispatched_at,
    "special_call": clean.special_call,
    "units": clean.units,
    "channel": clean.channel,
    "incident_type": clean.incident_type,
    "address": clean.address,   # clean.address is already the normalized string
    "cleaned_text": clean.text,
    ...
}
```

This `doc` dict is then passed to `ApiSink.write_api()`, which constructs
`IncidentIn` and posts to the REST API:

```python
incident = IncidentIn(
    dispatched_at=obj["dispatched_at"],
    special_call=obj["special_call"],
    units=obj["units"],
    channel=obj["channel"],
    incident_type=obj["incident_type"],
    address=obj["address"],
    original_text=obj["cleaned_text"],
    transcript=obj["cleaned_text"],
    ...
)
```

The API then stores the record and the SSE stream publishes a
`dispatch.incident.created` event. The canonical event envelope (with
`event_id`, `schema_version`, `source`, `payload`, etc.) is not produced by
the transcriber module at all — it is assembled at the API layer. The
transcriber's `ApiSink` only calls `POST /incidents/`, not a full event
envelope endpoint.

**Field-by-field conformance to EVENT_MODEL `dispatch.incident.created` payload:**

| EVENT_MODEL field | `CleanResult` field | Translation |
|---|---|---|
| `id` | — | Assigned by API on write |
| `dispatched_at` | — | Extracted from filename regex in Worker (`/1795-(\d+)`) |
| `special_call` | `clean.special_call` | Direct |
| `units` | `clean.units` | Direct |
| `channel` | `clean.channel` | Direct |
| `incident_type` | `clean.incident_type` | Direct |
| `address` | `clean.address` (normalized str) | Direct |
| `source_audio` | `str(p)` (audio path) | Direct |
| `original_text` | `clean.text` (normalized transcript) | Note: misleading — original_text is set to the *cleaned* text, not raw |
| `transcript` | `clean.text` | Same as original_text |
| `parsed` | `{}` (empty) | Hardcoded empty in ApiSink |
| `created_at` | `transcript.created_at` | Direct |

One data quality note: `original_text` in the API payload is set to
`clean.text` (the normalized transcript), not `d.text` (the raw dispatch text
before cleaning). The raw dispatch text is stored in `doc["original_text"]` at
worker level but then remapped to `cleaned_text` when constructing `IncidentIn`.
This means the API receives the cleaned text in both `original_text` and
`transcript` fields; the pre-normalization text is not stored in the API.

---

## Stage 4 — Seam / Refactor Assessment

### Q10 — Can the harness call each stage independently in-process today?

| Stage | Callable in-process today? | Notes |
|---|---|---|
| **(a) Transcribe audio** | **YES** | `FasterWhisperTranscriber(cfg).transcribe(path)` — pure in-process, no service needed |
| **(b) Split a transcript** | **YES** (text splitter) / **YES** (tone splitter) | Both are importable pure functions/classes. No external state. |
| **(c) Parse a dispatch** | **YES** | `clean_transcript(Transcript(...))` — pure function, no external state |

All three stages are reachable as library calls today. No running service, MQTT
connection, or API endpoint is required to invoke any of them.

### Q11 — What is the minimal refactor for clean seams?

The stages are already in separate files. The pipeline "shape" issue is not
fusion — it is a **broken data handoff between transcription and splitting**.

#### Critical gap: Whisper segments are discarded before reaching the splitter

`FasterWhisperTranscriber._do_transcribe()` iterates Whisper's segment
generator and joins the text, but does not preserve segments on `Transcript`
because `Transcript` has no `segments` field (`models/transcript.py`). The
Worker then constructs a single synthetic `Segment(text=full_transcript_text)`
for the splitter, losing all timing information.

Minimal fix to expose the seam properly:
1. Add `segments: Optional[List[dict]] = None` to `Transcript` in `models/transcript.py`
2. In `FasterWhisperTranscriber._do_transcribe()`, populate `segments` with at
   minimum `[{"start": s.start, "end": s.end, "text": s.text.strip()}]` per
   segment instead of setting it to `None`
3. Update `Worker.process()` to map `Transcript.segments` to `Seg` objects
   rather than synthesizing a single-element list

This makes the segment boundary data available without changing any external
API or behavior for the single-dispatch common case.

#### Splitter bug: trailing dispatch is never emitted

Independent of the segment issue, `split_transcript()` has a logic error where
the text from `disp_start` to end of string is never appended after the loop.
This is the single largest contributor to under-splitting (every multi-dispatch
file loses its last dispatch). Fixing this is a one-block addition after the
`for occurance in result:` loop, but it changes observable output and should
be treated as a behavior change, not just a refactor.

#### Splitting and parsing are already separable

`segmentation/splitter.py:split_transcript()` and
`cleaning/cleaner.py:clean_transcript()` are already separate functions in
separate modules. They are not fused. The Worker orchestrates them in sequence.
No separation work is needed here — only clean callable seams need to be exposed
at the harness level.

#### `initial_prompt` injection

Fully supported today: pass `WhisperConfig(initial_prompt="...")` to
`FasterWhisperTranscriber(cfg=cfg)`. No source edit needed.

#### Note on two splitter implementations

The codebase has two splitters that solve the same problem with different
strategies:

- `segmentation/splitter.py` — text-based, keys on repeated channel strings,
  used by the live pipeline
- `utils/transcribe.py:ToneSplitter` — audio-based, detects 660 Hz dispatch
  tones and slices the WAV, used only as a standalone CLI

These are currently independent and not composed. The audio-based approach is
architecturally more robust (it doesn't depend on Whisper transcribing channel
names correctly), but it produces audio clip files on disk as its output, which
would need to be passed back to `FasterWhisperTranscriber` for per-clip
transcription. The eval harness could exercise either or both.

### Q12 — Reverse-dependency risks, shared global state, service-only assumptions

**No reverse-dependency risk.** The transcriber package (`packages/modules/transcriber/`)
imports nothing from `packages/api/` or `packages/web/`. The dependency
direction is already `transcriber → API (network only)`. Eval at
`packages/eval/` importing from `packages/modules/transcriber/` maintains the
correct flow.

**Global state — `@lru_cache` on `get_settings()`:**
`config.py:92-94` wraps `get_settings()` with `@lru_cache`. First import
freezes `Settings`. The eval harness must set `EMBERLOG_*` env vars before
any import from `emberlog.config.config`, or explicitly construct
`WhisperConfig`/`Settings` with override values. Passing explicit config
objects to the constructors is the cleaner approach.

**Side effect on import — directory creation:**
`config.py:87-89` runs unconditionally at module load:
```python
settings.inbox_dir.mkdir(parents=True, exist_ok=True)   # /data/emberlog/inbox
settings.outbox_dir.mkdir(parents=True, exist_ok=True)   # /data/emberlog/outbox
settings.ledger_path.parent.mkdir(parents=True, exist_ok=True)
```
Importing anything from `emberlog.config.config` (directly or transitively)
will attempt to create these directories on blackpearl. Set
`EMBERLOG_INBOX_DIR`, `EMBERLOG_OUTBOX_DIR`, and `EMBERLOG_LEDGER_PATH` to
writable scratch paths before importing if `/data/emberlog/` is not available.

**No MQTT dependency in transcriber core.** None of the three pipeline stages
(transcribe/split/parse) reference MQTT, the API, or any network service.
MQTT is only in `packages/api/emberlog_api/app/services/mqtt_consumer.py`,
which is a separate package.

**`ApiSink` requires a running API, but eval will not use it.** The `Worker`
conditionally includes `ApiSink` (`consumer.py:61-64`), but calling the three
pipeline functions directly bypasses the Worker and its sinks entirely.

**`ffmpeg` must be on PATH.** `FasterWhisperTranscriber._trim_dispatch_tones()`
calls `ffmpeg` as a subprocess (`whisper_fast.py:116-130`). The harness needs
`ffmpeg` installed on blackpearl. If ffmpeg is absent, transcription will
raise `FileNotFoundError` before Whisper is invoked.

---

## Recommended Phase 2 Shape

### Transcription stage
**Call directly.** `FasterWhisperTranscriber` is harness-callable today.

Recommended eval invocation:
```python
from emberlog.transcriber.whisper_fast import FasterWhisperTranscriber, WhisperConfig

cfg = WhisperConfig(
    model_name="large-v3",
    device="cuda",     # or "cpu" for blackpearl if no GPU
    initial_prompt="...",   # inject per run
)
transcriber = FasterWhisperTranscriber(cfg=cfg)
transcript = await transcriber.transcribe(Path("audio.wav"))
# transcript.text: str — full transcript
```

Pre-condition: set `EMBERLOG_INBOX_DIR` etc. before import, or ensure
`/data/emberlog/` is writable. `ffmpeg` must be on PATH.

### Splitting stage
**Call directly — but note the two implementations.**

Text-based (live pipeline):
```python
from emberlog.segmentation.splitter import Segment, split_transcript

segments = [Segment(start=0.0, end=duration, text=transcript.text)]
dispatches = split_transcript(segments, audio_path)
# dispatches: List[Dispatch] — each .text is a dispatch substring
```

Audio-based (dev tool, more robust):
```python
from emberlog.utils.transcribe import ToneSplitter, ToneConfig

splitter = ToneSplitter(ToneConfig())
clips, tone_runs = splitter.split_file(Path("audio.wav"), save_dir=Path("/tmp/clips"))
# clips: List[Path] — each is a wav file for one dispatch
```

For eval fidelity, run the text splitter against the same transcript the live
pipeline receives. Optionally also run the tone splitter to measure whether
audio-based splitting reduces under-split errors.

**Extract function first (recommended before Phase 2 eval):** The trailing
dispatch bug in `split_transcript()` should be confirmed and the fix reviewed
before tuning any harness around it — otherwise the eval will be measuring
behavior that is already known-wrong.

### Parsing stage
**Call directly.**

```python
from emberlog.cleaning.cleaner import clean_transcript
from emberlog.models.transcript import Transcript

t = Transcript(audio_path=Path("audio.wav"), text=dispatch_text)
result = clean_transcript(t)
# result.special_call: bool
# result.units: List[str]
# result.channel: Optional[str]
# result.incident_type: Optional[str]
# result.address: Optional[str]
```

No extraction or wrapper needed. `clean_transcript()` is already the clean
callable seam.

### Recommended pre-Phase-2 changes (minimal, behavior-preserving unless noted)

| Item | File | Type | Notes |
|---|---|---|---|
| Add `segments` field to `Transcript` | `models/transcript.py` | Additive | Enables segment-aware splitting |
| Populate segments in `_do_transcribe` | `whisper_fast.py` | Additive | Store `[{start, end, text}]` instead of None |
| Fix trailing dispatch drop | `segmentation/splitter.py:105` | Bug fix | Append `text[disp_start:]` after loop; behavior change |
| Resolve two-splitter ambiguity | Architecture decision | — | Decide which splitter the pipeline uses; currently they don't compose |

---

*End of Phase 1 seam review. No code was changed. Only `packages/eval/SEAM_REVIEW.md` was created.*
