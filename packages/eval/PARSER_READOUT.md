# Parser Readout: `clean_transcript` Logic & Vocab Inventory

**Prepared by:** Blurryface (Claude Code, on tortuga)  
**For:** Clancy + Justin — Fix 4 spec finalization  
**Date:** 2026-06-04  
**Source examined:** `packages/modules/transcriber/emberlog/cleaning/cleaner.py` (all 537 lines)  
**Reference:** `docs/EVENT_MODEL_v0.2.md`, `packages/modules/transcriber/phoenix_dispatch_vocab.json`

---

## Section A — Field-Extraction Walkthrough

### Fields produced

`CleanResult` (the dataclass returned by `clean_transcript`) has these fields:

| Field | Type | Notes |
|---|---|---|
| `text` | `str` | The normalized transcript (after REPLACEMENTS + whitespace collapse) |
| `special_call` | `bool` | True if transcript starts with "special call" |
| `units` | `List[str]` | All matched unit strings, titlecased, deduped |
| `channel` | `Optional[str]` | e.g. `"K-Deck 8"` or `"A5"` — None if unrecognized |
| `incident_type` | `Optional[str]` | **The fall-through residual** — everything left after the above are stripped |
| `address` | `Optional[str]` | Normalized address string; empty string `""` if none found |
| `stats` | `CleanStats` | Counters (replacements, units before/after, channel/address found flags) |

**No `parsed` field is produced.** The EVENT_MODEL `dispatch.incident.created` payload specifies `"parsed": {}` as a field, but `CleanResult` has no such field. No response modifiers, no dispatch action codes, no incident codes land anywhere. This is a hard gap.

---

### A.1 — Order of operations (the full sequence)

```
1.  REPLACEMENTS applied to raw          → `fixed`
2.  Strip commas  re.sub(r",+", "", fixed)
3.  Strip periods re.sub(r"\.+", "", fixed)
4.  Collapse whitespace re.sub(r"\s+", " ", fixed).strip()
5.  `incident = fixed`   (working string; will be progressively consumed)

6.  SPECIAL_CALL check on `fixed` (not `incident`)
      sc_re = r"^special call" (re.I, anchored)
      special_call = bool(sc_re.search(fixed))
      incident = sc_re.sub("", fixed)     ← strips prefix from working copy

7.  UNIT extraction on `fixed` (original, not the sc-stripped `incident`)
      for each pat in UNIT_PATTERNS: pat.finditer(fixed)
      m.group(1).title() → deduped into units_found
      for unit in units_found: incident = incident.replace(unit, "")   ← case-sensitive remove
      strip leading "and" from incident

8.  CHANNEL extraction on `fixed` (original, not stripped `incident`)
      CHAN_RE.search(fixed)
      if group(1): chan = "K-Deck N"
      if group(2): chan = "AN"
      CHAN_RE.sub("", incident)   ← remove from working copy
      strip leading "and" from incident

9.  incident_type = incident.strip()   ← snapshot before address pass

10. ADDRESS cascade on incident_type (4 sub-steps, see A.4)
      → updates incident_type to the pre-address prefix
      → addr dict populated

11. if addr["normalized"]: incident = incident_type

12. re.sub(r"\s+", " ", incident).strip()

13. MISHEARD_INCIDENTS applied to incident  (second correction pass)

14. re.sub(r"(?:\band\s*)+", "", incident)   ← strip stray "and"
```

### A.2 — Per-field method and pattern

#### `special_call`

- **Method:** Anchored regex on `fixed`.
- **Pattern:** `r"^special call"` (`re.I`)
- **Extraction:** `.search()` produces the bool; `.sub("", fixed)` strips the phrase from the working string.
- **Failure:** If not present, bool is False and `incident` equals `fixed` unchanged.
- **Gap:** Only handles the literal phrase "special call" at the very start of the transcript. No other dispatch action ("Balance of Assignment", "Second Alarm", etc.) is recognized here or anywhere else.

#### `units`

