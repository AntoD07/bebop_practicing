import streamlit as st
import streamlit.components.v1 as components

import ast
import time

import pandas as pd

from scripts.utils import (
    sidebar_practice_key,
    sidebar_metronome,
    join_notes,
)

from scripts.melodic_lines.combinations import find_combinations_on_pivot_new

from scripts.fingering.config import FingeringConfig
from scripts.fingering.optimizer import optimize_fingering, enumerate_fingerings
from scripts.fingering.render import render_html, format_report
from scripts.fingering.cell_bridge import (
    build_connection_line,
    cell_beat,
    cell_context,
    chord_symbol_for_mode,
    chord_symbol_for_root_pc,
    is_single_chord,
    root_offset,
    root_pc,
    timed_cell_line,
)
from scripts.fingering.positions import (
    classify_position,
    classify_positions,
    position_boxes,
    position_signature,
    POSITION_SLACK,
    POSITIONS,
)


from scripts.modes.mode_transposition import (
    translate_dom_to_minor,
    translate_dom_to_major,
    translate_dom_to_dorian,
)
from scripts.melodic_lines.melodic_lines import combo_mapping_info

from scripts.load_cells import create_cell_frames
from scripts.paths import LOGS_DIR
import os
import json
import datetime as _dt

CONNECTION_PICKS = os.path.join(str(LOGS_DIR), "connection_picks.json")


def _load_picks() -> dict:
    try:
        with open(CONNECTION_PICKS) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_picks(picks: dict) -> None:
    os.makedirs(os.path.dirname(CONNECTION_PICKS), exist_ok=True)
    with open(CONNECTION_PICKS, "w") as f:
        json.dump(picks, f, indent=1)


def _layout_sig(result) -> str:
    """A fingering's string/fret layout, e.g. '3/14 3/12 4/14' (stable id)."""
    return " ".join(f"{p.string}/{p.fret}" for p in result.best.placed)


def _pair_key(row) -> str:
    return f"{row['end']} → {row['start']}"


def _anchor_pc_of(row):
    """Root pitch class the row's position was anchored on (for labelling)."""
    return row.get("anchor_pc", st.session_state.key)


def _sticky_checkbox(label, state_key, default=False, **kw):
    """A checkbox whose value survives a mid-page ``st.rerun()``.

    Streamlit drops the state of keyed widgets that were not drawn yet when a
    run is cut short by ``st.rerun()`` (our Keep/Delete buttons), so a plain
    keyed checkbox placed below those buttons snaps back to its default. The
    value is kept in ``state_key`` (a non-widget key), copied in by on_change,
    and the widget is re-seeded from it on every run.
    """
    st.session_state[state_key] = st.session_state.get(state_key, default)
    wkey = f"_w_{state_key}"
    st.session_state[wkey] = st.session_state[state_key]

    def _sync():
        st.session_state[state_key] = st.session_state[wkey]

    st.checkbox(label, key=wkey, on_change=_sync, **kw)
    return st.session_state[state_key]


def _primary_label(placed, anchor_pc, position):
    """'<shape> · frets a–b': the ENFORCED position when the fingering fits it
    (boxes overlap once the tolerance is on), else the first matching shape."""
    names = classify_positions(placed, anchor_pc)
    frets = [p.fret for p in placed if p.fret > 0]
    span = f"frets {min(frets)}–{max(frets)}" if frets else "open strings"
    if position in names:
        return f"{position} · {span}"
    return f"{names[0]} · {span}" if names else span


def _in_position(f, row):
    pos = st.session_state.fingering_position
    return pos not in POSITIONS or pos in classify_positions(f.best.placed, _anchor_pc_of(row))


def _candidate_fingerings(row):
    """This connection's fingerings inside the position and under the max cost."""
    return [f for f in row.get("fingerings") or []
            if _in_position(f, row) and f.best.total_cost <= st.session_state.max_fing_cost]


def _kept_fingerings(row, deleted):
    """Candidates minus the ones you deleted — what the exercise practises."""
    gone = deleted.get(_pair_key(row), set())
    return [f for f in _candidate_fingerings(row) if _layout_sig(f) not in gone]


st.set_page_config(layout="wide")
# Example of setting up the practice routine
st.title("Practicing Bebop Cell combinations")

