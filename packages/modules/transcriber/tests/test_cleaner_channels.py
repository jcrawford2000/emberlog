from __future__ import annotations

from pathlib import Path

from emberlog.cleaning.cleaner import clean_transcript
from emberlog.models import Transcript


def test_bare_k_channel_is_leading_bookend() -> None:
    # call_27361: whisper.cpp heard the leading "K-Deck 9" as "K-9"
    t = Transcript(
        audio_path=Path("/x/1795-1-call_27361.wav"),
        text="Engine 915, K-9, Hillperson, 6638, West Broadway Road. Engine 915, K-Deck 9.",
    )
    c = clean_transcript(t)
    assert c.units == ["Engine 915"]
    assert c.channel == "K-Deck 9"
    assert c.incident_type == "Ill person"
    assert c.address == "6638 W Broadway Rd"


def test_bare_deck_channel_is_leading_bookend() -> None:
    # call_27097: whisper.cpp heard the leading "K-Deck 8" as "Deck 8"
    t = Transcript(
        audio_path=Path("/x/1795-1-call_27097.wav"),
        text="Ladder Tender 33, Deck 8, Assault, 420 West Peoria Ave. Ladder Tender 33, K-Deck 8.",
    )
    c = clean_transcript(t)
    assert c.units == ["Ladder Tender 33"]
    assert c.channel == "K-Deck 8"
    assert c.incident_type == "Assault"
    assert c.address == "420 W Peoria Ave"
