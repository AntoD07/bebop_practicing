"""Bridge: turn the existing cell engine's output into a pitch ``line``.

The optimizer operates on fixed pitches (per spec). The cell engine, however,
emits *scale-degree strings* (``"1"``, ``"b3"``, ``"#11"``, ``"maj7"`` ...) that
are relative to each cell's harmonic context. This module converts a chain of
cells + a key into an ordered list of ``{"pitch","role","degree","cell"}`` dicts,
choosing octaves so the melodic contour of each cell is preserved and successive
cells stay contiguous (they share their pivot note by construction).

Degree->semitone is MODE-AWARE, as jazz spelling requires: a *bare* degree
number is the mode's own diatonic scale degree, so it carries that mode's
characteristic quality — Dorian ``"3"`` is a minor 3rd, Myxolidian/Dorian
``"7"`` is a flat 7, Locrian ``"5"`` is a flat 5, and so on. Accidental-spelled
tokens (``"b9"``, ``"#11"``, ``"maj7"``, ``"b7"`` ...) are absolute chromatic
intervals from the root, independent of mode. This is a best-effort helper — the
spec-exact entry point is still ``optimize_fingering`` on explicit pitches.
"""

from __future__ import annotations

import ast
import re
from typing import List, Optional, Union

from scripts.domain.catalog import cells as _catalog_cells, find_cell as _find_cell, pivot_hint

_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

# Diatonic semitone of each scale degree (1..7) *within a mode*. A bare degree
# number in a cell means "this degree of this mode", so it inherits the mode's
# flats/naturals. Extensions (9/11/13) fold onto 2/4/6.
_MAJOR = {1: 0, 2: 2, 3: 4, 4: 5, 5: 7, 6: 9, 7: 11}     # Ionian
_DORIAN = {1: 0, 2: 2, 3: 3, 4: 5, 5: 7, 6: 9, 7: 10}    # b3, nat6, b7
_MIXO = {1: 0, 2: 2, 3: 4, 4: 5, 5: 7, 6: 9, 7: 10}      # maj3, b7
_LOCRIAN = {1: 0, 2: 1, 3: 3, 4: 5, 5: 6, 6: 8, 7: 10}   # b2, b3, b5, b6, b7

_MODE_DIATONIC = {
    "Maj7": _MAJOR,
    # "Minor" is the ii-relative melodic-minor vocabulary (the pre-rename
    # "Dorian" CSV, #7 kept); "Dorian" is its #7-free subset. Same diatonic
    # base — #7/maj3 are absolute tokens.
    "Minor": _DORIAN,
    "Dorian": _DORIAN,
    "Myxolidian": _MIXO, "7sus4": _MIXO,
    # Resolution cells are DOMINANT-based: their degrees are spelled from the
    # V7 chord that resolves, NOT from the tonic they land on (e.g. in a D-major
    # 2-5-1 the resolution cell reads from A7, resolving into D).
    "MajorResolutions": _MIXO, "MinorResolutions": _MIXO,
    "Locrian": _LOCRIAN,
    # Tonic readings for resolution cells whose degrees were TRANSLATED to the
    # I-chord representation (the pages' "translate Dominant to Minor/Major-I"
    # checkboxes rewrite the degrees; these virtual modes read that form).
    "MajorTonic": _MAJOR, "MinorTonic": _DORIAN,
}

# Accidental-spelled / fixed tokens: absolute chromatic interval from the root,
# regardless of mode. (Bare "7"/"3"/"6"/... are NOT here — they go mode-diatonic.)
_ABSOLUTE_DEGREE = {
    "b2": 1, "b9": 1, "#2": 3, "#9": 3, "b3": 3, "maj3": 4, "min3": 3,
    "#4": 6, "#11": 6, "b5": 6, "#5": 8, "b6": 8, "b7": 10,
    "maj7": 11, "#7": 11, "#8": 12,
}

_DEGREE_ROLE = {
    "1": "root", "3": "3rd", "b3": "b3", "5": "5", "7": "7th", "maj7": "7th",
    "b7": "b7", "9": "9", "2": "9", "b9": "b9", "#9": "#9", "6": "6", "13": "6",
    "11": "11", "4": "11", "#11": "#11", "#4": "#11", "b5": "b5", "#5": "#5",
    "b6": "b6", "#8": "root",
}