- **Method:** Iterated regex scan against `UNIT_PATTERNS` (17 compiled patterns, see Section B).
- **Pattern:** Each is a `re.I` pattern with one capture group — the full unit string including the number. Iterated in list order; each runs `finditer` on `fixed`.
- **Dedup:** A `seen: set` keyed on the titlecased string prevents double-counting repeated bookend units.
- **Removal from working string:** `incident.replace(unit, "")` — **case-sensitive string replacement**. If the transcript's casing doesn't exactly match the `.title()` output, the unit is found in `units_found` but NOT removed from `incident`, and the text bleeds into `incident_type`. This is the most likely cause of the ~5% imperfect extraction rate on otherwise-clean transcripts (details in Section C).
- **Failure:** No match → unit omitted from list; text remains in `incident` and pollutes `incident_type`.

#### `channel`

- **Method:** Single regex on `fixed`.
- **Pattern (`CHAN_RE`):**
  ```python
  (?:
      K[- ]?De(?:ck|c)\s*(\d+)       # group(1): K-Deck family
      |
      (?:Fire\s*Channel\s*)?          # optional "Fire Channel" prefix
      \bA(\d{1,2})\b                  # group(2): A-channel family
  )
  ```
  Flags: `re.I | re.VERBOSE`
- **Output:** `"K-Deck {int(group(1))}"` or `"A{int(group(2))}"`.
- **Removal:** `CHAN_RE.sub("", incident)` replaces the channel text in the working copy.
- **Failure:** `chan = None`; channel text remains in `incident` and bleeds into `incident_type`.
- **Gap:** Recognizes only two channel families (K-Deck N and A-style). No other named channels. "Fire Channel A5" works (optional prefix absorbed); bare "Fire 5" does not.

#### `incident_type`

- **Method:** Fall-through residual — no regex, no lookup. It is literally whatever text remains in `incident` after special_call prefix, units, channel, and address have been removed/consumed.
- **Fall-through confirmed:** Yes. The "fall-through-sink hypothesis" is correct.
- **Second correction pass:** `MISHEARD_INCIDENTS` (8 patterns: e.g. "Tech Welfare" → "Check Welfare", "Park Problem" → "Heart Problem") are applied to `incident` after address extraction. These are the only normalization applied to the incident type text.
- **Failure behavior:** If the transcript has unusual formatting, extra noise, or units/channels that weren't extracted, those tokens bleed into `incident_type` directly. There is no sanitization step other than stripping "and" fragments.
- **No vocab lookup:** `incident_type` is never matched against the `incident_types` list in `phoenix_dispatch_vocab.json` — that file isn't loaded anywhere.

#### `address`

- **Method:** 4-step cascade (see A.4 below), each step calling `_normalize_address()`.
- **Failure:** If no step matches, `addr = {"raw": "", "normalized": ""}`. The field on `CleanResult` is `addr["normalized"]` — an empty string, not `None`.

#### `text`

- **Method:** The normalized transcript (`fixed`) produced after REPLACEMENTS + whitespace collapse. Not further modified during field extraction.

---

### A.3 — REPLACEMENTS (pre-processing normalization, step 1)

These run first, before any field extraction:

| Pattern | Replacement | Purpose |
|---|---|---|
| `\bItalian\s+(\d{1,3})\b` | `Battalion \1` | ASR mishearing |
| `\bBattalion\s+Chief\s+(\d{1,3})\b` | `Battalion \1` | Normalize variant |
| `\bK\s*[-]?\s*dec?k\s*(\d{1,2})\b` | `K-Deck \1` | Channel normalization |
| `\bC R\s*?(\d+)\b` | `Crisis Response \1` | Unit abbreviation expansion |
| `\bStage 4 PD\b` | `Stage For PD` | Mishearing correction |

### A.4 — Address cascade (step 10)

Runs on `incident_type` (the incident working string after special_call/units/channel removed).

**Sub-step 1 — 9xx incident code prefix:**
```python
re.match(r"^(?P<code>\d{3})\b\s+(?P<rest>.+)", incident_type)
```
If matches: `incident_type = code`, `address_text = rest`, pass rest to `_normalize_address()`.

**Sub-step 2 — Numbered street address anywhere:**
`ADDR_RE.search(incident_type)` — the full numbered-address regex (see B). On match: `incident_type = text before match`, `address_text = matched span`.

**Sub-step 3 — Street anchor (no leading house number):**
`STREET_ANCHOR_RE.search(incident_type)` matches directional+word, ordinal, or word+type anchors. On match: splits at anchor; checks if the prefix ends with a 3-5 digit number (prepends it to address_text). `incident_type = text before anchor`.

