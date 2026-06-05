"""
Region vocab loader for the dispatch parser.

Reads a region adapter directory (manifest.json + vocabulary JSON files) and
returns a compiled Vocab object. Call load_vocab() once at module level; the
parser depends on one Vocab instance, not individual file paths.

Swapping regions = swap the directory. No code change.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_DEFAULT_REGION_DIR = (
    Path(__file__).parent.parent.parent / "regions" / "phoenix-regional"
)


# ---------------------------------------------------------------------------
# Compiled Vocab container
# ---------------------------------------------------------------------------


@dataclass
class Vocab:
    region_id: str = ""

    # Unit patterns: (compiled_re, canonical_type, requires_number)
    # Pre-sorted longest-pattern-first (longest-match semantics).
    # regex captures the NUMBER in group(1) for requires_number=True entries.
    unit_patterns: list = field(default_factory=list)

    # Channel: compiled regex with three positional groups (k_num, a_num, b_num)
    channel_re: Optional[re.Pattern] = None

    # Dispatch actions: (compiled_re, action_str, is_supplement)
    # Sorted longest-phrase-first; each regex is anchored to start of string (^).
    dispatch_action_patterns: list = field(default_factory=list)

    # Response modifiers: (compiled_re, parsed_key, parsed_value)
    modifier_patterns: list = field(default_factory=list)

    # Incident types: sorted longest-phrase-first for longest-match.
    # Each entry: {"code", "canonical_phrase", "is_stem", "qualifiers", "_all_phrases"}
    # _all_phrases = [(phrase, code)] sorted longest-first.
    incident_type_entries: list = field(default_factory=list)

    # Freeway: compiled alternation of all aliases (longest-first)
    freeway_re: Optional[re.Pattern] = None

    # Named interchanges: compiled alternation (longest-first)
    interchange_re: Optional[re.Pattern] = None

    # ASR corrections by stage: {stage: [(compiled_re, replacement_str)]}
    asr_corrections: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def load_vocab(region_dir: Optional[Path] = None) -> Vocab:
    """Load and compile a region adapter directory into a Vocab object."""
    if region_dir is None:
        env_dir = os.environ.get("EMBERLOG_REGION_DIR")
        region_dir = Path(env_dir) if env_dir else _DEFAULT_REGION_DIR

    region_dir = Path(region_dir)
    if not region_dir.is_dir():
        raise FileNotFoundError(
            f"Region directory not found: {region_dir}\n"
            "Set EMBERLOG_REGION_DIR to point to a valid region adapter directory."
        )

    manifest = json.loads((region_dir / "manifest.json").read_text())
    files = manifest["files"]

    def _load(key: str) -> dict:
        return json.loads((region_dir / files[key]).read_text())

    vocab = Vocab(region_id=manifest["region_id"])
    _load_unit_types(vocab, _load("unit_types"))
    _load_channels(vocab, _load("channels"))
    _load_dispatch_actions(vocab, _load("dispatch_actions"))
    _load_response_modifiers(vocab, _load("response_modifiers"))
    _load_incident_types(vocab, _load("incident_types"))
    _load_freeways(vocab, _load("freeways"))
    _load_asr_corrections(vocab, _load("asr_corrections"))
    return vocab


# ---------------------------------------------------------------------------
# Per-category builders
# ---------------------------------------------------------------------------


def _load_unit_types(vocab: Vocab, data: dict) -> None:
    entries = [e for e in data.get("unit_types", []) if "type" in e]

    # Sort by canonical pattern length descending — longest-match semantics.
    entries.sort(key=lambda e: -len(e["pattern"]))

    patterns = []
    for entry in entries:
        canonical_type = entry["type"]
        pat_text = entry["pattern"]
        aliases = [a for a in entry.get("aliases", []) if a]
        requires_number = entry["requires_number"]

        # Detect LA-hyphen style ("LA-" alias means hyphen is a separator)
        la_style = any(a.endswith("-") for a in aliases)
        clean_aliases = [a.rstrip("-") for a in aliases]
        all_prefixes = [pat_text] + clean_aliases

        # Escape and build alternation
        alts = "|".join(re.escape(p) for p in all_prefixes)

        if requires_number:
            if la_style:
                # Allow optional hyphen OR space before the number
                pat = re.compile(rf"\b(?:{alts})[-\s]?(\d{{1,4}})\b", re.I)
            else:
                pat = re.compile(rf"\b(?:{alts})\s*(\d{{1,4}})\b", re.I)
        else:
            pat = re.compile(rf"\b(?:{alts})\b", re.I)

        patterns.append((pat, canonical_type, requires_number))

    vocab.unit_patterns = patterns


def _load_channels(vocab: Vocab, data: dict) -> None:
    """Build a single channel regex with three positional groups (K, A, B)."""
    # group(1): K-Deck number
    # group(2): A-channel number
    # group(3): Mesa-B channel number
    vocab.channel_re = re.compile(
        r"""
        (?:
            K[- ]?De(?:ck|c)?\s*(\d{1,2})              # K-Deck family   → group(1)
            |
            (?:Fire\s*Channel\s*)?A\s*(\d{1,2})\b       # A-channel family → group(2)
            |
            (?:Mesa\s*(?:Fire\s*Channel\s*)?)B(\d{1,2})\b  # Mesa-B family → group(3)
        )
        """,
        re.I | re.VERBOSE,
    )
    vocab._channel_families = data.get("families", [])


def _load_dispatch_actions(vocab: Vocab, data: dict) -> None:
    actions = data.get("actions", [])
    # Sort longest phrase first for longest-match
    actions_expanded = []
    for act in actions:
        for phrase in act.get("phrases", []):
            actions_expanded.append((phrase, act["action"], act.get("is_supplement", False)))
    actions_expanded.sort(key=lambda x: -len(x[0]))

    patterns = []
    for phrase, action, is_supplement in actions_expanded:
        pat = re.compile(rf"^(?:{re.escape(phrase)})\b", re.I)
        patterns.append((pat, action, is_supplement))
    vocab.dispatch_action_patterns = patterns


def _load_response_modifiers(vocab: Vocab, data: dict) -> None:
    patterns = []
    for mod in data.get("modifiers", []):
        token = mod["token"]
        aliases = mod.get("aliases", [])
        all_forms = [token] + aliases
        # Build alternation, longest first
        all_forms.sort(key=len, reverse=True)
        alts = "|".join(re.escape(f) for f in all_forms)
        pat = re.compile(rf"\b(?:{alts})\b", re.I)
        patterns.append((pat, mod["parsed_key"], mod["parsed_value"]))
    vocab.modifier_patterns = patterns


def _load_incident_types(vocab: Vocab, data: dict) -> None:
    entries = []
    for item in data.get("incident_types", []):
        if "canonical_phrase" not in item:
            continue  # skip comment-only entries
        canonical = item["canonical_phrase"]
        code = item.get("code", "")
        is_stem = item.get("is_stem", False)
        aliases = item.get("aliases", [])
        qualifiers = item.get("qualifiers", [])

        # Build the full list of (phrase, effective_code) pairs, longest first
        all_phrases = [(canonical, code)] + [(a, code) for a in aliases]

        if is_stem and qualifiers:
            # Add "stem qualifier_phrase" as longer alternatives
            for q in qualifiers:
                full_phrase = f"{canonical} {q['phrase']}"
                all_phrases.append((full_phrase, q["code"]))

        all_phrases.sort(key=lambda x: -len(x[0]))

        entries.append(
            {
                "canonical_phrase": canonical,
                "code": code,
                "is_stem": is_stem,
                "qualifiers": qualifiers,
                "all_phrases": all_phrases,
            }
        )

    # Sort the type entries by canonical phrase length descending (outer longest-match)
    entries.sort(key=lambda e: -len(e["canonical_phrase"]))
    vocab.incident_type_entries = entries


def _load_freeways(vocab: Vocab, data: dict) -> None:
    all_aliases: list[str] = []
    for fw in data.get("freeways", []):
        for alias in fw.get("aliases", []):
            all_aliases.append(alias)

    interchanges: list[str] = []
    for ic in data.get("named_interchanges", []):
        interchanges.append(ic["name"])

    if all_aliases:
        # Longest-first to prevent "I-1" matching before "I-10"
        all_aliases.sort(key=len, reverse=True)
        alts = "|".join(re.escape(a) for a in all_aliases)
        vocab.freeway_re = re.compile(rf"\b(?:{alts})\b", re.I)

    if interchanges:
        interchanges.sort(key=len, reverse=True)
        alts = "|".join(re.escape(ic) for ic in interchanges)
        vocab.interchange_re = re.compile(rf"\b(?:{alts})\b", re.I)


def _load_asr_corrections(vocab: Vocab, data: dict) -> None:
    by_stage: dict[str, list] = {}
    for corr in data.get("corrections", []):
        stage = corr["stage"]
        pat = re.compile(corr["pattern"], re.I)
        repl = corr["replacement"]
        by_stage.setdefault(stage, []).append((pat, repl))
    vocab.asr_corrections = by_stage


# ---------------------------------------------------------------------------
# Matching helpers (used by cleaner)
# ---------------------------------------------------------------------------


def match_incident_type(residual: str, vocab: Vocab) -> Optional[tuple[str, str]]:
    """
    Try to match `residual` against the incident type vocabulary.

    Returns (canonical_phrase, code) if a match is found, else None.
    Longest match wins: qualifiers beat bare stems, longer phrases beat shorter.
    Matching is case-insensitive on the trimmed residual.
    """
    r = residual.strip().lower()
    if not r:
        return None

    def _output_phrase(entry: dict, phrase: str, code: str) -> str:
        # For qualifier / alias forms, return the matched phrase so callers get
        # "962 involving pedestrian" rather than just the stem "962".
        # For canonical and alias matches that share the entry code, return canonical.
        return phrase if code != entry["code"] else entry["canonical_phrase"]

    # First pass: exact match (longest phrases are tried first via sort in loader)
    for entry in vocab.incident_type_entries:
        for phrase, code in entry["all_phrases"]:
            if r == phrase.lower():
                return _output_phrase(entry, phrase, code), code

    # Second pass: prefix match (residual STARTS WITH the phrase, word-boundary after)
    for entry in vocab.incident_type_entries:
        for phrase, code in entry["all_phrases"]:
            pl = phrase.lower()
            if r.startswith(pl) and (len(r) == len(pl) or not r[len(pl) : len(pl) + 1].isalpha()):
                return _output_phrase(entry, phrase, code), code

    return None