# Default mode->root offset from the key tonic, interpreting a line as a ii-V-i
# (the common case in this app). Override per line-type when needed.
DEFAULT_MODE_ROOT_OFFSET = {
    "Maj7": 0, "MajorResolutions": 7, "Myxolidian": 7, "Minor": 2, "Dorian": 2,
    "Locrian": 2, "MinorResolutions": 7, "7sus4": 7,
    "MajorTonic": 0, "MinorTonic": 0,
}

# Jazz chord-symbol spelling (Eb7, not D#7) — today's keys are named this way.
_PC_NAMES = ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
_MODE_QUALITY = {
    "Myxolidian": "7", "7sus4": "7sus4", "Locrian": "m7b5",
    "Minor": "m7", "Dorian": "m7",
    "Maj7": "maj7", "MajorResolutions": "7", "MinorResolutions": "7",
    "MajorTonic": "maj7", "MinorTonic": "m6",
}

# Vocabularies played over the SAME chord (Minor = Dorian + the #7 cells).
_CHORD_FAMILY = {"Minor": "m7", "Dorian": "m7"}
# Resolution cells always move V -> I, so they never form a single-chord line.
_RESOLUTION_MODES = {"MajorResolutions", "MinorResolutions"}


def is_single_chord(modes) -> bool:
    """True when every cell is played over ONE chord (Dorian -> Dorian,
    Minor -> Dorian, Myxolidian -> Myxolidian ...). Pass the ORIGINAL CSV mode
    names, not translated reading modes."""
    modes = list(modes)
    if not modes or any(m in _RESOLUTION_MODES for m in modes):
        return False
    return len({_CHORD_FAMILY.get(m, m) for m in modes}) == 1


def root_offset(mode: str, single_chord: bool = False) -> int:
    """Semitones from today's key up to a cell's chord root.

    Single chord: today's key IS that chord's root (Eb + Dorian -> Ebm7).
    Otherwise the line is read as a ii-V-I and today's key is the I
    (Eb + Dorian -> Myxolidian -> Fm7 -> Bb7).
    """
    return 0 if single_chord else DEFAULT_MODE_ROOT_OFFSET.get(mode, 0)


def chord_symbol_for_mode(key, mode: str, single_chord: bool = False) -> str:
    """Chord symbol of a mode's root in a key (see :func:`root_offset`):
    C + 'Dorian' -> 'Dm7' in a ii-V-I, 'Cm7' when the line is single-chord."""
    pc = (root_pc(key) + root_offset(mode, single_chord)) % 12
    return _PC_NAMES[pc] + _MODE_QUALITY.get(mode, "")


def chord_symbol_for_root_pc(pc: int, mode: str) -> str:
    """Chord symbol from an explicit root pitch class (for derived roots)."""
    return _PC_NAMES[pc % 12] + _MODE_QUALITY.get(mode, "")


# Cell names may HINT the true sounding degree of their first note, e.g.
# "Bill Evans enclosure (from #9)" — see ``scripts.domain.catalog.pivot_hint``
# (the catalog parses it once per cell; kept here under its old name).
_pivot_hint = pivot_hint