st.session_state.key, st.session_state.position = sidebar_practice_key()
sidebar_metronome()
_FREE = "Free (best on the neck)"
st.session_state.enforce_position = st.session_state.get("enforce_position", True)
st.sidebar.checkbox(
    "Enforce the position",
    key="enforce_position",
    help="On: every connection is forced into today's position (selected "
         "above), anchored on today's key (or the chord chosen above the "
         "fingering table). "
         "Off: Free — the single cheapest fingering anywhere on the neck.",
)
st.session_state.fingering_position = (
    POSITIONS[st.session_state.position - 1]
    if st.session_state.enforce_position else _FREE
)
st.session_state.include_bonus = st.session_state.get("include_bonus", False)
st.sidebar.checkbox("Whether to include bonus cells", key="include_bonus")
st.session_state.max_fing_cost = st.session_state.get("max_fing_cost", 15.0)
st.sidebar.slider(
    "Max fingering cost to display", 0.0, 40.0, step=0.5, key="max_fing_cost",
    help="Fingerings of a connection costing more than this are hidden from the "
         "list below the table (the cheapest one is always the exercise's).",
)
# Use key and position in your Streamlit application
c1, c2 = st.columns((0.5, 0.5))

with c1:
    st.session_state.chord1 = st.selectbox(
        "Select first chord to practice",
        [
            "Maj7",
            # "7sus4",
            "Minor",
            "Dorian",
            "Myxolidian",
            "Locrian",
            "MajorResolutions",
            "MinorResolutions",
        ],
        index=[
            "Maj7",
            # "7sus4",
            "Minor",
            "Dorian",
            "Myxolidian",
            "Locrian",
            "MajorResolutions",
            "MinorResolutions",
        ].index(st.session_state.get("chord1", "Minor")),
    )
    # st.session_state.permute1 = st.checkbox(
    #     "Whether to change to translate the intervals for other modes", value=False
    # )
    # st.session_state.mode_filter1 = st.checkbox(
    #     "Whether to filter cells with high mode score", value=False
    # )
    # if st.session_state.chord1 == "Locrian":
    #     st.session_state.loc_2_dom1 = st.checkbox(
    #         "Translate Locrian to Dominant", value=False
    #     )
    # else:
    #     st.session_state.loc_2_dom1 = False
    if st.session_state.chord1 in [
        "MinorResolutions",
        "MajorResolutions",
        "Locrian",
        "Myxolidian",
    ]:
        st.session_state.dom_to_minor1 = st.checkbox(
            "Translate Dominant to Minor/Major-I", value=False
        )
    else:
        st.session_state.dom_to_minor1 = False

    df_cells_1, mapped_names_1, mapping_1 = create_cell_frames(
        st.session_state.chord1,
        False,
        False,
        st.session_state.include_bonus,
        "End Note",
        False,
        st.session_state.dom_to_minor1,
    )

with c2:
    st.session_state.chord2 = st.selectbox(
        "Select second chord to connect to",
        [
            "Maj7",
            # "7sus4",
            "Minor",
            "Dorian",
            "Myxolidian",
            "Locrian",
            "MajorResolutions",
            "MinorResolutions",
        ],
        index=3,
    )
    # Dorian/Minor -> Myxolidian: re-spell the Myxolidian cells from the ii
    # root so both sides share one representation and the pivots line up.
    _myxo_to_dorian = (st.session_state.chord1 in ("Dorian", "Minor")
                       and st.session_state.chord2 == "Myxolidian")
    # st.session_state.mode_filter_2 = st.checkbox(
    #     "Whether to filter cells with high mode score ", value=False
    # )
    # Locrian to dominant
    # if st.session_state.chord2 == "Locrian":
    #     st.session_state.loc_2_dom_2 = st.checkbox(
    #         "Translate Locrian to Dominant ", value=False
    #     )
    # else:
    #     st.session_state.loc_2_dom_2 = False
    # Minor Resolution Cell transposition
    if st.session_state.chord2 in [
        "MinorResolutions",
        "MajorResolutions",
        "Locrian",
        "Myxolidian",
    ] and not _myxo_to_dorian:
        st.session_state.dom_to_minor2 = st.checkbox(
            "Translate Dominant to Minor/Major-I ", value=False
        )
    else:
        st.session_state.dom_to_minor2 = False

    df_cells_2, mapped_names_2, mapping_2 = create_cell_frames(
        st.session_state.chord2,
        False,
        False,
        st.session_state.include_bonus,
        "Start Note",
        False,
        st.session_state.dom_to_minor2,
    )
    if _myxo_to_dorian:
        df_cells_2 = translate_dom_to_dorian(df_cells_2)
        mapped_names_2 = df_cells_2["Start Note"].astype(str).unique()
        mapping_2 = {n: n for n in mapped_names_2}

if _myxo_to_dorian:
    st.info(combo_mapping_info())


st.subheader("", divider="red")


# Pivot notes common to both sides, in degree order; "3" is the default pivot
# (the most practised connection note) whenever both sides offer it.
_DEGREE_ORDER = ["1", "b9", "9", "#9", "3", "maj3", "4", "11", "#11", "5", "#5",
                 "b6", "6", "b7", "7", "#7", "maj7"]