**Sub-step 4 — Last resort:** Passes entire `incident_type` to `_normalize_address()`. If it finds something, removes the raw match from `incident_type`.

**Within `_normalize_address()`:**
1. Try `ADDR_RE` (numbered address: `\b<3-5 digits> <compass> <name tokens> [type]`)
2. Try `INTERSECTION_RE` (`<street1> [and|&|at] <street2>`)
3. Try `FREEWAY_INTERSECTION_RE` (`I-N|Loop N|US-N|SR-N|A-NN [at|and] <cross>`)

---

## Section B — Hardcoded-Strings Inventory

Everything below is baked into `cleaner.py` and belongs in an external data file.

### B.1 — Unit types (`UNIT_PATTERNS`)

17 compiled patterns. Each is a separate `re.compile`. Listed by what they recognize:

| Pattern | Recognizes | Multi-word? | Trailing number required? |
|---|---|---|---|
| `\b(Batt(?:alion)?\s*\d{1,4})\b` | Battalion / Batt | No | Yes |
| `\b(Engine\s*\d{1,4})\b` | Engine N | No | Yes |
| `\b(Ladder\s+Tender\s*\d{1,4}\|LA-\d{1,4}\|Ladder\s*\d{1,4}\|Truck\s*\d{1,4}\|TR\s*\d{1,4})\b` | Ladder Tender N, LA-N, Ladder N, Truck N, TR N | Yes (Ladder Tender) | Yes |
| `\b(Rescue\s*\d{1,4}\|Medic\s*\d{1,4}\|Maricopa\s*\d{1,4}\|Medical Response\s*\d{1,4})\b` | Rescue N, Medic N, Maricopa N, Medical Response N | Yes (Medical Response) | Yes |
| `\b(Crisis\s+Response\s*\d{1,4})\b` | Crisis Response N | Yes | Yes |
| `\b(West Deputy)\b` | West Deputy | Yes | No (no number) |
| `\b(Car\s+\d{1,4}\s+(?:North\|South))\b` | Car N North/South | Yes | Yes (between type and direction) |
| `\b(Heavy Rescue Tender\s*\d{1,4})\b` | Heavy Rescue Tender N | Yes | Yes |
| `\b(Hazmat\s*\d{1,4})\b` | Hazmat N | No | Yes |
| `\b(Brush\s*\d{1,3})\b` | Brush N | No | Yes |
| `\b(Car\s*\d{1,4})\b` | Car N | No | Yes |
| `\b(South Deputy)\b` | South Deputy | Yes | No |
| `\b(Medical Response\s*\d{1,4})\b` | Medical Response N | Yes | Yes (duplicate of row 4) |
| `\b(BH\s*\d{1,2})\b` | BH N | No | Yes |
| `\b(Foam\s*\d{1,3})\b` | Foam N | No | Yes |
| `\b(Air Stair\s*\d{1,3})\b` | Air Stair N | Yes | Yes |
| `\b(Attack\s*\d{1,3})\b` | Attack N | No | Yes |

**Note:** `Medical Response` appears in both row 4 and row 13 — exact duplicate pattern.

**Missing unit types (real Phoenix dispatch language not covered):**

| Unit Type | Example | Why it fails |
|---|---|---|
| North Deputy | "North Deputy 50" | No pattern. "West Deputy" and "South Deputy" exist but not "North Deputy". |
| PIO | "PIO 1" | No pattern at all. |
| Mobile Stroke Unit | "Mobile Stroke Unit 1" | No pattern. |
| Brush Engine | "Brush Engine 6130" | `Brush\s*\d+` requires a number immediately after "Brush"; "Brush Engine 6130" doesn't match. |
| Care | "Care N" | No pattern. |
| LA (bare, no hyphen) | "LA 608" | Pattern has `LA-\d{1,4}` (hyphen required). "LA 608" doesn't match. |

### B.2 — Channels (`CHAN_RE`)

Two families recognized:
- **K-Deck family:** `K[- ]?De(?:ck|c)\s*(\d+)` — handles "K-Deck 8", "K Dec 8", "KDeck 8"
- **A-channel family:** `(?:Fire\s*Channel\s*)?\bA(\d{1,2})\b` — handles "A5", "Fire Channel A5"