def _append_cell_at_pivot(line: List[dict], cell: dict):
    """Extend ``line`` with ``cell``, sharing the pivot note (in place).

    The current last note of ``line`` IS the first note of ``cell`` — a single
    event. The cell's root is DERIVED from the pivot pitch (transposed so its
    NOMINAL Start-Note degree lands exactly there); its remaining notes are
    voiced from the pivot by the usual octave search (movement contour +
    markers). If the cell's name hints a different sounding degree for its
    first note ("(from #9)"), the pivot is RE-PITCHED to that degree of the
    same derived root — the previous cell's ending note changes pitch (e.g. a
    3rd becomes the #9, a semitone lower) while pivot matching stays nominal.

    Returns ``(pivot_index, derived_root_pc)``.
    """
    pivot_midi = line[-1]["pitch"]
    pivot_index = len(line) - 1

    mode = cell.get("mode")
    degrees = cell["degrees"]
    core0, marker0 = _split_marker(degrees[0])
    root_pc_val = (pivot_midi - degree_to_semitone(core0, mode)) % 12

    pivot_update = {"role": "pivot"}
    hint = _pivot_hint(cell.get("name"))
    if hint:
        try:
            delta = ((degree_to_semitone(hint, mode)
                      - degree_to_semitone(core0, mode) + 6) % 12) - 6
        except (KeyError, ValueError):
            delta = 0  # unparseable hint token -> leave the pivot as written
        if delta:
            pivot_midi += delta
            core0 = hint  # the cell's first pc IS the hinted degree
            pivot_update.update(pitch=pivot_midi, degree=hint)

    pcs_markers, cleaned = [], []
    for k, deg in enumerate(degrees):
        core, marker = _split_marker(deg)
        if k == 0:
            core = core0
        pcs_markers.append(((root_pc_val + degree_to_semitone(core, mode)) % 12, marker))
        cleaned.append((core, marker))
    # First note pinned to the pivot pitch (same pc, nearest octave = exact).
    midis = _assign_cell_octaves(pcs_markers, pivot_midi, cell.get("movement"),
                                 free_first=False)

    line[pivot_index] = dict(line[pivot_index], **pivot_update)
    for k in range(1, len(degrees)):
        core, marker = cleaned[k]
        label = core + ("↑" if marker == "higher" else "↓" if marker == "lower" else "")
        line.append({
            "pitch": midis[k],
            "role": degree_to_role(core),
            "degree": label,
            "cell": cell["name"],
        })
    return pivot_index, root_pc_val


# Cell rhythm: cell notes are EIGHTH notes (the player's reading). A 5-note
# cell is 4 eighths + the pivot, so pivot-chained cells stride 2 beats and
# every pivot lands on a downbeat (beat 1 or 3) of a 4/4 bar.
CELL_NOTE_BEATS = 0.5
CELL_BEATS_PER_BAR = 4


def cell_beat(index: int) -> float:
    """Onset, in beats, of the ``index``-th note of a cell line."""
    return index * CELL_NOTE_BEATS


def timed_cell_line(line: List[dict]) -> List[dict]:
    """Copy of a cell ``line`` with each note's eighth-note onset stamped."""
    return [dict(n, start=cell_beat(i)) for i, n in enumerate(line)]


def cell_context(context: dict) -> dict:
    """Copy of ``context`` on the cell grid: 4/4 bars, eighth-note pacing
    (drops priced at eighth tempo). Chord ``start_beat`` values are in beats —
    compute them with :func:`cell_beat`."""
    return dict(context, beats_per_bar=CELL_BEATS_PER_BAR, density="eighth")


def build_connection_line(cell1: dict, cell2: dict, base_midi: int = 60):
    """Join two cells at their pivot as ONE line (the pivot note is shared).

    Returns ``(line, pivot_index, root2_pc)``.
    """
    line = build_pitch_line([cell1], base_midi=base_midi)
    pivot_index, root2_pc = _append_cell_at_pivot(line, cell2)
    return line, pivot_index, root2_pc


def build_chain_line(cells: List[dict], base_midi: int = 60):
    """Join N pivot-connected cells into ONE line (each pivot note shared).

    The first cell anchors the register; every subsequent cell's root is
    derived from its pivot so the whole chain is literally seamless. Returns
    ``(line, pivot_indices, root_pcs)`` where ``root_pcs[k]`` is cell k's root
    pitch class (cell 0's as given, later ones derived).
    """
    line = build_pitch_line([cells[0]], base_midi=base_midi)
    pivots: List[int] = []
    roots: List[int] = [root_pc(cells[0]["root"])]
    for cell in cells[1:]:
        pidx, rpc = _append_cell_at_pivot(line, cell)
        pivots.append(pidx)
        roots.append(rpc)
    # A long chain can drift off the neck; shift the WHOLE line by octaves
    # (uniform => pivot continuity preserved) back into playable range.
    CEIL, FLOOR = 79, 40  # high-E fret 15 .. open low E
    midis = [n["pitch"] for n in line]
    shift = 0
    while max(midis) + shift > CEIL:
        shift -= 12
    while min(midis) + shift < FLOOR:
        shift += 12
    if shift:
        for n in line:
            n["pitch"] += shift
    return line, pivots, roots


