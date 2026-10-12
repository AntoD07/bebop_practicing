"""Phase-2 ornament engine — UPPER-NEIGHBOR TURN / MORDENT only.

    pick -> hammer up -> pull back        e.g.  8h10p8

Single string, NO crossing, mechanically IDLE (buys no picking window) — pure
phrasing colour on a sustained/target note. It is deliberately the ONLY device
this engine applies: the mechanical families (drop cushions, slides, enclosure
inserts, chromatic triplets) were tried and dropped — they cluttered the tab
without earning their place. The turn reads cleanly because it never leaves
the target's string or disturbs the line's crossings.

When ``config.ornament_engine_enabled`` is on, eligible targets (a chord tone
on a bar downbeat, a tagged resolution, or the line's final note) get the turn
applied to a COPY of the phase-1 solution: the target keeps its pick, then two
attack-free grace notes follow inside its beat (upper neighbour hammered, the
target pulled back). ``result.ornamented`` is the ornamented (slurred) version;
``result.best`` stays the untouched all-picked line.

Honesty:
* The turn is the FIRST thing to smear at tempo — strip it above ~180 bpm
  (a note in the UI; the engine does not know the play-along tempo).
* Three notes land on one string: when that exceeds the 2npS layout it is
  flagged, never hidden.

Mechanics are verified post-build by :func:`find_ornament_violations` (a
hammer needs a lower-fret same-string source, a pull a higher-fret one, and
every picked string entry is still a rest-stroke D).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, List, Optional

from scripts.fingering.config import FingeringConfig, STANDARD_TUNING_MIDI
from scripts.fingering.costs import DOWN, UP, PULL, HAMMER, PlacedNote, relabel_fingers
from scripts.fingering.pitch import Note, midi_to_name, finger_for
from scripts.fingering.chords import chord_for_beat, is_chord_tone

_PICKED = (DOWN, UP)
_LEGATO = (PULL, HAMMER)


@dataclass
class OrnamentedVoicing:
    """The applied, ornamented version of a line (phase-1 stays untouched)."""

    placed: List[PlacedNote]     # full sequence, incl. inserted grace notes
    events: List[dict]           # what was applied where (drives the report)
    flags: List[str]             # honesty flags: 2npS breaks, tempo advice, ...
    picks_before: int
    picks_after: int

    def stroke_string(self) -> str:
        return " ".join(p.stroke for p in self.placed)


# --------------------------------------------------------------------------- #
# Target gate
# --------------------------------------------------------------------------- #
def _chord_tone(pn: PlacedNote, context: dict, bpb: int) -> bool:
    sym = chord_for_beat(context, pn.note.onset, bpb)
    return bool(sym) and is_chord_tone(pn.note.midi, sym)


def _target_priority(placed: List[PlacedNote], i: int, context: dict,
                     bpb: int) -> Optional[int]:
    """A sustained/target note worth colouring, ranked: a tagged resolution
    (0, best) beats the line's final chord tone (1) beats a chord tone on a
    bar downbeat (2). None = not a target."""
    pn = placed[i]
    if pn.note.onset % 1:
        return None
    if pn.note.role == "resolution":
        return 0
    if i == len(placed) - 1 and _chord_tone(pn, context, bpb):
        return 1
    if pn.note.onset % bpb == 0 and (_chord_tone(pn, context, bpb)
                                     or pn.note.degree in ("1", "3", "5", "b3")):
        return 2
    return None


# --------------------------------------------------------------------------- #
# Mechanics verifier
# --------------------------------------------------------------------------- #
def find_ornament_violations(placed: List[PlacedNote]) -> List[str]:
    """Physical-impossibility check on an ornamented sequence.

    A hammer needs a lower-fret same-string source; a pull a higher-fret one;
    every picked string ENTRY is still a rest-stroke D; no U-U on one string.
    """
    out: List[str] = []
    for i, pn in enumerate(placed):
        if i == 0:
            if pn.stroke != DOWN:
                out.append(f"note 0: a line must open with a picked D (got {pn.stroke})")
            continue
        prev = placed[i - 1]
        entry = prev.string != pn.string
        if pn.stroke == PULL:
            if entry or prev.fret <= pn.fret:
                out.append(f"note {i}: pull-off without a higher-fret same-string source")
        elif pn.stroke == HAMMER:
            if entry or prev.fret >= pn.fret:
                out.append(f"note {i}: hammer-on without a lower-fret same-string source")
        elif pn.stroke == UP:
            if entry and not pn.note.phrase_start:
                out.append(f"note {i}: U arriving on a string entry")
            elif prev.stroke == UP and not entry:
                out.append(f"note {i}: U-U on one string")
    return out


# --------------------------------------------------------------------------- #
# The apply pass
# --------------------------------------------------------------------------- #
def _turn_grace(target: PlacedNote, fret: int, stroke: str, onset: float,
                bpb: int, config: FingeringConfig) -> PlacedNote:
    midi = STANDARD_TUNING_MIDI[target.string] + fret
    note = Note(
        index=target.note.index, midi=midi, beat=(onset % bpb) + 1,
        role="turn", cell=target.note.cell, degree="",
        onset=onset, phrase_start=False, is_grace=True, ornament="turn",
    )
    finger, is_stretch = finger_for(fret, target.anchor, config)
    return PlacedNote(
        note=note, string=target.string, fret=fret, anchor=target.anchor,
        finger=finger, is_stretch=is_stretch, stroke=stroke, run_len=1,
        is_rest_stroke=False,
    )


def _recount_runs(placed: List[PlacedNote]) -> None:
    run = 0
    for i, pn in enumerate(placed):
        run = 1 if (i == 0 or placed[i - 1].string != pn.string
                    or pn.note.phrase_start) else min(run + 1, 3)
        placed[i] = replace(pn, run_len=run)


def _string_runs(placed: List[PlacedNote]):
    if not placed:
        return
    start = 0
    for i in range(1, len(placed)):
        if placed[i].string != placed[start].string:
            yield start, i - start, placed[start].string
            start = i
    yield start, len(placed) - start, placed[start].string


def apply_ornaments(result, context: Optional[dict],
                    config: FingeringConfig) -> OrnamentedVoicing:
    """Apply upper-neighbor turns to a copy of ``result.best``.

    At each eligible target the picked note keeps its attack, then the upper
    neighbour (``config.turn_fret_interval`` frets up, same string) is hammered
    and pulled back — the turn lives inside the target's beat as a triplet
    (T, T+1/3, T+2/3). Capped at ``config.max_ornaments_per_bar`` per bar.
    Never mutates phase 1.
    """
    context = context or {}
    base = result.best.placed
    bpb = context.get("beats_per_bar", config.beats_per_bar)
    iv = config.turn_fret_interval

    events: List[dict] = []
    flags: List[str] = []
    per_bar: Dict[int, int] = {}
    turned: List[int] = []

    # Rank candidates first (resolutions beat downbeats), THEN spend the
    # per-bar budget — so the cap never starves the best target in a bar.
    candidates: List[tuple] = []
    for i, pn in enumerate(base):
        if pn.stroke not in _PICKED or pn.fret + iv > config.max_fret:
            continue
        # the turn needs the beat to itself: skip if the next note starts
        # before the pulled-back return would sound (T + 2/3).
        if i + 1 < len(base) and base[i + 1].note.onset < pn.note.onset + 1:
            continue
        prio = _target_priority(base, i, context, bpb)
        if prio is not None:
            candidates.append((prio, i))
    candidates.sort()

    for _prio, i in candidates:
        pn = base[i]
        bar = int(pn.note.onset // bpb)
        if per_bar.get(bar, 0) >= config.max_ornaments_per_bar:
            continue
        per_bar[bar] = per_bar.get(bar, 0) + 1
        turned.append(i)
        upper = STANDARD_TUNING_MIDI[pn.string] + pn.fret + iv
        events.append({
            "family": "turn", "at": i, "bar": bar + 1,
            "target_pitch": pn.note.name,
            "stroke_before": pn.stroke, "stroke_after": pn.stroke,
            "added_notes": [
                {"fret": pn.fret + iv, "midi": upper, "name": midi_to_name(upper),
                 "stroke": HAMMER, "role": "upper neighbour (hammered)"},
                {"fret": pn.fret, "midi": pn.note.midi, "name": pn.note.name,
                 "stroke": PULL, "role": "return (pulled back)"},
            ],
            "note": f"{pn.fret}h{pn.fret + iv}p{pn.fret} on str{pn.string} — "
                    f"mechanically idle, pure phrasing colour on the target",
            "authentic": "trad", "breaks_2nps": True,
        })
    events.sort(key=lambda e: e["at"])  # report in note order, not priority

    # ---- build ---------------------------------------------------------------
    new: List[PlacedNote] = []
    turned_set = set(turned)
    for i, pn in enumerate(base):
        cur = replace(pn)  # copy; phase-1 list stays untouched
        if i in turned_set:
            cur = replace(cur, note=replace(cur.note, ornament="turn"))
            new.append(cur)
            T = cur.note.onset
            new.append(_turn_grace(cur, cur.fret + iv, HAMMER, T + 1.0 / 3,
                                   bpb, config))
            new.append(_turn_grace(cur, cur.fret, PULL, T + 2.0 / 3,
                                   bpb, config))
        else:
            new.append(cur)

    _recount_runs(new)
    relabel_fingers(new, config)

    # ---- honesty flags ---------------------------------------------------------
    if events:
        flags.append("turns are pure colour (no picking window gained) and the "
                     "first thing to smear at tempo — strip them above ~180 bpm.")
    for start, length, string in _string_runs(new):
        if length >= 3 and any(new[j].note.is_grace
                               for j in range(start, start + length)):
            frets = [new[j].fret for j in range(start, start + length)]
            flags.append(f"2npS BREAK (turn): {length} notes on str{string} "
                         f"(frets {frets}).")
    for v in find_ornament_violations(new):
        flags.append(f"MECHANICS WARNING: {v}")

    picks_before = sum(1 for p in base if p.stroke in _PICKED)
    picks_after = sum(1 for p in new if p.stroke in _PICKED)
    return OrnamentedVoicing(placed=new, events=events, flags=flags,
                             picks_before=picks_before, picks_after=picks_after)
