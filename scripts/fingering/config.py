"""Tunable configuration for the fingering/picking optimizer.

Every weight in the cost function and every playability limit lives here so the
solver is fully steerable ("debug by ear"). Defaults match the spec:

    max_stretch=4, string_range=[1..6], u_cost=low, drop_cost=high,
    quarter_density_scale=0.4, sweep_bonus=small, beat3_penalty=med,
    shift_cost=0.5/fret, break_cost=med, allow_up_arrival=false,
    max_ornaments_per_bar=1 (engine disabled), alt_margin=0.15.

The absolute numbers below encode the *relative* economy the spec demands:

    D (downstroke)  = free                (rest-stroke, maximised by construction)
    U (upstroke)    = u_cost   (small)    a scarce resource, spent only to set
                                          parity so a descending crossing arrives
                                          U->D instead of D->D
    managed drop    = drop_cost * 0.4     (quarter pacing: a full beat to recover)
    parity-U fix    = u_cost              << managed drop, so the solver prefers
                                          the U fix whenever geometry allows it

Because ``u_cost`` (1) is far below the managed drop (drop_cost * 0.4 = 4), the
DP naturally spends an upstroke to dodge a descending drop; because an ascending
crossing costs nothing (and earns a sweep bonus) the DP never manufactures
upstrokes on ascending sweeps. That is the whole game.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import List, Optional, Tuple


# Standard guitar tuning. Strings are numbered 1..6, string 1 = high E
# (thinnest / highest pitch), string 6 = low E (thickest / lowest pitch).
# Values are the MIDI note of each open string.
STANDARD_TUNING_MIDI = {
    1: 64,  # E4
    2: 59,  # B3
    3: 55,  # G3
    4: 50,  # D3
    5: 45,  # A2
    6: 40,  # E2
}


@dataclass
class FingeringConfig:
    # ---- Playability limits -------------------------------------------------
    max_stretch: int = 4               # frets spanned by fingers 1..4 in a box
    allow_stretch_to: int = 5          # index/pinky extension; flagged when used
    max_fret: int = 15                 # highest fret we will place a note on
    string_range: Tuple[int, ...] = (1, 2, 3, 4, 5, 6)
    expected_notes_per_string: int = 2  # the 2npS default layout
    # Open strings as placements. OFF by default: opens are not part of the
    # fretted Gypsy vocabulary (no vibrato/control, dead tone next to rest
    # strokes) and kept sneaking into "best" fingerings near the nut. The ONE
    # sanctioned context is pentatonic runs — scripts/pentatonics/ re-enables
    # them (the 3+2 open-string-pivot system needs the pivot to ring open).
    allow_open_strings: bool = False
    # Optional fret box: when set, placements are confined near [lo, hi] —
    # the box is SOFT: up to window_overflow_frets outside are allowed but
    # charged per fret (players extend a position transiently all the time).
    fret_window: Optional[Tuple[int, int]] = None
    # Per-string windows ((string, lo, hi), ...) for SLANTED shapes (the
    # diagonals): each string gets its own box; ``fret_window`` stays the
    # global envelope. Strings not listed fall back to ``fret_window``.
    string_fret_windows: Optional[Tuple[Tuple[int, int, int], ...]] = None
    window_overflow_frets: int = 2
    window_overflow_cost: float = 1.0
    # Optional root pin: (root_pitch_class, allowed_strings). Key-root notes
    # prefer the shape's root strings (E-shape: 6/4/1 ...) — SOFT: placing a
    # root elsewhere is allowed but charged per occurrence, so shape identity
    # holds unless an idiomatic placement decisively pays for itself.
    root_pin: Optional[Tuple[int, Tuple[int, ...]]] = None
    root_pin_cost: float = 1.0

    # ---- Rhythm / meter -----------------------------------------------------
    beats_per_bar: int = 4             # 4/4 by default; from context if given
    start_beat_index: int = 0          # note 0 falls on this beat offset (0 => beat 1)
    # Quarter grid => every drop has a full beat to recover ("managed") and is
    # genuinely cheap — cheaper than relocating the hand several frets. An
    # eighth/doubled feel scales to 1.0. We do NOT build an unknown-rhythm
    # branch (spec): density is quarter unless context explicitly says "eighth".
    quarter_density_scale: float = 0.2
    eighth_density_scale: float = 1.0

    # ---- Picking / cost weights (lower total = better) ----------------------
    u_cost: float = 0.5                # each upstroke (small; D is free)
    drop_cost: float = 10.0            # a descending crossing arriving D->D
    # Per-CELL exception to the drop rule: {cell name: multiplier} applied to
    # the managed-drop charge when BOTH notes of the crossing belong to that
    # cell (a crossing at the pivot stays at full price). Idiomatic cells that
    # leap downward twice in five notes (e.g. Dorian "Convert style" 3-7-6-5-3)
    # would otherwise sink to the bottom of every ranking.
    cell_drop_scale: Tuple[Tuple[str, float], ...] = (("Convert style", 0.25),)
    sweep_bonus: float = 0.5           # reward an ascending D->D sweep on a beat
    beat3_penalty: float = 2.0         # a U landing on beat 3 (soft)
    shift_cost: float = 1.0            # per fret of hand-anchor movement
    # Relocating the hand mid-phrase costs more than its fret distance: a flat
    # charge per anchor CHANGE keeps the line in one position when possible.
    shift_event_cost: float = 1.0
    # Finger-PAIR span cost: what consecutive fingers can physically cover.
    # Each pair has a max comfortable fret gap (3-4 barely spans 1 fret; 1-4
    # spans 4); every fret beyond the pair's span costs this much. This is the
    # general inter-finger penalty — awkward shapes (e.g. ring landing 2 frets
    # behind pinky) price themselves out without special-case rules.
    finger_span_cost: float = 1.0
    break_cost: float = 3.0            # deviating from the 2npS box (always flagged)
    stretch_cost: float = 3.0          # using the 5-fret extension (always flagged)
    # Within one string, consecutive D-D at this pacing is stiffer than natural
    # up-down alternation: charge it slightly MORE than a U, so same-string
    # pairs come out D-U — except before an ascending crossing, where staying
    # on D earns the sweep bonus and D-D wins.
    same_string_dd_penalty: float = 0.6
    # The same D-D when its second D lands on a downbeat (beat 1/3): repeating
    # the downstroke to put the downbeat on D is accepted, but priced slightly
    # above a plain D-D so the solver prefers fingerings where the downbeat
    # falls on a string change or after an even number of notes on the string.
    downbeat_dd_penalty: float = 1.0
    # Open strings break the hand position mid-line AND dodge all left-hand
    # geometry costs (a fret-0 note has no reach/span/shift) — price them so
    # they never become a teleport loophole.
    open_string_cost: float = 2.0
    # Playing the SAME pitch at a different (string,fret) than an earlier
    # occurrence confuses the hand. When the best path refingers a repeated
    # pitch, a consistency pass re-solves with placements pinned and keeps the
    # consistent solution unless it's worse by more than this per pitch.
    consistency_cost: float = 1.5

    # Physical spread between two consecutive notes on the neck. We charge the
    # Euclidean fretboard distance (horizontal frets + weighted vertical strings)
    # BEYOND a free hand-span, so a normal 2npS box or a swept arpeggio (small
    # fret spread) is free, but an 8-fret leap on one string is expensive.
    reach_cost: float = 0.5            # per distance unit beyond free_reach
    free_reach: float = 4.0            # a hand can span this far for nothing
    string_distance: float = 0.5       # vertical weight: 1 string ~ this many frets

    # allow_up_arrival: if True a U arrival on a *descending* crossing is legal
    # but penalised. Leave False (orthodox Gypsy) unless explicitly told.
    allow_up_arrival: bool = False
    up_arrival_penalty: float = 8.0    # only used when allow_up_arrival is True

    # Which beats grant the sweep bonus. ``None`` => every note that lands on a
    # beat, which in a pure quarter grid is *every* note ("accent on the beat").
    sweep_bonus_beats: Optional[Tuple[int, ...]] = None

    # ---- Search -------------------------------------------------------------
    alt_margin: float = 0.15           # keep a runner-up within this rel. margin
    kbest: int = 3                     # paths tracked per state for the alternate

    # ---- Ornament engine (phase 2 — APPLIED when enabled) -------------------
    # One device only: the upper-neighbor TURN / mordent (pick -> hammer up ->
    # pull back, e.g. 8h10p8) on sustained/target notes. Single string, no
    # crossing, mechanically idle — pure phrasing colour. When enabled it is
    # applied to a COPY of the solution (result.ornamented); the all-picked
    # phase-1 line stays untouched. Strip turns above ~180 bpm (they smear).
    ornament_engine_enabled: bool = False   # master switch (UI toggle)
    turn_fret_interval: int = 2        # upper neighbour: 2 = whole step, 1 = half
    max_ornaments_per_bar: int = 1     # per-bar cap on turns

    def density_scale(self, density: str = "quarter") -> float:
        return self.eighth_density_scale if density == "eighth" else self.quarter_density_scale

    def drop_scale_for(self, cell: Optional[str]) -> float:
        """Managed-drop multiplier for a crossing inside ``cell`` (1.0 = none)."""
        for name, scale in self.cell_drop_scale:
            if name == cell:
                return scale
        return 1.0

    def fret_window_for(self, string: int) -> Optional[Tuple[int, int]]:
        """The (lo, hi) fret box that applies on ``string``."""
        for s, lo, hi in self.string_fret_windows or ():
            if s == string:
                return (lo, hi)
        return self.fret_window

    def with_overrides(self, **kwargs) -> "FingeringConfig":
        """Return a copy with fields overridden (handy for tests)."""
        return replace(self, **kwargs)


def default_config() -> FingeringConfig:
    return FingeringConfig()
