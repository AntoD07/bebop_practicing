"""Pitch handling and fretboard geometry.

The optimizer never invents pitches — it only decides *where* on the neck each
given pitch is played. This module converts the incoming ``line`` (MIDI ints or
scientific-pitch strings, each optionally tagged with a musical ``role``) into a
normalised list of :class:`Note`, and enumerates the candidate ``(string, fret)``
placements for each note within the configured reach.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Union

from scripts.fingering.config import FingeringConfig, STANDARD_TUNING_MIDI

# Chromatic names for display (sharps). Fret math is octave-agnostic; names are
# only for the per-note table.
_PC_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_NAME_TO_PC = {
    "C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11,
}


def parse_pitch(pitch: Union[int, str]) -> int:
    """Return a MIDI integer for a MIDI int or a scientific-pitch string.

    Accepts ``60``, ``"C4"``, ``"F#5"``, ``"Bb3"``, ``"Ebb2"`` (middle C = C4 = 60).
    """
    if isinstance(pitch, bool):  # guard: bool is an int subclass
        raise ValueError(f"invalid pitch {pitch!r}")
    if isinstance(pitch, int):
        return pitch
    s = str(pitch).strip()
    if not s:
        raise ValueError("empty pitch string")
    letter = s[0].upper()
    if letter not in _NAME_TO_PC:
        # maybe it's a stringified int
        try:
            return int(s)
        except ValueError:
            raise ValueError(f"unrecognised pitch {pitch!r}")
    pc = _NAME_TO_PC[letter]
    i = 1
    while i < len(s) and s[i] in "#b":
        pc += 1 if s[i] == "#" else -1
        i += 1
    octave_str = s[i:]
    try:
        octave = int(octave_str)
    except ValueError:
        raise ValueError(f"missing/invalid octave in pitch {pitch!r}")
    return (octave + 1) * 12 + pc


def midi_to_name(midi: int) -> str:
    return f"{_PC_NAMES[midi % 12]}{midi // 12 - 1}"


@dataclass
class Note:
    """A single note of the input line after normalisation."""

    index: int                    # position in the line (0-based)
    midi: int                     # pitch as MIDI
    beat: float                   # 1-based beat within the bar (exact; 1.5 = "and of 1")
    role: Optional[str] = None    # "root","b3","5","9","chromatic-approach",...
    cell: Optional[str] = None    # owning cell name (for labels), if known
    degree: Optional[str] = None  # scale-degree string ("1","b3","5",...) if known
    onset: float = 0.0            # absolute start, in quarter-note beats from 0
    phrase_start: bool = False    # first note of a phrase (line start / after a rest)
    is_grace: bool = False        # inserted by the ornament engine (sub-beat timing)
    ornament: Optional[str] = None  # ornament family that inserted/altered this note

    @property
    def name(self) -> str:
        return midi_to_name(self.midi)


@dataclass(frozen=True)
class Placement:
    """A candidate (string, fret) for a note, plus its hand-position options."""

    string: int
    fret: int

    def is_open(self) -> bool:
        return self.fret == 0


def build_notes(line: List[dict], config: FingeringConfig,
                context: Optional[dict] = None) -> List[Note]:
    """Normalise the raw ``line`` into :class:`Note` objects with exact beats.

    Each note may carry an explicit ``"start"`` (absolute onset in quarter-note
    beats, floats allowed — eighths land on x.5). Without it, the uniform
    quarter grid applies: onset = index. Downbeat identification stays exact —
    there is no unknown-rhythm branch. ``"phrase_start"`` marks the first note
    after a rest (the hand repositions for free there).
    """
    beats_per_bar = config.beats_per_bar
    start = config.start_beat_index
    if context and "beats_per_bar" in context:
        beats_per_bar = context["beats_per_bar"]
    notes: List[Note] = []
    for i, raw in enumerate(line):
        midi = parse_pitch(raw["pitch"])
        onset = float(raw.get("start", start + i))
        beat = (onset % beats_per_bar) + 1
        notes.append(
            Note(
                index=i,
                midi=midi,
                beat=beat,
                role=raw.get("role"),
                cell=raw.get("cell"),
                degree=raw.get("degree"),
                onset=onset,
                phrase_start=bool(raw.get("phrase_start", i == 0)),
            )
        )
    return notes


def candidate_placements(midi: int, config: FingeringConfig) -> List[Placement]:
    """All playable ``(string, fret)`` positions for a pitch within reach."""
    out: List[Placement] = []
    strings = config.string_range
    # (Root pin is SOFT — off-shape root placements are charged in costs.py,
    # not filtered here.)
    for s in strings:
        win = config.fret_window_for(s)
        if win:
            # Soft box: a small overflow margin is playable (charged in costs).
            lo = win[0] - config.window_overflow_frets
            hi = win[1] + config.window_overflow_frets
        else:
            lo, hi = 0, config.max_fret
        open_midi = STANDARD_TUNING_MIDI[s]
        fret = midi - open_midi
        if fret == 0 and not config.allow_open_strings:
            continue
        if 0 <= fret <= config.max_fret and lo <= fret <= hi:
            out.append(Placement(string=s, fret=fret))
    return out


def anchors_for(fret: int, config: FingeringConfig) -> List[Optional[int]]:
    """Hand-anchor (index-finger fret) options that can reach ``fret``.

    Open strings (fret 0) impose no anchor — they inherit the carried position,
    represented as ``None`` here (resolved during the DP transition).
    """
    if fret == 0:
        return [None]
    lo = max(1, fret - (config.allow_stretch_to - 1))
    hi = fret
    return list(range(lo, hi + 1))


def finger_for(fret: int, anchor: Optional[int], config: FingeringConfig):
    """Return ``(finger, is_stretch)`` for a fret given a hand anchor.

    finger 0 = open string. 1..4 = index..pinky. A 5th-fret reach uses the
    pinky/index extension and is flagged.
    """
    if fret == 0:
        return 0, False
    if anchor is None:
        anchor = fret  # play with index as a fallback
    finger = fret - anchor + 1
    is_stretch = finger > config.max_stretch
    return finger, is_stretch
