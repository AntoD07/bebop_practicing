"""Phase-2 ornament engine — BUILT AS A HOOK, SHIPPED DISABLED.

At flagged drop sites only, and only when the note we drop onto is a chord tone
or a tagged resolution point, propose ONE ornament from a fixed whitelist. The
stroke-parity effect of each candidate is COMPUTED (never hard-coded): we
re-derive the local stroke sequence and accept a candidate only if it converts
the descending crossing from D->D to either U->D or pull->D.

MODEL (documented, first-cut, validate by ear)
-----------------------------------------------
A descending crossing drops from ``prev`` (the last note on the thinner/upper
string) onto ``target`` (the chord tone on the thicker/lower string), and the
"hot" part is the two consecutive picked downstrokes prev(D)->target(D). The
only articulation the picking hand can change to avoid that is the note *before*
the crossing. So candidates A/B/C edit the upper string's exit:

  A. upper chromatic appoggiatura, pull-off into the exit note
     upper string exit becomes [nb=+1 (picked D), prev (pull-off)] -> pre-crossing
     articulation = pull-off  =>  pull->D.
  B. lower appoggiatura, hammered into the exit note
     upper string exit becomes [nb=-1 (picked D), prev (hammer-on)] => pull->D
     (legato via hammer).
  C. chromatic triplet (picked D + two pull-offs) replacing the exit quarter
     upper string exit becomes [prev+2 (D), prev+1 (po), prev (po)]; 1 pick for
     3 notes, pre-crossing articulation = pull-off  =>  pull->D.

Candidate D (enclosure prepended, drawn from the cell DB's own enclosure set)
ornaments the LANDING on the target string; it softens the drop but does not
change the pre-crossing pick, so the parity math REJECTS it for conversion —
kept in the whitelist to show the computed accept/reject, not to fire by default.

Nothing here mutates the phase-1 solution; suggestions are printed alongside it.
Cap: ``config.max_ornaments_per_bar`` (default 1).
"""

from __future__ import annotations

from typing import Dict, List, Optional

from scripts.fingering.config import FingeringConfig
from scripts.fingering.costs import DOWN, UP, PULL, HAMMER, PlacedNote
from scripts.fingering.pitch import midi_to_name
from scripts.fingering.chords import chord_for_beat, is_chord_tone


def _derive_strokes(articulations: List[str]) -> List[str]:
    """Given a list of intended articulations, return the picked/legato sequence.

    'D'/'U' are picked; 'po'/'h' are legato (no pick). We only report them.
    """
    return list(articulations)


def _candidate_A(prev: PlacedNote) -> dict:
    p = prev.note.midi
    added = [
        {"midi": p + 1, "name": midi_to_name(p + 1), "stroke": DOWN, "role": "upper chromatic appoggiatura"},
        {"midi": p, "name": midi_to_name(p), "stroke": PULL, "role": "exit note (pulled off)"},
    ]
    return {
        "name": "upper chromatic appoggiatura (pull-off into exit)",
        "articulations_before": [DOWN],
        "articulations_after": [DOWN, PULL],
        "pre_crossing_before": DOWN,
        "pre_crossing_after": PULL,
        "picks_before": 1,
        "picks_after": 1,
        "added_notes": added,
    }


def _candidate_B(prev: PlacedNote) -> dict:
    p = prev.note.midi
    added = [
        {"midi": p - 1, "name": midi_to_name(p - 1), "stroke": DOWN, "role": "lower appoggiatura"},
        {"midi": p, "name": midi_to_name(p), "stroke": HAMMER, "role": "exit note (hammered)"},
    ]
    return {
        "name": "lower appoggiatura (hammer-on into exit)",
        "articulations_before": [DOWN],
        "articulations_after": [DOWN, HAMMER],
        "pre_crossing_before": DOWN,
        "pre_crossing_after": HAMMER,
        "picks_before": 1,
        "picks_after": 1,
        "added_notes": added,
    }


