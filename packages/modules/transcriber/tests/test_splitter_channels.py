from __future__ import annotations

from pathlib import Path

import pytest

from emberlog.cleaning.cleaner import clean_transcript
from emberlog.models.transcript import Transcript
from emberlog.segmentation.splitter import Segment, correct_channels, split_transcript

P = Path("/data/emberlog/inbox/2026/11/23/1795-1795394061.967_769618750.0-call_226635.wav")


BRUSH_322 = (
    "Rush Engine 322. Fire Channel 813. Smoke. 411th Avenue and Bethany Home Road. "
    "Rush Engine 322. Fire Channel 813."
)
LADDER_TENDER_608 = (
    "Ladder tender 608. A channel way 11. Fire alarm indication. 10,160, East Cactus Road. "
    "Ladder tender 608. Fire channel way 11."
)


def _split(text: str):
    return split_transcript([Segment(start=0.0, end=15.0, text=text)], P)


# Real faster-whisper transcripts from calypso (2026-11-22) that produced no
# dispatch because the splitter couldn't see the misheard A channel.
@pytest.mark.parametrize(
    "text,channel",
    [
        (BRUSH_322, "A13"),
        (LADDER_TENDER_608, "A11"),
        ("Fire alarm indication. 2058 East Apache Blvd. Engine 2-7-8. Fire channel A-7.", "A7"),
    ],
)
def test_misheard_a_channel_dispatch_is_kept(text: str, channel: str) -> None:
    dispatches = _split(text)
    assert len(dispatches) == 1
    assert clean_transcript(Transcript(audio_path=P, text=dispatches[0].text)).channel == channel


def test_brush_engine_correction() -> None:
    result = clean_transcript(Transcript(audio_path=P, text=_split(BRUSH_322)[0].text))
    assert "Brush Engine 322" in result.units


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Fire Channel 813", "Fire Channel A13"),
        ("Fire Channel Way 6", "Fire Channel A6"),
        ("Fire channel A-7", "Fire Channel A7"),
        ("Fire Channel 8", "Fire Channel A8"),
        ("A channel way 11", "A channel A11"),
        ("Utility 20 A-10", "Utility 20 A10"),
        ("K-Deck 8", "K-Deck 8"),
    ],
)
def test_correct_channels(raw: str, expected: str) -> None:
    assert correct_channels(raw) == expected


def test_same_channel_in_different_forms_is_one_bookend() -> None:
    # "A11" then "Fire Channel A11" must close one dispatch, not open a second.
    assert (
        len(_split("Ladder Tender 608. A11. Fire alarm. Ladder Tender 608. Fire Channel A11.")) == 1
    )


def test_k_deck_dispatches_unchanged() -> None:
    text = (
        "Engine 154. K-Deck 6. Assault. 1234 West Main Street. Engine 154. K-Deck 6. "
        "Rescue 12. K-Deck 8. Fall injury. 500 East Camelback Road. Rescue 12. K-Deck 8."
    )
    assert [d.text.strip() for d in _split(text)] == [
        "Engine 154. K-Deck 6. Assault. 1234 West Main Street. Engine 154. K-Deck 6",
        "Rescue 12. K-Deck 8. Fall injury. 500 East Camelback Road. Rescue 12. K-Deck 8",
    ]


def test_unit_traffic_is_still_not_a_dispatch() -> None:
    assert (
        _split("Engine 40, you're clearing on channel 1. Please switch over to your channel.") == []
    )