def root_pc(name: Union[str, int]) -> int:
    """Pitch class (0..11) for a note name like ``"A"``, ``"Bb"``, ``"F#"``."""
    if isinstance(name, int):
        return name % 12
    s = name.strip()
    pc = _PC[s[0].upper()]
    for acc in s[1:]:
        if acc == "#":
            pc += 1
        elif acc == "b":
            pc -= 1
    return pc % 12


def degree_to_semitone(deg: str, mode: Optional[str] = None) -> int:
    """Semitone (mod-12, from the root) of a jazz scale-degree string in a mode.

    Bare numbers are read as the mode's own diatonic degree (so Dorian "3" -> 3 =
    minor 3rd, Myxolidian "7" -> 10 = b7). Accidental-spelled tokens are absolute.
    """
    d = deg.strip().replace("(higher)", "").replace("(lower)", "").strip()
    if not d:
        return 0
    if d in _ABSOLUTE_DEGREE:
        return _ABSOLUTE_DEGREE[d]
    m = re.match(r"^([#b]*)(\d+)$", d)
    if not m:
        return 0
    accs, num = m.group(1), int(m.group(2))
    reduced = ((num - 1) % 7) + 1          # 9->2, 11->4, 13->6, 8->1(octave)
    table = _MODE_DIATONIC.get(mode, _MAJOR)
    semi = table.get(reduced, _MAJOR[reduced])
    for a in accs:                         # explicit accidentals still shift
        semi += 1 if a == "#" else -1
    return semi                            # build_pitch_line reduces mod 12


def degree_to_role(deg: str) -> str:
    return _DEGREE_ROLE.get(deg.strip(), "chromatic-approach")


def _nearest_octave_midi(pc: int, ref: int, movement: Optional[str]) -> int:
    """Place a pitch class in the octave nearest ``ref`` (voice-leading).

    This is the key to honouring the jazz reading: a "9" is pitch class 2 (not a
    hard +14), a "#11" is pitch class 6, etc. — the *contour* comes from choosing
    each note's octave nearest the previous note, so a descending line keeps
    descending and never jumps up an octave. ``movement`` only breaks the
    tritone tie (equal distance up/down): 'D' picks the lower, 'A' the higher.
    """
    cands = [pc + 12 * o for o in range(2, 8) if 33 <= pc + 12 * o <= 96]
    if not cands:
        cands = [pc + 12 * o for o in range(0, 9)]
    best = min(cands, key=lambda m: abs(m - ref))
    tied = [m for m in cands if abs(m - ref) == abs(best - ref)]
    if len(tied) > 1:
        return min(tied) if movement == "D" else max(tied) if movement == "A" else min(tied)
    return best


_MARKER_RE = re.compile(r"\((higher|lower)\)\s*$")


def _split_marker(deg: str):
    """Split an explicit octave marker off a degree string.

    The cell DB spells octave displacement as ``b9(higher)`` / ``b6(lower)``:
    play that degree in the octave ABOVE / BELOW the previous note, overriding
    nearest-octave voice-leading.
    """
    m = _MARKER_RE.search(deg)
    if m:
        return deg[: m.start()].strip(), m.group(1)
    return deg.strip(), None


def _octave_candidates(pc: int, prev: int, marker: Optional[str],
                       max_leap: int = 16) -> List[int]:
    """Playable octave placements of ``pc`` around ``prev``, marker-filtered."""
    base = prev - (prev % 12) + pc
    out = []
    for k in (-2, -1, 0, 1, 2):
        m = base + 12 * k
        if not (33 <= m <= 96):
            continue
        iv = m - prev
        if abs(iv) > max_leap:
            continue
        if marker == "higher" and iv <= 0:
            continue
        if marker == "lower" and iv >= 0:
            continue
        out.append(m)
    return out or [_nearest_octave_midi(pc, prev, None)]