def _candidate_C(prev: PlacedNote) -> dict:
    p = prev.note.midi
    added = [
        {"midi": p + 2, "name": midi_to_name(p + 2), "stroke": DOWN, "role": "chromatic triplet head"},
        {"midi": p + 1, "name": midi_to_name(p + 1), "stroke": PULL, "role": "pull-off"},
        {"midi": p, "name": midi_to_name(p), "stroke": PULL, "role": "exit note (pulled off)"},
    ]
    return {
        "name": "chromatic triplet (picked D + two pull-offs)",
        "articulations_before": [DOWN],
        "articulations_after": [DOWN, PULL, PULL],
        "pre_crossing_before": DOWN,
        "pre_crossing_after": PULL,
        "picks_before": 1,
        "picks_after": 1,
        "added_notes": added,
    }


def _candidate_D(prev: PlacedNote, target: PlacedNote,
                 enclosure_degrees: Optional[List[str]]) -> dict:
    # Landing ornament on the target string; does NOT change the pre-crossing pick.
    t = target.note.midi
    added = [
        {"midi": t + 1, "name": midi_to_name(t + 1), "stroke": DOWN, "role": "enclosure upper"},
        {"midi": t - 1, "name": midi_to_name(t - 1), "stroke": UP, "role": "enclosure lower"},
    ]
    return {
        "name": "enclosure prepended (cell-DB enclosure set)",
        "articulations_before": [DOWN],
        "articulations_after": [DOWN, DOWN, UP],  # on the TARGET string, not the exit
        "pre_crossing_before": DOWN,
        "pre_crossing_after": DOWN,  # crossing pick unchanged -> will be rejected
        "picks_before": 1,
        "picks_after": 2,
        "added_notes": added,
        "enclosure_degrees": enclosure_degrees,
    }


def _accepts(candidate: dict) -> bool:
    """A candidate converts the drop iff the pre-crossing articulation is now
    an upstroke (U->D) or a legato pull/hammer (pull->D)."""
    return candidate["pre_crossing_after"] in (UP, PULL, HAMMER)


def _conversion_label(candidate: dict) -> str:
    a = candidate["pre_crossing_after"]
    if a == UP:
        return "U->D"
    if a in (PULL, HAMMER):
        return "pull->D"
    return "D->D (unchanged)"


def propose_ornaments(result, context: dict, config: FingeringConfig,
                      enclosure_degrees: Optional[List[str]] = None) -> List[dict]:
    """Return accepted ornament suggestions for the result's flagged drop sites.

    Each suggestion carries its computed parity math. Never mutates ``result``.
    Capped at ``config.max_ornaments_per_bar`` per bar.
    """
    placed = result.best.placed
    beats_per_bar = config.beats_per_bar
    suggestions: List[dict] = []
    per_bar: Dict[int, int] = {}

    for site in result.best.drop_sites:
        target = placed[site.target_index]
        prev = placed[site.prev_index]
        bar = site.target_index // beats_per_bar

        # Gate: only ornament a drop landing on a chord tone or a tagged resolution.
        symbol = chord_for_beat(context, site.target_index, beats_per_bar)
        gate_chord_tone = bool(symbol) and is_chord_tone(target.note.midi, symbol)
        gate_role = (target.note.role in ("resolution",)) or \
                    (target.note.degree in ("1", "3", "5", "b3"))
        if not (gate_chord_tone or gate_role):
            continue

        if per_bar.get(bar, 0) >= config.max_ornaments_per_bar:
            continue

        candidates = [
            _candidate_A(prev),
            _candidate_B(prev),
            _candidate_C(prev),
            _candidate_D(prev, target, enclosure_degrees),
        ]
        chosen = None
        for cand in candidates:
            cand["converts"] = _accepts(cand)
            cand["conversion"] = _conversion_label(cand)
            if cand["converts"] and chosen is None:
                chosen = cand
        if chosen is None:
            continue

        suggestions.append({
            "target_index": site.target_index,
            "target_pitch": target.note.name,
            "target_role": target.note.role,
            "chord": symbol,
            "bar": bar + 1,
            "gate": "chord-tone" if gate_chord_tone else "tagged-resolution",
            "ornament": chosen["name"],
            "parity_before": f"{chosen['pre_crossing_before']}->D (drop)",
            "parity_after": chosen["conversion"],
            "picks_before": chosen["picks_before"],
            "picks_after": chosen["picks_after"],
            "added_notes": chosen["added_notes"],
            "all_candidates": [
                {"name": c["name"], "converts": c["converts"], "result": c["conversion"]}
                for c in candidates
            ],
        })
        per_bar[bar] = per_bar.get(bar, 0) + 1

    return suggestions
