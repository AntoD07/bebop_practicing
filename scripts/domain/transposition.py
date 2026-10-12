"""Degree translations between harmonic contexts (marker-aware, stdlib only).

Every mapping re-spells a cell's degree tokens from one chord root to another:

* ``loc_to_dom``    Locrian (ii) degrees read from the V root
* ``dom_to_minor``  dominant (V) degrees read from the minor-I root
* ``dom_to_major``  dominant (V) degrees read from the major-I root
* ``dom_to_dorian`` dominant (V) degrees read from the ii (Dorian) root — what
                    lets Dorian and Myxolidian cells pivot-connect
* ``sus4``          the arithmetic shift of the 7sus4 vocabulary into Minor/
                    Dorian (+3) or Locrian (+5)

Octave markers (``9(lower)``, ``b9(higher)``) ride along untouched. A token a
mapping does not know raises :class:`TranslationError` (never a bare KeyError),
which the API turns into a 422 naming the token and the mapping.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Tuple


class TranslationError(KeyError):
    """A degree token the requested mapping has no entry for."""

    def __init__(self, token: str, mapping: str):
        super().__init__(token)
        self.token = token
        self.mapping = mapping

    def __str__(self) -> str:
        return f"token {self.token!r} has no {self.mapping} translation"


loc_to_dom_mapping: Dict[str, str] = {
    "1": "5", "4": "1", "7": "4", "3": "7", "9": "b6", "5": "b9", "6": "#9",
    "#9": "6", "maj5": "9", "#3": "maj7", "maj7": "#11", "#6": "3",
}

# V degrees read from the minor-I root (+7 semitones): 3 -> #7 (the i's major
# 7th), maj7/#7 (11 semitones) -> #11. "#7" is the Locrian CSV's spelling of
# the major 7th (same pitch as maj7), filled 2026-10 — confirm musically.
dom_to_min_mapping: Dict[str, str] = {
    "1": "5", "4": "1", "7": "4", "3": "#7", "9": "6", "5": "9", "6": "maj3",
    "#9": "7", "b9": "b6", "b6": "3", "maj7": "#11", "#7": "#11", "#11": "b9",
}

# Dominant (Myxolidian) degrees re-spelled relative to the ii (Dorian) root,
# a 4th below the V root (G7 degrees read from D). Bare "7" is the mode's b7
# on both sides; "#7" is the Dorian spelling of the major 7th (the V root's
# #11), "maj3" the chromatic major-3rd passing tone (the V's maj7).
dom_to_dorian_mapping: Dict[str, str] = {
    "1": "4", "2": "5", "9": "5", "3": "6", "4": "7", "5": "1", "6": "9",
    "7": "3", "maj7": "maj3", "#11": "#7", "#5": "b9", "#9": "b6", "b9": "#11",
}

dom_to_maj_mapping: Dict[str, str] = {
    "1": "5", "4": "1", "7": "4", "3": "7", "9": "6", "2": "6", "5": "9",
    "6": "3", "#9": "b7", "b9": "b6", "#5": "b6", "b6": "min3", "maj7": "#11",
    "#7": "#11", "#11": "b9",
}

MAPPINGS: Dict[str, Dict[str, str]] = {
    "loc_to_dom": loc_to_dom_mapping,
    "dom_to_minor": dom_to_min_mapping,
    "dom_to_major": dom_to_maj_mapping,
    "dom_to_dorian": dom_to_dorian_mapping,
}
MAPPING_NAMES = list(MAPPINGS) + ["sus4"]

_MARKER_RE = re.compile(r"^(.*?)(\((?:higher|lower)\))$")


def split_marker(token: str) -> Tuple[str, str]:
    """``'9(lower)' -> ('9', '(lower)')``; a bare token keeps an empty suffix."""
    m = _MARKER_RE.match(str(token).strip())
    return (m.group(1).strip(), m.group(2)) if m else (str(token).strip(), "")


def translate_token(token: str, mapping) -> str:
    """Map one degree token with ``mapping`` (a name or a dict), keeping any
    octave marker. Raises :class:`TranslationError` on a gap."""
    name = mapping if isinstance(mapping, str) else "custom"
    table = MAPPINGS[mapping] if isinstance(mapping, str) else mapping
    core, suffix = split_marker(token)
    if core in table:
        return table[core] + suffix
    # Explicit marker-bearing entries (legacy dom_to_major) still resolve.
    if str(token).strip() in table:
        return table[str(token).strip()]
    raise TranslationError(str(token), name)


def translate_tokens(tokens: Iterable[str], mapping) -> List[str]:
    return [translate_token(t, mapping) for t in tokens]


_SUS4_RE = re.compile(r"([a-zA-Z#b]*)(\d+)([^\d]*)")
_SUS4_SHIFT = {"Minor": 3, "Dorian": 3, "Locrian": 5}


def sus4_token(token: str, mode: str) -> str:
    """The 7sus4 vocabulary's arithmetic shift into ``mode`` (Minor/Dorian +3,
    Locrian +5), modulo 7 with jazz re-spelling (2 -> 9, accidental 4 -> 11).
    Tokens without a number translate to ``"0"`` (legacy behaviour)."""
    shift = _SUS4_SHIFT.get(mode)
    if shift is None:
        raise TranslationError(str(token), f"sus4->{mode}")
    m = _SUS4_RE.match(str(token))
    if not m:
        return "0"
    prefix, number, suffix = m.groups()
    new_number = (int(number) - 1 + shift) % 7 + 1
    if new_number == 2:
        new_number = 9
    if new_number == 4 and bool(prefix):
        new_number = 11
    return f"{prefix}{new_number}{suffix}"


def translate_step(tokens: Iterable[str], step: str, mode: Optional[str] = None) -> List[str]:
    """Apply one named step (``sus4`` needs the target ``mode``)."""
    if step == "sus4":
        return [sus4_token(t, mode or "") for t in tokens]
    return translate_tokens(tokens, step)