_pivots = sorted(set(mapped_names_1.astype(str)) & set(mapped_names_2.astype(str)),
                 key=lambda n: (_DEGREE_ORDER.index(n) if n in _DEGREE_ORDER else 99, n))
st.session_state.tone_modified = st.selectbox(
    "Select a pivot note (starting second cell)",
    _pivots,
    index=_pivots.index("3") if "3" in _pivots else 0,
)

st.session_state.movement = st.sidebar.selectbox(
    "Select the line movement (optional) ",
    [None, "A", "D"],
    index=[None, "A", "D"].index(st.session_state.get("movement", None)),
)
st.session_state.tone = mapping_2[st.session_state.tone_modified]
if st.session_state.movement is None:
    movements = ["N", "A", "D"]
else:
    movements = ["N", st.session_state.movement]

starting_cells = df_cells_2.loc[
    (df_cells_2["Start Note"] == st.session_state.tone)
    & df_cells_2["Movement"].astype(str).isin(movements)
]
ending_cells = df_cells_1.loc[
    (df_cells_1["End Note"] == mapping_1[st.session_state.tone_modified])
    & df_cells_1["Movement"].astype(str).isin(movements)
]

if st.session_state.chord1 == "Locrian":
    st.write("Locrian cells are translated to Dominant by default")
if (
    st.session_state.chord1 in ["MinorResolutions", "Locrian"]
) and st.session_state.dom_to_minor1:
    ending_cells = translate_dom_to_minor(ending_cells)
elif (
    st.session_state.chord1 in ["Myxolidian", "MajorResolutions"]
) and st.session_state.dom_to_minor1:
    ending_cells = translate_dom_to_major(ending_cells)


# if st.session_state.chord2 == "Locrian" and st.session_state.loc_2_dom_2:
#     starting_cells = translate_loc_to_dominant(starting_cells)
if (
    st.session_state.chord2 in ["MinorResolutions", "Locrian"]
) and st.session_state.dom_to_minor2:
    starting_cells = translate_dom_to_minor(starting_cells)
elif (
    st.session_state.chord2 in ["Myxolidian", "MajorResolutions"]
) and st.session_state.dom_to_minor2:
    starting_cells = translate_dom_to_major(starting_cells)

st.session_state.use_cell_selector = st.checkbox(
    "Filter cells by selection", value=False
)

# Cell selectors outside expander (conditional)
if st.session_state.use_cell_selector:
    c1, c2 = st.columns((0.5, 0.5))

    with c1:
        st.write(f"**{st.session_state.chord1} Cells** (ending)")
        ending_cell_names = ending_cells.index.tolist()
        st.session_state.selected_ending_cells = st.multiselect(
            "Select ending cells:",
            ending_cell_names,
            default=ending_cell_names,
            key="ending_cells_selector",
        )

    with c2:
        st.write(f"**{st.session_state.chord2} Cells** (starting)")
        starting_cell_names = starting_cells.index.tolist()
        st.session_state.selected_starting_cells = st.multiselect(
            "Select starting cells:",
            starting_cell_names,
            default=starting_cell_names,
            key="starting_cells_selector",
        )

    # Filter cells based on selection
    ending_cells_filtered = ending_cells.loc[
        ending_cells.index.isin(st.session_state.selected_ending_cells)
    ]
    starting_cells_filtered = starting_cells.loc[
        starting_cells.index.isin(st.session_state.selected_starting_cells)
    ]
else:
    ending_cells_filtered = ending_cells
    starting_cells_filtered = starting_cells

with st.expander("Show Cells"):
    c1, c2 = st.columns((0.5, 0.5))
    for i, cell in ending_cells_filtered.reset_index().iterrows():
        n = cell["Cell Name"]
        notes = cell["Notes"]
        mvt = cell["Movement"]

        c1.write(f"##### {n}")
        c1.write(join_notes(notes) + "  " + mvt)

    for i, cell in starting_cells_filtered.reset_index().iterrows():
        n = cell["Cell Name"]
        notes = cell["Notes"]
        mvt = cell["Movement"]

        c2.write(f"##### {n}")
        c2.write(join_notes(notes) + "  " + mvt)

combinations, names = find_combinations_on_pivot_new(
    st.session_state.tone, starting_cells_filtered, ending_cells_filtered
)

st.subheader(
    "Practicing cells around chord tone :blue[{}] - All :red[{}] combinaisons".format(
        st.session_state.tone_modified, len(combinations)
    ),
)


# --------------------------------------------------------------------------- #
# Fingering + score for every pairwise connection (same engine as the quiz).
# --------------------------------------------------------------------------- #
def _cell_records(df):
    """Hashable (name, degrees, movement) tuples for st.cache_data."""
    recs = []
    for _, row in df.reset_index().iterrows():
        notes = row["Notes"]
        degs = notes if isinstance(notes, list) else ast.literal_eval(str(notes))
        recs.append((row["Cell Name"], tuple(s.strip() for s in degs),
                     str(row["Movement"])))
    return tuple(recs)


