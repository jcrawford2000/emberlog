from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from emberlog.transcriber import factory
from emberlog.transcriber.whisper_cpp import (
    WhisperCppConfig,
    WhisperCppTranscriber,
    _vad_min_silence_ms,
    strip_prompt_echo,
)

PROMPT = (
    "Phoenix metro fire dispatch. Terms: K-Deck, Battalion, Engine, Ladder, Ladder Tender, "
    "Rescue, Medic, HazMat. Spell out channels like 'K-Deck 10'."
)


def _cfg(**kw) -> WhisperCppConfig:
    base = {
        "server_url": "http://whisper.test",
        "timeout_s": 5.0,
        "language": "en",
        "beam_size": 5,
        "best_of": 8,
        "temperature": 0.0,
        "initial_prompt": PROMPT,
        "no_speech_threshold": 0.3,
        "log_prob_threshold": -1.2,
        "vad": True,
        "vad_min_silence_ms": 250,
    }
    base.update(kw)
    return WhisperCppConfig(**base)


def _transcriber(tmp_path: Path, handler) -> tuple[WhisperCppTranscriber, list[Path]]:
    """Build a transcriber with a mock HTTP transport and a fake (no-ffmpeg) trim."""
    trimmed: list[Path] = []

    def fake_trim(src: Path) -> Path:
        out = tmp_path / f"trim-{len(trimmed)}.wav"
        out.write_bytes(b"RIFFfake")
        trimmed.append(out)
        return out

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return WhisperCppTranscriber(_cfg(), client=client, trim=fake_trim), trimmed


def test_posts_audio_and_decoding_params(tmp_path: Path) -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = request.read()
        return httpx.Response(
            200,
            json={
                "text": "ignored when segments present",
                "language": "en",
                "duration": 12.5,
                "segments": [
                    {"start": 0.4, "end": 5.0, "text": " Engine 154. K-Deck 6."},
                    {"start": 5.2, "end": 11.9, "text": " Assault. Engine 154. K-Deck 6"},
                ],
            },
        )

    t, trimmed = _transcriber(tmp_path, handler)
    out = asyncio.run(t.transcribe(tmp_path / "1795-1-call_1.wav"))

    assert seen["url"] == "http://whisper.test/inference"
    body = seen["body"].decode(errors="ignore")
    for field, value in [
        ("response_format", "verbose_json"),
        ("beam_size", "5"),
        ("best_of", "8"),
        ("temperature_inc", "0.0"),
        ("no_speech_thold", "0.3"),
        ("vad", "true"),
        ("vad_min_silence_duration_ms", "250"),
    ]:
        assert f'name="{field}"\r\n\r\n{value}\r\n' in body
    assert "RIFFfake" in body

    assert out.text == "Engine 154. K-Deck 6. Assault. Engine 154. K-Deck 6"
    assert (out.start, out.end, out.duration_s) == (0.4, 11.9, 12.5)
    assert not trimmed[0].exists(), "trimmed temp file must be removed"


def test_segments_split_mid_word_are_rejoined(tmp_path: Path) -> None:
    # Real whisper.cpp output: a segment boundary inside "Cactus"/"Meadowbrook"
    segments = [
        {
            "start": 0.0,
            "end": 3.0,
            "text": " Ladder Tender 33, K-Deck 6. Overdose. 23rd Avenue and C",
        },
        {"start": 3.0, "end": 5.0, "text": "actus Road. Tender 33,"},
        {"start": 5.0, "end": 6.0, "text": " K-Deck 6."},
    ]
    t, _ = _transcriber(tmp_path, lambda r: httpx.Response(200, json={"segments": segments}))
    out = asyncio.run(t.transcribe(tmp_path / "x.wav"))
    assert out.text == (
        "Ladder Tender 33, K-Deck 6. Overdose. 23rd Avenue and Cactus Road. Tender 33, K-Deck 6."
    )


def test_400_is_treated_as_no_speech(tmp_path: Path) -> None:
    t, trimmed = _transcriber(tmp_path, lambda r: httpx.Response(400, text="Invalid request"))
    out = asyncio.run(t.transcribe(tmp_path / "short.wav"))
    assert out.text == ""
    assert not trimmed[0].exists()


def test_server_error_raises_for_worker_retry(tmp_path: Path) -> None:
    t, trimmed = _transcriber(tmp_path, lambda r: httpx.Response(500, text="boom"))
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(t.transcribe(tmp_path / "x.wav"))
    assert not trimmed[0].exists()


def test_falls_back_to_text_without_segments(tmp_path: Path) -> None:
    t, _ = _transcriber(tmp_path, lambda r: httpx.Response(200, json={"text": " Engine 9. "}))
    out = asyncio.run(t.transcribe(tmp_path / "x.wav"))
    assert out.text == "Engine 9."
    assert out.start is None and out.duration_s is None


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Spell out channels like 'K-Deck 5695' or 'K-Deck 119'.", ""),
        (
            "Engine 142, fire channel A10. Spell out channels like K-Deck 10.",
            "Engine 142, fire channel A10.",
        ),
        # Dispatch text that merely uses prompt vocabulary must be kept
        (
            "Ladder Tender 33 and Rescue 43, K-Deck 8. Chest pain.",
            "Ladder Tender 33 and Rescue 43, K-Deck 8. Chest pain.",
        ),
        ("", ""),
    ],
)
def test_strip_prompt_echo(text: str, expected: str) -> None:
    assert strip_prompt_echo(text, PROMPT) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("{'min_silence_duration_ms': 300}", 300),
        ('{"min_silence_duration_ms": 120}', 120),
        ("garbage", 250),
        (None, 250),
    ],
)
def test_vad_min_silence_parsing(raw, expected) -> None:
    assert _vad_min_silence_ms(raw) == expected


def test_factory_creates_whisper_cpp() -> None:
    assert isinstance(factory.create("whisper_cpp"), WhisperCppTranscriber)