def _assign_cell_octaves(pcs_markers: List[tuple], first_ref: int,
                         movement: Optional[str],
                         free_first: bool = False) -> List[int]:
    """Choose each note's octave for one cell (the octave-displacement search).

    Movement is a HARD contour constraint — a 'D' cell must END below its start,
    'A' above — and explicit ``(higher)``/``(lower)`` markers force the leap
    direction at that note. Among satisfying assignments we minimise, in order:
      1. the largest leap        (unconstrained cells stay pure nearest-octave),
      2. the total motion,
      3. how LATE the big leap happens (prefer it EARLY — jazz convention: the
         displaced note is the FIRST one, e.g. an arpeggio's root played an
         octave up before the 3-5-7 runs beneath it; and the resolution at the
         end of a cell is never the note that gets displaced),
      4. distance of the first note from its register anchor.

    ``free_first`` lets the first note pick its own octave around ``first_ref``
    (used at the START of a line); chained cells keep it pinned so the pivot
    note stays contiguous with the previous cell.
    """
    n = len(pcs_markers)
    first_pc, first_marker = pcs_markers[0]
    if free_first:
        first_cands = [m for m in _octave_candidates(first_pc, first_ref, first_marker)
                       if abs(m - first_ref) <= 11]
        if not first_cands:
            first_cands = [_nearest_octave_midi(first_pc, first_ref, movement)]
    else:
        first_cands = [_nearest_octave_midi(first_pc, first_ref, movement)]

    best = None  # (key, path)

    def leaf_key(path):
        leaps = [abs(path[i + 1] - path[i]) for i in range(len(path) - 1)]
        mx = max(leaps) if leaps else 0
        sm = sum(leaps)
        # Prefer the displacement leap as EARLY as possible (jazz convention).
        first_mx_pos = min((i for i, l in enumerate(leaps) if l == mx), default=0)
        return (mx, sm, first_mx_pos, abs(path[0] - first_ref))

    def dfs(i, path):
        nonlocal best
        if i == n:
            end, start = path[-1], path[0]
            if n > 1 and movement == "D" and not end < start:
                return
            if n > 1 and movement == "A" and not end > start:
                return
            key = leaf_key(path)
            if best is None or key < best[0]:
                best = (key, list(path))
            return
        pc, marker = pcs_markers[i]
        for m in _octave_candidates(pc, path[-1], marker):
            dfs(i + 1, path + [m])

    for f in first_cands:
        dfs(1, [f])
    if best is None:
        # Movement can't be satisfied (unexpected data) — fall back to nearest.
        path = [first_cands[0]]
        for pc, marker in pcs_markers[1:]:
            path.append(_octave_candidates(pc, path[-1], marker)[0]
                        if marker else _nearest_octave_midi(pc, path[-1], movement))
        return path
    return best[1]


def build_pitch_line(cells: List[dict], base_midi: int = 60,
                     first_note_target: Optional[int] = None) -> List[dict]:
    """Build a pitch ``line`` from explicit cells using nearest-octave voice-leading.

    Each cell dict: ``{"name", "root", "degrees", "mode"?, "movement"?,
    "is_resolution"?}``. Each note is placed in the octave nearest the previous
    note, so the written contour (and ascending/descending intent) is preserved
    without octave jumps.

    The first note anchors the register: pass ``first_note_target`` for an exact
    register (positions do this so the fret box lines up); otherwise an ascending
    line starts low and a descending line starts high, so it has room to travel.
    """
    line: List[dict] = []
    if first_note_target is not None:
        prev = first_note_target
    else:
        mv0 = cells[0].get("movement") if cells else None
        prev = base_midi - 8 if mv0 == "A" else base_midi + 11 if mv0 == "D" else base_midi
    for c in cells:
        pc0 = root_pc(c["root"])
        mode = c.get("mode")
        movement = c.get("movement")
        degrees = c["degrees"]
        # Parse degrees: pitch class + explicit (higher)/(lower) octave marker.
        pcs_markers = []
        cleaned = []
        for deg in degrees:
            core, marker = _split_marker(deg)
            pcs_markers.append(((pc0 + degree_to_semitone(core, mode)) % 12, marker))
            cleaned.append((core, marker))
        # Run the octave-displacement search (movement contour + markers). The
        # line's FIRST cell may pick its opening octave around the register
        # anchor; subsequent cells stay pinned to the pivot for continuity.
        midis = _assign_cell_octaves(pcs_markers, prev, movement,
                                     free_first=(not line))
        for k, ((core, marker), midi) in enumerate(zip(cleaned, midis)):
            role = degree_to_role(core)
            if c.get("is_resolution") and k == len(degrees) - 1:
                role = "resolution"
            label = core + ("↑" if marker == "higher" else "↓" if marker == "lower" else "")
            line.append({
                "pitch": midi,
                "role": role,
                "degree": label,
                "cell": c["name"],
            })
            prev = midi

    # Fit the whole line into the guitar's range (standard tuning, 15 frets):
    # shift by octaves so it stays playable. Skipped when a position pins the
    # register (it manages its own box). Preserves contour exactly.
    if first_note_target is None and line:
        CEIL, FLOOR = 79, 40  # high-E fret 15 (G5) .. open low E (E2)
        midis = [n["pitch"] for n in line]
        shift = 0
        while max(midis) + shift > CEIL:
            shift -= 12
        while min(midis) + shift < FLOOR:
            shift += 12
        if shift:
            for n in line:
                n["pitch"] += shift
    return line