Not recognized: bare "Fire N", any named channels, any channel format outside these two families.

**CHAN_RE is duplicated:** There is a REPLACEMENTS rule that normalizes K-deck variants before the CHAN_RE runs. The CHAN_RE itself also handles those variants. Both are hardcoded.

### B.3 — Dispatch actions

Only one:
```python
sc_re = re.compile(r"^special call", re.I)
```
Hardcoded inline in `clean_transcript`. Produces a boolean only.

Not recognized: "Balance of Assignment", "Second Alarm", "Third Alarm", any escalation/supplement language.

### B.4 — Response modifiers

**None in the parser.** The vocab file (`phoenix_dispatch_vocab.json`) lists AOI, Code 2, Code 3, but the parser does not load that file and has no code to extract these tokens. They fall through entirely into `incident_type` if present in the transcript.

### B.5 — Incident type corrections (`MISHEARD_INCIDENTS`)

8 hardcoded correction pairs:

| Pattern | Replacement |
|---|---|
| `\bTech Welfare\b` | `Check Welfare` |
| `\b[A-Z]ill\s*Person\b\|\bIlkerson\b\|\bIlverson\b` | `Ill Person` |
| `\bPark Problem\b` | `Heart Problem` |
| `\bJust Payne\b` | `Chest Pain` |
| `\brush fire\b` | `Brush Fire` |
| `\band no medical\b` | `Unknown Medical` |
| *(Stage 4 PD in REPLACEMENTS, not here)* | — |

These are ASR mishearing corrections. They apply to the `incident` remainder AFTER address extraction, and correct the free-text leftover — not a vocabulary lookup.

### B.6 — Address components

**Street suffixes (`ST_TYPE_MAP`):** `avenue/ave`, `street/st`, `road/rd`, `drive/dr`, `lane/ln`, `way`, `boulevard/blvd`, `place/pl`, `court/ct`, `terrace/ter`, `trail/trl`, `parkway/pkwy`. Hardcoded dict.

**Compass directions (`COMPASS_WORDS`):** `north/n → N`, `south/s → S`, `east/e → E`, `west/w → W`. Hardcoded dict.

**Address stop tokens** (tokens the street-name regex must NOT absorb, to prevent runoff into units/channels): `Engine`, `Rescue`, `Ladder`, `Battalion`, `Crisis Response`, `K-Deck`. These are hardcoded inline inside `ADDR_RE`'s negative lookahead.

**Freeway pattern** (inside `FREEWAY_INTERSECTION_RE`): `I-?\d+|Loop\s+\d+|US\s*\d+|SR\s*\d+|A(\s*|-)\d{2,3}`. This is separate from (and inconsistent with) the `freeways` list in the vocab file, which has canonical names + aliases. The parser-internal freeway regex is a generic structural pattern; it cannot recognize named aliases like "Papago Freeway" or "Black Canyon".

**`Mall`** appears as a recognized street suffix type in `ADDR_RE` but not in `ST_TYPE_MAP`.

---

## Section C — Unit Recognition in Detail

### How matching works today

1. `fixed` (the normalized transcript string) is scanned by each of 17 patterns in order using `finditer`.
2. Group 1 of each match is captured, `.title()`'d, and added to `units_found` if not already in `seen`.
3. Each found unit is removed from `incident` via **case-sensitive** `str.replace()`.

### Multi-word unit type handling

- **Works:** Ladder Tender N (explicit alternation), Crisis Response N, Medical Response N, Heavy Rescue Tender N, Air Stair N, Car N North/South.
- **Partially works:** West Deputy, South Deputy (no number, exact fixed strings — work only if transcript casing matches).
- **Does not work:** North Deputy (missing), Mobile Stroke Unit (missing), Brush Engine N (no pattern), PIO (missing), "and" between units (the "and" is only stripped as a leading artifact, not parsed as a unit separator).

### The ~5% miss rate — root causes

**Root cause 1 — Case-sensitive removal.**
Units are extracted with `re.I` (case-insensitive), stored as `.title()`, but removed via `str.replace()` (case-sensitive). If the ASR output is `"engine 25"` (lowercase) and the pattern captures it as `"Engine 25"` (titlecased via `.title()`), then `incident.replace("Engine 25", "")` finds nothing. The unit is correctly in `units_found` but the text is NOT removed from `incident`, polluting `incident_type`.