def _reading_mode(chord, translated):
    """Mode the fingering bridge reads a cell's degrees with.

    The "Translate Dominant to Minor/Major-I" checkboxes rewrite resolution /
    Myxolidian degrees to the I-chord representation; those must be read with
    the tonic modes, else the derived root (and the chord label) are wrong.
    """
    if not translated:
        return chord
    return {"MajorResolutions": "MajorTonic", "MinorResolutions": "MinorTonic",
            "Myxolidian": "MajorTonic"}.get(chord, chord)


@st.cache_data(show_spinner=False)
def score_connections(key, read1, read2, end_records, start_records,
                      position="Free (best on the neck)", anchor="key",
                      myxo_to_dorian=False, single_chord=False, shape_sig=None):
    """Score each ending->starting pair as ONE merged line.

    The pivot note is SHARED — the last note of the first cell IS the first
    note of the second (len1 + len2 - 1 notes total) — and the whole line goes
    through a single DP, so the cost is the cost of the entire connection.
    Cell 2's root is derived from the pivot pitch, so the join is seamless.

    ``read1``/``read2``: the modes each side's degrees are READ with.

    ``single_chord``: both cells are played over ONE chord (e.g. Dorian ->
    Dorian), so today's key is that chord's root; otherwise the key is the I
    of a ii-V-I (see ``cell_bridge.root_offset``).

    ``position``: "Free" searches the whole neck for the single cheapest
    fingering; a named position LISTS every fingering inside that shape
    (``row["fingerings"]``, cheapest first — ``row["result"]`` is the best),
    anchored on ``anchor``: "key" (today's key — the I of a ii-V-I, or the
    chord itself when ``single_chord``), "chord1" or "chord2" (that chord's
    root). The anchor root also drives the CAGED root strings (a hard filter
    here) and the "Position" label.

    ``myxo_to_dorian``: chord2's Myxolidian cells were re-spelled ii-relative,
    so they are READ as Dorian degrees (the derived root is the ii root) while
    the sounding chord — label and position anchor — is the dominant a 4th
    above that root.
    """
    def chord2_root(root2_pc):
        return (root2_pc + 5) % 12 if myxo_to_dorian else root2_pc

    def sym2_for(root2_pc):
        if myxo_to_dorian:
            return chord_symbol_for_root_pc(chord2_root(root2_pc), "Myxolidian")
        return chord_symbol_for_root_pc(root2_pc, read2)

    sym1 = chord_symbol_for_mode(key, read1, single_chord)
    root1 = (root_pc(key) + root_offset(read1, single_chord)) % 12
    constrained = position in POSITIONS
    _pos_cache = {}

    def pos_boxes(anchor_pc):
        if anchor_pc not in _pos_cache:
            # The box is a near-hard FILTER: a hand "more or less" in the
            # region may poke POSITION_SLACK fret(s) outside (charged), no more.
            _pos_cache[anchor_pc] = [
                (cfg.with_overrides(window_overflow_frets=POSITION_SLACK), root_midi)
                for cfg, root_midi in position_boxes(position, anchor_pc)]
        return _pos_cache[anchor_pc]

    rows = []
    for n1, d1, mv1 in end_records:
        for n2, d2, mv2 in start_records:
            cell1 = {"name": n1, "root": root1,
                     "degrees": list(d1), "mode": read1, "movement": mv1}
            cell2 = {"name": n2, "root": 0,  # derived from the pivot
                     "degrees": list(d2), "mode": read2, "movement": mv2}
            # Cell notes are eighths: a 5-note cell spans 2 beats, so the
            # pivot lands on beat 3 (a rest-stroke downbeat).
            result, pivot_index = None, len(d1) - 1
            try:
                # Register-independent dry build: chord 2's root pitch class.
                _, _, root2_pc = build_connection_line(cell1, cell2)
            except (ValueError, KeyError) as e:
                rows.append({"end": n1, "start": n2, "cost": None,
                             "pivot": f"error: {e}", "position": "-",
                             "anchor": "-", "result": None,
                             "n_up": None, "n_flags": None})
                continue
            sym2 = sym2_for(root2_pc)
            if anchor == "chord2":
                anchor_pc, anchor_sym = chord2_root(root2_pc), sym2
            elif anchor == "chord1":
                anchor_pc, anchor_sym = root1, sym1
            else:
                anchor_pc, anchor_sym = root_pc(key), f"{key} (today's key)"
            fingerings = []
            if constrained:
                # EVERY fingering in the position: both octaves of the shape on
                # the neck x every register the line fits x every string/fret
                # layout (root on the shape's root strings), cheapest first.
                seen = set()
                for box_cfg, box_root_midi in pos_boxes(anchor_pc):
                    seen_lines = set()
                    for off in (-24, -12, 0, 12, 24):
                        try:
                            line, pivot_index, _ = build_connection_line(
                                cell1, cell2, base_midi=box_root_midi + off)
                            pitches = tuple(nt["pitch"] for nt in line)
                            if pitches in seen_lines:
                                continue
                            seen_lines.add(pitches)
                            ctx = cell_context({
                                "key": key,
                                "chords": [{"start_beat": 0, "symbol": sym1},
                                           {"start_beat": cell_beat(pivot_index),
                                            "symbol": sym2}]})
                            cands = enumerate_fingerings(timed_cell_line(line), ctx,
                                                         box_cfg)
                        except (ValueError, KeyError):
                            continue
                        for cand in cands:
                            sig = _layout_sig(cand)
                            if sig not in seen:
                                seen.add(sig)
                                fingerings.append(cand)
                fingerings.sort(key=lambda r: r.best.total_cost)
                if not fingerings:
                    rows.append({"end": n1, "start": n2, "cost": None,
                                 "pivot": "does not fit this position",
                                 "position": "-", "anchor": anchor_sym,
                                 "result": None, "fingerings": [],
                                 "n_up": None, "n_flags": None})
                    continue
                result = fingerings[0]
            else:
                try:
                    line, pivot_index, _ = build_connection_line(cell1, cell2)
                    ctx = cell_context({
                        "key": key,
                        "chords": [{"start_beat": 0, "symbol": sym1},
                                   {"start_beat": cell_beat(pivot_index),
                                    "symbol": sym2}]})
                    result = optimize_fingering(timed_cell_line(line), ctx,
                                                FingeringConfig())
                    fingerings = [result]
                except (ValueError, KeyError) as e:
                    rows.append({"end": n1, "start": n2, "cost": None,
                                 "pivot": f"error: {e}", "position": "-",
                                 "anchor": anchor_sym, "result": None,
                                 "fingerings": [], "n_up": None, "n_flags": None})
                    continue
            pv = result.notes[pivot_index]
            rows.append({
                "end": n1, "start": n2,
                "cost": result.best.total_cost,
                "pivot": f"{pv.name} ({d1[-1]}={d2[0]})",
                "position": _primary_label(result.best.placed, anchor_pc, position),
                "anchor": anchor_sym, "anchor_pc": anchor_pc,
                "n_up": sum(1 for p in result.best.placed if p.stroke == "U"),
                "n_flags": len(result.best.flags),
                "result": result,
                "fingerings": fingerings,
            })
    # Rank by cost, ascending (easiest first); failures sink to the bottom.
    rows.sort(key=lambda r: (r["cost"] is None,
                             r["cost"] if r["cost"] is not None else 0.0))
    return rows


