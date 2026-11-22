from __future__ import annotations

from pathlib import Path

import pytest

from emberlog.cleaning.cleaner import clean_transcript
from emberlog.models import Transcript


@pytest.mark.parametrize("sep", [":", ".", ","])
def test_cleaner_strips_trailing_punctuation_from_incident_type(sep: str) -> None:
    t = Transcript(
        audio_path=Path("/x/1795-1-call_1.wav"),
        text=f"Engine 154. K-Deck 6. Fall injury{sep} 27, North 32nd Lane. Engine 154. K-Deck 6",
    )
    c = clean_transcript(t)
    assert c.incident_type is not None
    assert c.incident_type.lower() == "fall injury"
    assert c.address == "27 N 32nd Ln"