**Root cause 2 — Missing patterns.**
North Deputy, PIO, Mobile Stroke Unit, Brush Engine, bare "LA N" (no hyphen), Care — any of these in a transcript go unrecognized and fall into `incident_type`.

**Root cause 3 — `Brush\s*\d+` requires number adjacency.**
"Brush Engine 6130" has "Engine" between the type stem and the number. The pattern `Brush\s*\d+` matches "Brush 6130" or "Brush6130" but not "Brush Engine 6130".

**Root cause 4 — `stats.units_before` uses a different, narrower regex:**
```python
re.findall(r"\b(Engine|Rescue|Ladder|Batt(?:alion)?|Crisis\s+Response)\s*\d{1,3}\b", fixed, re.I)
```
This counts only 5 types. `stats.deduped_units` is therefore always wrong for Hazmat, Foam, BH, Brush, etc. The stats field is unreliable but doesn't affect extraction correctness.

---

## Section D — Dispatch Action Handling

### Current state

**The only dispatch action recognized is "special call."**

The detection is anchored to the start of the transcript:
```python
sc_re = re.compile(r"^special call", re.I)
special_call = bool(sc_re.search(fixed))
incident = sc_re.sub("", fixed)
```

The phrase is stripped from the working string; the boolean rides on `CleanResult.special_call`. That boolean is included in the `dispatch.incident.created` payload. There is no mechanism to associate this with a prior incident (no `correlation_id` is set by the parser — that's an envelope field that would need the hub or a higher layer to manage).

### "Balance of Assignment"

Not handled anywhere. The phrase would fall through entirely into `incident_type`. Example transcript: `"Balance of Assignment Engine 25 Rescue 35 K-Deck 8 Chest Pain 1234 N 7th St"` — units and channel would be extracted, `incident_type` would come out `"Balance Of Assignment Chest Pain"` or similar depending on address extraction. There is no flag, no field, and no concept of "this call modifies an existing incident."

### Recommendation on `parsed.dispatch_action`

Yes — dispatch action warrants its own extracted field. The current `special_call` bool is the right precedent; it should be generalized to a `dispatch_action` enum/string (e.g. `"initial"`, `"special_call"`, `"balance_of_assignment"`, `"second_alarm"`, etc.) either on `CleanResult` directly or in a `parsed` dict.

The EVENT_MODEL `correlation_id` note is correct: "Balance of Assignment" and "Special Call" transmissions are supplements to an existing incident. If the parser extracts the dispatch action, the hub (or a linking layer) can use it as a signal to look up a prior incident and populate `correlation_id` on the event envelope.

---

## Section E — Vocab Structure Recommendation

### What the parser currently has vs. what the vocab file has

| Category | In `cleaner.py` | In `phoenix_dispatch_vocab.json` | Used by parser? |
|---|---|---|---|
| Unit types | 17 UNIT_PATTERNS | Not in vocab file | Yes (hardcoded) |
| Channel patterns | CHAN_RE (2 families) | Not in vocab file | Yes (hardcoded) |
| Dispatch actions | sc_re (1 action) | Not in vocab file | Yes (hardcoded) |
| Response modifiers | None | Yes (AOI, Code 2, Code 3) | No (not loaded) |
| Incident types | MISHEARD_INCIDENTS (8 corrections only) | Yes (~21 seed entries) | No (not loaded) |
| Freeways / interchanges | FREEWAY_INTERSECTION_RE (structural pattern) | Yes (full alias lists) | No (not loaded) |
| Address suffixes | ST_TYPE_MAP, COMPASS_WORDS | Not in vocab file | Yes (hardcoded) |

The vocab file (`phoenix_dispatch_vocab.json`) is untracked (not yet committed) and not imported anywhere. It is a design artifact only.

### Recommended split layout

Confirm the proposed split-by-maintenance-lifecycle approach. The lifecycle argument is sound:

```
vocab/
  unit_types.json        # unit type prefix patterns + aliases; changes when new unit types appear
  channels.json          # channel families + patterns; changes when radio plan changes
  dispatch_actions.json  # action phrases (special call, balance of assignment, second alarm…)
  response_modifiers.json # AOI, Code 2/3; stable but region-specific
  incident_types.json    # the full ~200-code table; changes as CAD codes evolve
  freeways.json          # freeway canonical names + aliases + named interchanges
```

Merge the current `phoenix_dispatch_vocab.json` contents into this structure: `incident_types`, `response_modifiers`, `freeways`, `named_interchanges` are already there; move to the split layout.

**Single loader, one in-memory vocab object.** The parser should import one `Vocab` object from a loader module that reads all files and merges. The parser depending on six JSON file paths directly would be brittle; one loader that returns a `Vocab` dataclass is the right seam.

### Unit type pattern form

Recommend **pattern-form entries** rather than enumerating every unit. Each entry should describe how the unit is matched, not a fixed string:

```json
{
  "type": "Engine",
  "pattern": "Engine",
  "requires_number": true,
  "number_suffix_words": [],
  "aliases": []
}
```

For multi-word prefix units:
```json
{
  "type": "Brush Engine",
  "pattern": "Brush Engine",
  "requires_number": true,
  "number_suffix_words": [],
  "aliases": ["Brush"]
}
```

For directional no-number units:
```json
{
  "type": "North Deputy",
  "pattern": "North Deputy",
  "requires_number": false,
  "aliases": []
}
```

The loader builds regexes at startup from these entries: `\b({pattern})\s*(\d{{1,4}})\b` for `requires_number: true`, `\b({pattern})\b` for false. This handles "North Deputy 50" vs "North Deputy" vs "Brush Engine 6130" vs "Engine 25" generically without enumerating every unit number.

**Important:** The number must be absorbed into the unit string when present (so "Brush Engine 6130" is one unit, not "Brush Engine" + stray "6130"). The current UNIT_PATTERNS approach of capturing the full `type + number` in group(1) is correct — keep that contract.

---

## Recommended Fix 4 Adjustments

Based on the actual code:

1. **Add `parsed: dict` to `CleanResult`** — the field exists in EVENT_MODEL but `CleanResult` has no `parsed` attribute. All region-specific extractions (response modifiers, dispatch action code, incident type code) need somewhere to land.

2. **Fix the case-sensitive removal bug** — `incident.replace(unit, "")` must be case-insensitive. Simplest fix: `re.sub(re.escape(unit), "", incident, flags=re.I)`. This is the most likely cause of the ~5% miss rate on clean transcripts.

3. **Add `dispatch_action` extraction** — generalize `special_call` from a bool into a recognized field (string or enum). Minimum vocabulary: `"initial"`, `"special_call"`, `"balance_of_assignment"`. The `special_call` bool can remain for backward compatibility; `parsed.dispatch_action` carries the full value.

4. **Load `phoenix_dispatch_vocab.json` (or the split files)** — the parser currently ignores the vocab file. Fix 4's primary job is wiring the loader into `clean_transcript`.

5. **Add response modifier extraction** — before address extraction, scan for AOI / Code 2 / Code 3 from the vocab and strip them from the working string; park in `parsed.response_code` / `parsed.aoi`. Without this step they bleed into `incident_type`.

6. **Add missing unit types** — North Deputy, PIO, Mobile Stroke Unit, Brush Engine, Care, bare LA (no hyphen) must be in the new vocab-driven unit list.

7. **Replace the freeway structural regex with vocab-driven alias lookup** — `FREEWAY_INTERSECTION_RE`'s generic `I-?\d+` pattern can't recognize "Papago Freeway" or "Beeline". The freeway vocab already has the alias lists; the address cascade should check them before falling through to the structural pattern.

8. **Do NOT change the 4-step address cascade structure** — it's sound. The improvements are in what feeds into it (freeway alias recognition) and what is stripped before it runs (response modifiers, dispatch actions).

9. **The `incident_type` fall-through is fine as the architectural approach** — but after Fix 4, the leftover should also be matched against the `incident_types` vocab (canonical phrase + aliases) to produce a normalized type and optionally a code in `parsed.incident_code`. The leftover text after that match is the true residual.

10. **Fix `stats.units_before` count** — it uses a 5-type narrow regex for dedup tracking, making `stats.deduped_units` unreliable. Low priority but worth fixing when the unit patterns move to vocab-driven.

---

*End of report.*