st.subheader("", divider="red")
st.write("## Fingering for each connection (easiest first — "
         "click a row to see its tab)")

# Same chord on both sides (Dorian -> Dorian): today's key IS its root.
# Otherwise today's key is read as the I of a ii-V-I.
_single_chord = is_single_chord([st.session_state.chord1, st.session_state.chord2])
_sym1 = chord_symbol_for_mode(
    st.session_state.key,
    _reading_mode(st.session_state.chord1, st.session_state.dom_to_minor1),
    _single_chord)
if _single_chord:
    st.info(f"**One chord: {_sym1}.** {st.session_state.chord1} → "
            f"{st.session_state.chord2} stays on a single chord, so today's key "
            f"({st.session_state.key}) is its root — and the position sits on it.")
    st.session_state.pos_anchor = "key"
else:
    st.info(f"**Today's key {st.session_state.key} is read as the I of a ii-V-I**: "
            f"{st.session_state.chord1} starts on **{_sym1}**; the 2nd chord follows "
            "from the pivot (shown on each tab).")
    # By default the whole connection is played in ONE box on today's key (the
    # I); chord 1 / chord 2 re-anchor it on that chord's root instead.
    _ANCHORS = {"key": f"Today's key — {st.session_state.key}",
                "chord1": f"1st chord — {_sym1}",
                "chord2": f"2nd chord — {st.session_state.chord2}"}
    st.session_state.pos_anchor = st.session_state.get("pos_anchor", "key")
    st.radio(
        "Anchor the position on",
        list(_ANCHORS),
        format_func=_ANCHORS.get,
        key="pos_anchor",
        horizontal=True,
        help="The selected position's fret box, CAGED root strings and the "
             "'Position' label are built on this root (e.g. key Eb, Fm7 → Bb7: "
             "today's key = Eb, 1st = F, 2nd = Bb).",
    )

