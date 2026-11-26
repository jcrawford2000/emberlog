from __future__ import annotations

from pathlib import Path

import pytest

from emberlog.cleaning.cleaner import (
    clean_transcript,
    fix_thousand_two,
    normalize_house_numbers,
)
from emberlog.models import Transcript


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Zero-padded thousands
        ("190817 West Amelia Avenue", "19817 West Amelia Avenue"),
        ("150638 South 13th Pl", "15638 South 13th Pl"),
        ("100610 West Windsor Avenue", "10610 West Windsor Avenue"),
        ("10000701 North 99th Avenue", "10701 North 99th Avenue"),
        ("1800626 North Spanish Garden Drive", "18626 North Spanish Garden Drive"),
        ("21000310 West Leisure Lane", "21310 West Leisure Lane"),
        # Hyphenated pieces
        ("1006-30 North 44th Street", "10630 North 44th Street"),
        ("24005-03 West Quayle Lane", "24503 West Quayle Lane"),
        ("48-54 South McMahon Court", "4854 South McMahon Court"),
        # Left alone
        ("19817 West Amelia Avenue", "19817 West Amelia Avenue"),
        ("227407 North 45th Place", "227407 North 45th Place"),
        ("I-17 North at Dunlap", "I-17 North at Dunlap"),
        ("C-232 West Royal Palm Road", "C-232 West Royal Palm Road"),
        ("Engine 2-7-8 Fire Channel A7", "Engine 2-7-8 Fire Channel A7"),
    ],
)
def test_normalize_house_numbers(text: str, expected: str) -> None:
    assert normalize_house_numbers(text)[0] == expected


def test_six_digit_house_number_is_split_from_incident_type() -> None:
    # call_26619: whisper.cpp wrote 19817 as "190817"
    t = Transcript(
        audio_path=Path("/x/1795-1-call_26619.wav"),
        text=(
            "Medic 327 and Engine 321. K-Deck 9. Difficulty breathing: 190817, "
            "West Amelia Avenue. Medic 327 and Engine 321. K-Deck 9."
        ),
    )
    c = clean_transcript(t)
    assert c.address == "19817 W Amelia Ave"
    assert c.incident_type is not None
    assert c.incident_type.lower() == "difficulty breathing"


def test_thousand_two_house_number() -> None:
    # call_26220, Maricopa 152: dispatcher said "ten thousand two eighteen"
    t = Transcript(
        audio_path=Path("/x/1795-1-call_26220.wav"),
        text=(
            "Special call: Maricopa 152, K-Deck 6. Injured person: 10000-18, "
            "North 66th Lane, Maricopa 152, K-Deck 6."
        ),
    )
    c = clean_transcript(t)
    assert c.address == "10218 N 66th Ln"
    assert c.incident_type == "Injured person"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("20000-21 North 29th Avenue", "20221 North 29th Avenue"),
        ("10,000 to 18, North 56th Lane", "10218, North 56th Lane"),
        ("16,000 to 20 West Tipatio Drive", "16220 West Tipatio Drive"),
        ("1000-18 East Main Street", "1218 East Main Street"),
        # Left alone
        ("Medic to 18 North", "Medic to 18 North"),
        ("10000701 North 99th Avenue", "10000701 North 99th Avenue"),
        ("24005-03 West Quayle Lane", "24005-03 West Quayle Lane"),
    ],
)
def test_fix_thousand_two(text: str, expected: str) -> None:
    assert fix_thousand_two(text)[0] == expected