# --------------------------------------------------------------------------- #
# Real cells from the cell catalog (scripts.domain.catalog reads the CSVs once)
# --------------------------------------------------------------------------- #
def cell_degrees(mode: str, name: str) -> List[str]:
    """Degree list for a named cell (first match, any type) in a mode."""
    c = _find_cell(mode, name)
    if c is None:
        raise KeyError(f"cell {name!r} not found in {mode}")
    return list(c.degrees)


def first_cell(mode: str, contains: Optional[str] = None,
               movement: Optional[str] = None) -> dict:
    """Return the first (optionally filtered) cell of a mode as a bridge dict."""
    for c in _catalog_cells(mode, bonus=True):
        if movement is not None and str(c.movement) != movement:
            continue
        if contains is not None and contains.lower() not in c.name.lower():
            continue
        return {"name": c.name, "degrees": list(c.degrees), "mode": mode,
                "movement": str(c.movement) if c.movement is not None else None}
    raise KeyError(f"no matching cell in {mode}")


def cell_movement(mode: str, name: str) -> Optional[str]:
    """Movement (A/D/N) of a named cell, looked up from the catalog."""
    try:
        c = _find_cell(mode, name)
    except KeyError:
        return None
    return None if c is None or c.movement is None else str(c.movement)


def enclosure_degree_sequences(modes: Optional[List[str]] = None) -> List[List[str]]:
    """Degree lists of cells that are enclosures, drawn from the cell DB."""
    modes = modes or ["Maj7", "Myxolidian", "Locrian", "MinorResolutions",
                       "MajorResolutions", "Minor", "Dorian"]
    out: List[List[str]] = []
    for mode in modes:
        try:
            cells = _catalog_cells(mode, bonus=True)
        except KeyError:
            continue
        out.extend(list(c.degrees) for c in cells if "nclosure" in c.name.lower())
    return out


def line_from_engine(melodic_line: List[str], note_representations: List, mode_list: List[str],
                     key: str, mode_root_offset: Optional[dict] = None,
                     base_midi: int = 57,
                     movement_modes: Optional[List[str]] = None) -> List[dict]:
    """Best-effort adapter for the live engine output (approximate roots).

    ``melodic_line`` cell names, ``note_representations`` the parallel degree
    lists, ``mode_list`` the mode per cell, ``key`` the tonic. Roots are derived
    from ``mode_root_offset`` (default ii-V-i interpretation). When degrees
    were TRANSLATED to another representation, ``mode_list`` carries the
    reading mode while ``movement_modes`` names the ORIGINAL sampling CSVs, so
    the Movement lookup finds the right cell. Documented as approximate — pass
    explicit cells to :func:`build_pitch_line` for exactness.
    """
    offsets = mode_root_offset or DEFAULT_MODE_ROOT_OFFSET
    mv_modes = movement_modes or mode_list
    key_pc = root_pc(key)
    cells = []
    n = len(mode_list)
    for i, (name, notes, mode) in enumerate(zip(melodic_line, note_representations, mode_list)):
        degs = notes if isinstance(notes, list) else [s.strip() for s in ast.literal_eval(str(notes))]
        cells.append({
            "name": name,
            "root": (key_pc + offsets.get(mode, 0)) % 12,
            "degrees": degs,
            "mode": mode,
            "movement": cell_movement(mv_modes[i], name),
            "is_resolution": ("Resolution" in mode) and (i == n - 1),
        })
    return build_pitch_line(cells, base_midi=base_midi)