conn_rows = []
if combinations:
    with st.spinner("Scoring all pairwise connections..."):
        conn_rows = score_connections(
            st.session_state.key,
            _reading_mode(st.session_state.chord1, st.session_state.dom_to_minor1),
            ("Dorian" if _myxo_to_dorian else
             _reading_mode(st.session_state.chord2, st.session_state.dom_to_minor2)),
            _cell_records(ending_cells_filtered),
            _cell_records(starting_cells_filtered),
            position=st.session_state.fingering_position,
            anchor=st.session_state.pos_anchor,
            myxo_to_dorian=_myxo_to_dorian,
            single_chord=_single_chord,
            # Cache key only: a changed shape definition must not serve old rows.
            shape_sig=position_signature(st.session_state.fingering_position),
        )

if conn_rows:
    _anchors = sorted({r["anchor"] for r in conn_rows if r.get("anchor") not in (None, "-")})
    if st.session_state.fingering_position in POSITIONS:
        st.caption(f"Enforced position: **{st.session_state.fingering_position}**, "
                   f"anchored on **{', '.join(_anchors) or '?'}**.")
    else:
        st.caption("Free: no position enforced (cheapest fingering anywhere); "
                   f"'Position' labels are relative to **{', '.join(_anchors) or '?'}**. "
                   "Tick 'Enforce the position' in the sidebar to enforce today's position.")

# A selected position acts as a FILTER: combinations that don't fit the box
# are dropped from the table and from the exercise.
if conn_rows and st.session_state.fingering_position in POSITIONS:
    _total = len(conn_rows)
    conn_rows = [r for r in conn_rows if r["result"] is not None]
    if len(conn_rows) < _total:
        st.caption(f"{len(conn_rows)} of {_total} combinations fit "
                   f"**{st.session_state.fingering_position}** — the rest are filtered out.")

# The sidebar's max cost applies to the connection table too: a connection
# is listed only if its cheapest fingering is under the max, and "Fingerings"
# counts the ones under it.
if conn_rows:
    _n_all = len(conn_rows)
    conn_rows = [r for r in conn_rows
                 if r["cost"] is not None and r["cost"] <= st.session_state.max_fing_cost]
    if len(conn_rows) < _n_all:
        st.caption(f"{_n_all - len(conn_rows)} of {_n_all} combinations hidden: their "
                   f"cheapest fingering costs more than the sidebar's max "
                   f"({st.session_state.max_fing_cost:g}).")

