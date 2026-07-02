"""Minimal chord-symbol parsing for naming, flags, and the phase-2 gate.

Used only for labels and to decide whether a drop lands on a chord tone — never
for fingering math (per spec, ``context`` does not drive the DP).
"""

from __future__ import annotations

import re
from typing import Optional, Set, Tuple

_ROOT_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

# Ordered so longer quality tokens match before their prefixes.
_QUALITIES = [
    ("maj7", {0, 4, 7, 11}), ("M7", {0, 4, 7, 11}), ("Δ", {0, 4, 7, 11}),
    ("m7b5", {0, 3, 6, 10}), ("m7(b5)", {0, 3, 6, 10}), ("ø", {0, 3, 6, 10}),
    ("dim7", {0, 3, 6, 9}), ("°7", {0, 3, 6, 9}), ("o7", {0, 3, 6, 9}),
    ("dim", {0, 3, 6}), ("°", {0, 3, 6}),
    ("m6", {0, 3, 7, 9}), ("min6", {0, 3, 7, 9}), ("-6", {0, 3, 7, 9}),
    ("m7", {0, 3, 7, 10}), ("min7", {0, 3, 7, 10}), ("-7", {0, 3, 7, 10}),
    ("m9", {0, 3, 7, 10, 2}), ("min9", {0, 3, 7, 10, 2}),
    ("6", {0, 4, 7, 9}),
    ("9", {0, 4, 7, 10, 2}), ("13", {0, 4, 7, 10, 2, 9}),
    ("7", {0, 4, 7, 10}),
    ("aug", {0, 4, 8}), ("+", {0, 4, 8}),
    ("m", {0, 3, 7}), ("min", {0, 3, 7}), ("-", {0, 3, 7}),
    ("maj", {0, 4, 7}), ("M", {0, 4, 7}),
    ("", {0, 4, 7}),  # bare root = major triad
]


def parse_chord(symbol: str) -> Optional[Tuple[int, Set[int]]]:
    """Return ``(root_pitch_class, {interval_pcs})`` or ``None`` if unparseable."""
    if not symbol:
        return None
    s = symbol.strip()
    m = re.match(r"^([A-G])([#b]*)", s)
    if not m:
        return None
    root = _ROOT_PC[m.group(1)]
    for acc in m.group(2):
        root += 1 if acc == "#" else -1
    root %= 12
    quality = s[m.end():]
    for token, ivs in _QUALITIES:
        if quality.startswith(token):
            return root, set(ivs)
    return root, {0, 4, 7}


def is_chord_tone(midi: int, symbol: str) -> bool:
    parsed = parse_chord(symbol)
    if parsed is None:
        return False
    root, ivs = parsed
    return (midi - root) % 12 in ivs


def chord_for_beat(context: dict, abs_beat_index: int, beats_per_bar: int) -> Optional[str]:
    """Chord symbol active at an absolute (0-based) beat, from ``context['chords']``.

    Accepts entries as ``{"start_beat": int, "symbol": str}`` (0-based absolute)
    or ``{"bar": int, "beat": int, "symbol": str}`` (1-based). Returns the symbol
    of the latest entry whose start is <= the note's beat.
    """
    chords = (context or {}).get("chords") or []
    active = None
    active_start = -1
    for entry in chords:
        if "start_beat" in entry:
            start = entry["start_beat"]
        else:
            bar = entry.get("bar", 1)
            beat = entry.get("beat", 1)
            start = (bar - 1) * beats_per_bar + (beat - 1)
        if start <= abs_beat_index and start >= active_start:
            active, active_start = entry.get("symbol"), start
    return active
