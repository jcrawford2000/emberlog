from __future__ import annotations

import json
from pathlib import Path

import pytest

from emberlog.cleaning.cleaner import _VOCAB
from emberlog.cleaning.vocab_loader import match_incident_type

REGION = Path(__file__).resolve().parents[1] / "regions" / "phoenix-regional"


def test_incident_type_phrases_have_no_stray_whitespace() -> None:
    data = json.loads((REGION / "incident_types.json").read_text())
    bad = [
        item.get("code")
        for item in data["incident_types"]
        for phrase in [item.get("canonical_phrase", ""), *item.get("aliases", [])]
        if phrase != phrase.strip()
    ]
    assert bad == []


@pytest.mark.parametrize(
    ("residual", "canonical", "code"),
    [
        ("Fall Injury", "Fall injury", "FALL"),
        ("Difficulty breathing", "Difficulty breathing", "DB"),
        ("Seizure", "Seizure", "SEIZ"),
    ],
)
def test_common_incident_types_match(residual: str, canonical: str, code: str | None) -> None:
    match = match_incident_type(residual, _VOCAB)
    assert match is not None
    assert match[0] == canonical
    if code:
        assert match[1] == code