kept_rows = []
_deleted = {}
if conn_rows:
    # Curation is persisted per (chord1, chord2, pivot, position): tick Keep
    # on the combinations you want (e.g. only the easiest), save, and the same
    # selection reloads whenever you come back to this pivot + position.
    _picks = _load_picks()
    # The pivot is spelled ii-relative when the mapping is on; namespace it so
    # it never collides with a raw-spelled pivot saved before the mapping.
    _pick_key = "|".join([st.session_state.chord1, st.session_state.chord2,
                          ("ii:" if _myxo_to_dorian else "")
                          + str(st.session_state.tone),
                          st.session_state.fingering_position]
                         + {"key": [] if _single_chord else ["anchor:key"],
                            "chord1": [], "chord2": ["anchor:2nd"]}[
                             st.session_state.pos_anchor])
    _saved = _picks.get(_pick_key)
    _kept_set = ({tuple(p) for p in _saved["kept"]} if _saved else None)
    if _saved:
        st.caption(f"Loaded saved selection for this pivot+position "
                   f"({len(_saved['kept'])} kept, saved {_saved.get('saved', '?')}).")
    # Deleted fingerings per connection (layout signatures), seeded from the
    # save. Storing the DELETED ones means a fingering the engine finds later
    # shows up by default instead of being silently hidden.
    _deleted = st.session_state.setdefault("conn_fing_deleted", {}).setdefault(
        _pick_key, {pr: set(sigs) for pr, sigs in
                    ((_saved or {}).get("deleted_fingerings", {})).items()})

    # Kept set lives in session state (seeded from the save, else everything);
    # the table is a plain dataframe so a CLICK on a row selects the
    # connection shown below.
    _kept_store = st.session_state.setdefault("conn_kept", {})
    if _pick_key not in _kept_store:
        _kept_store[_pick_key] = ({_pair_key(r) for r in conn_rows
                                   if (r["end"], r["start"]) in _kept_set}
                                  if _kept_set is not None
                                  else {_pair_key(r) for r in conn_rows})
    _kept = _kept_store[_pick_key]

    _main_key = f"conn_table|{_pick_key}|{hash(tuple(_pair_key(r) for r in conn_rows))}"
    st.dataframe(
        pd.DataFrame([
            {"Keep": "✓" if _pair_key(r) in _kept else "",
             "Ending cell": r["end"], "Starting cell": r["start"],
             "Cost": r["cost"],
             "Fingerings": len(_kept_fingerings(r, _deleted)),
             "Pivot": r["pivot"], "Position": r["position"],
             "Upstrokes": r["n_up"], "Flags": r["n_flags"]}
            for r in conn_rows
        ]),
        use_container_width=True,
        hide_index=True,
        column_config={"Cost": st.column_config.NumberColumn(
            help="Cost of the cheapest fingering of this connection"),
                       "Fingerings": st.column_config.NumberColumn(
            help="How many distinct fingerings fit the position — "
                 "click the row to browse them below")},
        selection_mode="single-row", on_select="rerun", key=_main_key,
    )
    try:
        _msel = st.session_state[_main_key].selection["rows"]
    except (KeyError, AttributeError):
        _msel = []
    _row = conn_rows[_msel[0]] if _msel and _msel[0] < len(conn_rows) else conn_rows[0]
    kept_rows = [r for r in conn_rows if _pair_key(r) in _kept]

    ck1, ck2, ck3, csav, cdel = st.columns((0.22, 0.14, 0.14, 0.25, 0.25))
    _in_kept = _pair_key(_row) in _kept
    if ck1.button(("Unkeep" if _in_kept else "Keep") + " selected connection"):
        (_kept.discard if _in_kept else _kept.add)(_pair_key(_row))
        st.rerun()
    if ck2.button("Keep all"):
        _kept.update(_pair_key(r) for r in conn_rows)
        st.rerun()
    if ck3.button("Keep none"):
        _kept.clear()
        st.rerun()
    if csav.button("💾 Save kept combinations", type="primary"):
        _kept_pairs = {_pair_key(r) for r in kept_rows}
        _picks[_pick_key] = {
            "kept": [[r["end"], r["start"]] for r in kept_rows],
            "deleted_fingerings": {p: sorted(sigs) for p, sigs in _deleted.items()
                                   if p in _kept_pairs and sigs},
            "saved": _dt.date.today().isoformat(),
        }
        _save_picks(_picks)
        st.success(f"Saved {len(kept_rows)} combinations (and their deleted "
                   f"fingerings) for this pivot+position.")
    if _saved and cdel.button("Delete saved selection"):
        _picks.pop(_pick_key, None)
        _save_picks(_picks)
        st.session_state.conn_fing_deleted.pop(_pick_key, None)
        _kept_store.pop(_pick_key, None)
        st.rerun()

    st.write(f"**{_row['end']}  →  {_row['start']}**   ·   "
             + ("kept" if _in_kept else "not kept") + "   ·   click another row to switch")
    _pair = _pair_key(_row)
    _gone = _deleted.setdefault(_pair, set())
    _cands = _candidate_fingerings(_row)
    _kept_f = [f for f in _cands if _layout_sig(f) not in _gone]
    _show_deleted = _sticky_checkbox("Show deleted fingerings",
                                     f"show_deleted|{_pick_key}")
    _fings = _cands if _show_deleted else _kept_f
    if not (_row.get("fingerings") or []):
        st.warning(f"No playable fingering: {_row['pivot']}")
    elif not _cands:
        st.info(f"All fingerings of this connection cost more than the sidebar's "
                f"max ({st.session_state.max_fing_cost:g}) — raise it to see them.")
    elif not _fings:
        st.info(f"All {len(_cands)} fingerings of this connection are deleted — "
                "tick 'Show deleted fingerings' to restore some.")
    else:
        # Key carries the list's content: a stale row click can never map
        # onto a different list of fingerings.
        _tbl_key = f"fing_list|{_pick_key}|{_pair}|{hash(tuple(map(_layout_sig, _fings)))}"
        st.write(f"**{len(_kept_f)} of {len(_cands)} fingerings of this connection kept "
                 f"for practice in {st.session_state.fingering_position}** (cheapest "
                 "first). Click a row to preview its tab, then delete it from — or "
                 "restore it to — the practice set; 'Save kept combinations' persists it.")
        st.dataframe(
            pd.DataFrame([{
                "Practice": "" if _layout_sig(f) in _gone else "✓",
                "#": i + 1,
                "Cost": f.best.total_cost,
                "Frets": "{}–{}".format(min(p.fret for p in f.best.placed),
                                        max(p.fret for p in f.best.placed)),
                "Upstrokes": sum(1 for p in f.best.placed if p.stroke == "U"),
                "Flags": len(f.best.flags),
                "Position(s)": ", ".join(classify_positions(f.best.placed, _anchor_pc_of(_row)))
                               or "none",
                "Layout (string/fret)": _layout_sig(f),
            } for i, f in enumerate(_fings)]),
            use_container_width=True, hide_index=True,
            selection_mode="single-row", on_select="rerun", key=_tbl_key,
        )
        try:
            _fsel = st.session_state[_tbl_key].selection["rows"]
        except (KeyError, AttributeError):
            _fsel = []
        _idx = _fsel[0] if _fsel and _fsel[0] < len(_fings) else 0
        _shown = _fings[_idx]
        _sig = _layout_sig(_shown)
        d1, d2, d3 = st.columns((0.3, 0.3, 0.4))
        if _sig in _gone:
            if d1.button(f"Restore #{_idx + 1} to practice"):
                _gone.discard(_sig)
                st.rerun()
        else:
            if d1.button(f"Delete #{_idx + 1} from practice"):
                _gone.add(_sig)
                st.rerun()
            if len(_kept_f) > 1 and d2.button(f"Keep only #{_idx + 1}"):
                _gone.update(_layout_sig(f) for f in _cands if _layout_sig(f) != _sig)
                st.rerun()
        if _gone and d3.button("Restore all fingerings of this connection"):
            _gone.clear()
            st.rerun()
        components.html(
            render_html(_shown, tempo=int(st.session_state.tempo)),
            height=360, scrolling=True)
        with st.expander("Full report (per-note table, flags, cost)"):
            st.code(format_report(_shown), language="text")

st.session_state.show_tab_in_exercise = st.checkbox(
    "Show fingering tab during the exercise", value=True)

# The exercise walks the KEPT connections — one (cheapest kept) fingering each,
# or every kept fingering with the checkbox — easiest first, hardest last.
# Deleted fingerings are never practised.
_display = {tuple(n): c for n, c in zip(names, combinations)}
_all_mode = _sticky_checkbox(
    "Practice all kept fingerings of each connection", "exercise_all_fingerings",
    help="Unticked: one fingering per kept connection (its cheapest kept one). "
         "Ticked: every kept fingering of each kept connection. Deleted "
         "fingerings are never practised.")
exercise_rows = []
for _r in kept_rows:
    _kf = _kept_fingerings(_r, _deleted)
    if not _all_mode:
        _kf = _kf[:1]
    exercise_rows += [(_r, _f, k + 1, len(_kf)) for k, _f in enumerate(_kf)]
exercise_rows.sort(key=lambda t: t[1].best.total_cost)

# Total duration for practicing all combinations
total_time_minutes = st.sidebar.number_input(
    "Total practice time (min) : ", min_value=1, max_value=120, value=10
)

# Calculate time per combination
if exercise_rows:
    time_per_combination = int((total_time_minutes * 60) / len(exercise_rows))
    st.sidebar.write(
        f"Time per combination : :blue[{time_per_combination}] seconds"
    )
    st.write(
        f"{len(exercise_rows)} fingerings across {len({_pair_key(t[0]) for t in exercise_rows})} "
        f"combinations, easiest → hardest; each displayed for "
        f":green[{time_per_combination}] seconds."
    )
else:
    time_per_combination = 0
    st.write("No playable combinations available for the selected pivot/position.")

# Initialize or update the current combination index
if "current_combination_index" not in st.session_state:
    st.session_state.current_combination_index = 0


# Function to advance to the next combination
def next_combination():
    if "current_combination_index" in st.session_state:
        st.session_state.current_combination_index = (
            st.session_state.current_combination_index + 1
        )


# Display the current combination
if st.button("Start exercise 1", type="primary"):
    st.session_state.current_combination_index = 0
    for i, (_row_ex, _f_ex, _k, _m) in enumerate(exercise_rows):
        # Inject JavaScript for auto-scrolling
        js = """
        <script>
        window.scrollTo(0, document.body.scrollHeight);
        </script>
        """
        st.markdown(js, unsafe_allow_html=True)
        c1, c2, c3 = st.columns((0.45, 0.45, 0.1))
        disp = _display.get((_row_ex["end"], _row_ex["start"]),
                            (_row_ex["end"], _row_ex["start"]))
        c1.markdown(f"##### {disp[0]}")
        c2.markdown(f"##### {disp[1]}")
        c1.caption(f"difficulty {i+1}/{len(exercise_rows)} · fingering {_k}/{_m} "
                   f"of this connection · cost {_f_ex.best.total_cost:.2f}")
        if st.session_state.get("show_tab_in_exercise"):
            components.html(
                render_html(_f_ex, tempo=int(st.session_state.tempo)),
                height=340, scrolling=True)
        ph = c3.empty()
        N = int(time_per_combination)
        for secs in range(N, -1, -1):
            mm, ss = secs // 60, secs % 60
            ph.metric(
                f"{i+1}/{len(exercise_rows)}",
                f"{mm:02d}:{ss:02d}",
                label_visibility="collapsed",
            )
            time.sleep(1)
        next_combination()
    st.success("Completed all combinations — easiest to hardest.")
