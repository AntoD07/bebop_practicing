import streamlit as st
import streamlit.components.v1 as components
import ast
import pandas as pd
import datetime
import time

from scripts.utils import (
    sidebar_practice_key,
    sidebar_metronome,
    join_notes,
    save_practice_session,
    load_practice_lines,
)
from scripts.melodic_lines.melodic_lines import (
    sample_line_from_path_with_connecting_note,
    line_structure_mapping,
    MYXO_TO_DORIAN_LINE_TYPE,
    combo_chord_tone_connecting_notes,
    combo_mapping_info,
    combo_chord_tones_info,
    CHORD_TONES,
    harmony_caption,
)
from scripts.modes.mode_transposition import translate_dom_to_dorian
from scripts.paths import MELODIC_LINES_LOG, TABS_DIR, sampling_file
from scripts.database import fetch_data_base
import os
import time as _time

from scripts.fingering.config import FingeringConfig
from scripts.fingering.optimizer import optimize_fingering, enumerate_fingerings
from scripts.fingering.render import render_html, render_svg, format_report
from scripts.fingering.cell_bridge import (
    build_chain_line,
    cell_beat,
    cell_context,
    cell_movement,
    chord_symbol_for_mode,
    chord_symbol_for_root_pc,
    DEFAULT_MODE_ROOT_OFFSET,
    is_single_chord,
    root_offset,
    root_pc,
    timed_cell_line,
)
from scripts.fingering.positions import (
    POSITIONS, classify_position, classify_positions, position_boxes,
    position_signature, POSITION_SLACK,
)


st.set_page_config(layout="wide")
# Example of setting up the practice routine
st.title("Practicing Melodic Lines")

st.session_state.key, st.session_state.position = sidebar_practice_key()
sidebar_metronome()

# Use key and position in your Streamlit application
c1, c2 = st.columns((0.5, 0.5))
st.session_state.pos_view_dom = st.sidebar.checkbox(
    "Anchor positions on the V (Myxolidian) root",
    value=st.session_state.get("pos_view_dom", False),
    help="Label/anchor the named CAGED positions relative to the DOMINANT of "
         "today's key instead of the tonic (e.g. key D -> shapes rooted on A). "
         "Convenient when the line lives on the V chord.",
)
_pos_key = ((root_pc(st.session_state.key) + 7) % 12
            if st.session_state.pos_view_dom else st.session_state.key)
_FREE = "Free (best on the neck)"
st.session_state.enforce_position = st.session_state.get("enforce_position", True)
st.sidebar.checkbox(
    "Enforce the position",
    key="enforce_position",
    help="On: every fingering of the line is confined to today's position "
         "(selected above), anchored on today's key (or its V with the checkbox "
         "above), and ALL of them are listed. Off: Free — the single cheapest "
         "fingering anywhere on the neck.",
)
st.session_state.fingering_position = (
    POSITIONS[st.session_state.position - 1]
    if st.session_state.enforce_position else _FREE
)
st.session_state.max_fing_cost = st.session_state.get("max_fing_cost", 15.0)
st.sidebar.slider(
    "Max fingering cost to display", 0.0, 40.0, step=0.5, key="max_fing_cost",
    help="Fingerings costing more than this are hidden; sampled lines whose "
         "cheapest fingering is above it are dropped from the batch ranking.",
)
_SHAPES = tuple(position_signature(p) for p in POSITIONS)
st.session_state.include_bonus = st.session_state.get("include_bonus", False)
st.sidebar.checkbox("Whether to include bonus cells", key="include_bonus")

st.session_state.sus_to_loc_dorian = c2.checkbox(
    "Whether to change to translate the intervals for other modes", value=False
)


st.session_state.dom_to_minor = c2.checkbox(
    "Whether to translate Dominant and Locrian cells to Minor/Major-I", value=False
)


def _bridge_modes(modes):
    """Mode names for the fingering bridge. Resolution cells are DOMINANT-based
    (degrees spelled from the resolving V7); but when the translate checkbox has
    rewritten their degrees to the Minor/Major-I representation, they must be
    read with the tonic modes instead. In the Dorian x Myxolidian combo the
    Myxolidian degrees are ALWAYS re-spelled ii-relative, so they read as
    Dorian."""
    out = list(modes)
    if st.session_state.line_type == MYXO_TO_DORIAN_LINE_TYPE:
        out = ["Dorian" if m == "Myxolidian" else m for m in out]
    if st.session_state.dom_to_minor:
        out = [{"MajorResolutions": "MajorTonic",
                "MinorResolutions": "MinorTonic"}.get(m, m) for m in out]
    return out
st.session_state.length = st.sidebar.number_input(
    "Select the line length (depends on the line type) ",
    min_value=2,
    max_value=8,
    value=4,
)
with c1:
    st.session_state.line_type = st.selectbox(
        "Type of line to practice",
        options=[
            "Maj7",
            # "7sus4 Infinity Loop",
            "Minor",
            "Dorian",
            "Myxolidian",
            "Locrian",
            "Short Maj 2-5-1",
            "Long Maj 2-5-1",
            "Short Minor 2-5-1",
            "Long Minor 2-5-1",
            "Long Minor with double resolution",
            "Double resolution",
            "Minor and Dominant 2-cells alternated",
            "Minor x Dominant",
            "Major x Dominant",
            MYXO_TO_DORIAN_LINE_TYPE,
        ],
        index=6,  # Default to "Long Maj 2-5-1"
    )

    if st.session_state.line_type == MYXO_TO_DORIAN_LINE_TYPE:
        cc1, cc2 = st.columns(2)
        st.session_state.n_dorian = cc1.number_input(
            "Dorian cells", min_value=1, max_value=6, value=2)
        st.session_state.n_myxo = cc2.number_input(
            "Myxolidian cells", min_value=1, max_value=6, value=2)
    else:
        st.session_state.n_dorian = 1
        st.session_state.n_myxo = 1

    sample_path = line_structure_mapping(
        st.session_state.line_type, st.session_state.length,
        n_dorian=st.session_state.n_dorian, n_myxo=st.session_state.n_myxo,
    )
    if st.session_state.line_type not in [
        "Long Minor 2-5-1 with Minor ending",
        "Long Maj 2-5-1 with Maj7 ending",
        "Minor and Dominant 2-cells alternated",
    ]:
        # tmp_df, _, _ = create_cell_frames(
        #     sample_path[-1],
        #     False,
        #     st.session_state.sus_to_loc_dorian,
        #     st.session_state.include_bonus,
        #     field="Start Note",
        #     loc_to_dominant=st.session_state.loc_to_dom,
        #     dom_to_minor=st.session_state.dom_to_minor,
        # )
        # tmp_df = change_note_representation(
        #     tmp_df,
        #     sample_path[-1],
        #     st.session_state.sus_to_loc_dorian,
        #     st.session_state.loc_to_dom,
        #     st.session_state.dom_to_minor,
        # )
        st.session_state.starting_note = st.selectbox(
            "Select the first note (optional) ",
            options=[
                "None",
                "1",
                "9",
                "3",
                "4",
                "11",
                "#11",
                "5",
                "6",
                "7",
                "b7",
                "b6",
                "b9",
                "#9",
                "#7",
            ],
            # st.session_state.get("starting_note", None),
        )
        st.session_state.ending_note = st.selectbox(
            "Select the end note (optional) ",
            options=[
                "None",
                "1",
                "9",
                "3",
                "4",
                "11",
                "#11",
                "5",
                "6",
                "7",
                "b7",
                "b6",
                "b9",
                "#9",
                "#7",
            ],
            # st.session_state.get("ending_note", None),
        )

    st.session_state.movement = st.sidebar.selectbox(
        "Select the line movement (optional) ",
        [None, "A and N", "D and N", "A", "D"],
        index=[None, "A and N", "D and N", "A", "D"].index(
            st.session_state.get("movement", None)
        ),
    )
    used_notes = [
        "1",
        "9",
        "3",
        "4",
        "11",
        "#11",
        "5",
        "6",
        "7",
        "b7",
        "b6",
        "b9",
        "#9",
        "#7",
        None,
    ]
    st.write("Melodic Lines sampled according to the following cells : ", sample_path)
    st.caption(harmony_caption(st.session_state.key, sample_path))
    connecting_notes = st.multiselect(
        "Select connecting notes",
        options=used_notes,
        default=(
            ["1", "3", "5", "7"]
            if st.session_state.line_type
            not in ["Long Minor 2-5-1", "Short Minor 2-5-1", "Double resolution"]
            else used_notes
        ),
    )
    connecting_notes = [list(connecting_notes) for _ in range(len(sample_path))]
_is_combo = st.session_state.line_type == MYXO_TO_DORIAN_LINE_TYPE
chord_tones = st.checkbox("Connecting note are chord tones", value=_is_combo)
if chord_tones and ("2-5-1" in st.session_state.line_type):
    connecting_notes = [
        ["9", "6", "b6", "b9", "#9", "11", "#11", "5"],
        ["9", "6", "b6", "b9", "#9", "11", "#11", "5"],
        ["1", "3", "5", "7"],
        ["1", "3", "5", "7"],
    ]
if _is_combo:
    st.info(combo_mapping_info())
    if chord_tones:
        connecting_notes = combo_chord_tone_connecting_notes(sample_path)
        st.info(combo_chord_tones_info())
# The line's FIRST note (connecting_notes[0]) is only constrained when chord
# tones are requested: 1-3-5-7 of the first cell's chord, unless an explicit
# "Select the first note" overrides it.
connecting_notes[0] = list(CHORD_TONES) if chord_tones else []
if chord_tones and st.session_state.get("starting_note") in (None, "None"):
    st.caption("First note: a chord tone (1 / 3 / 5 / 7) of the first cell's chord.")


def _pivots_respected(note_reps, cn_lists) -> bool:
    """Check every boundary pivot against the entering cell's allowed set.

    The legacy sampler's own connecting-note filter is gated behind a condition
    that rarely fires, so we enforce the constraint explicitly here: the note a
    cell STARTS on (== previous cell's end, the pivot) must be in that cell's
    connecting-notes list. Empty/None sets mean 'no constraint'.
    """
    if not cn_lists:
        return True
    starts = [
        [s.strip() for s in ast.literal_eval(str(r))][0] for r in note_reps
    ]
    for k in range(1, len(starts)):
        allowed = cn_lists[k] if k < len(cn_lists) else None
        if not allowed:
            continue
        allowed_set = {str(a) for a in allowed if a is not None}
        if allowed_set and starts[k] not in allowed_set:
            return False
    return True


def sample_line_checked(max_tries=60, **kwargs):
    """Sample a line and reject any whose pivots violate connecting_notes."""
    cn = kwargs.get("connecting_notes")
    for _ in range(max_tries):
        out = sample_line_from_path_with_connecting_note(**kwargs)
        if out is None:
            return None
        if _pivots_respected(out[1], cn):
            return out
    return None


if st.button("Generate melodic line", type="primary"):
    _gen = sample_line_checked(
        line_type=st.session_state.line_type,
        include_bonus=st.session_state.include_bonus,
        mode_filter=False,
        loc_to_dom=False,
        dom_to_minor=st.session_state.dom_to_minor,
        sus_to_loc_dorian=st.session_state.sus_to_loc_dorian,
        length=st.session_state.length,
        movement=st.session_state.movement,
        starting_note=st.session_state.starting_note,
        ending_note=st.session_state.ending_note,
        connecting_notes=connecting_notes,
        n_dorian=st.session_state.n_dorian,
        n_myxo=st.session_state.n_myxo,
    )
    if _gen is None:
        st.error("No line satisfying the connecting-note constraints was found "
                 "— try relaxing them.")
        st.stop()
    (
        st.session_state.melodic_line,
        st.session_state.note_representations,
        sample_path,
    ) = _gen
    c1, c2, c3 = st.columns((0.2, 0.5, 0.3))
    for mode, name, notes in zip(
        sample_path,
        st.session_state.melodic_line,
        st.session_state.note_representations,
    ):
        c1.write(f"##### :blue[{mode}]")
        c2.write(f"##### {name}")
        c3.write(join_notes(notes))
    st.session_state.fing_mode_list = _bridge_modes(sample_path)
    # Original (sampling CSV) mode names — the Movement lookup for translated
    # cells must read the CSV the cell actually came from.
    st.session_state.fing_movement_modes = list(sample_path)
    st.session_state.tmp = True


# --------------------------------------------------------------------------- #
# Fingering for the sampled line: rank Free + the five positions by cost and
# display the tab (same engine as the Connections/Quiz pages; whole line = ONE
# DP, pivots shared between cells).
# --------------------------------------------------------------------------- #
def _layout_sig(result) -> str:
    return " ".join(f"{p.string}/{p.fret}" for p in result.best.placed)


@st.cache_data(show_spinner=False)
def line_fingerings(key, cell_names, note_reps, mode_list, position, pos_key=None,
                    movement_modes=None, shape_sig=None):
    """Every fingering of a pivot-chained line inside ``position`` (cheapest
    first), or the single cheapest fingering anywhere when ``position`` is Free.

    Same logic as the Cell Connexions page: the position is a HARD box
    anchored on ``pos_key`` (today's key, or its V); both octaves of the box
    and every register of the line are enumerated, layouts deduped, and only
    fingerings labelled with the position are kept.

    ``shape_sig`` is cache-key only (the shapes live in another module, which
    st.cache_data does not watch). ``movement_modes`` are the ORIGINAL
    sampling-CSV mode names when ``mode_list`` carries translated reading
    modes (cell names collide across CSVs with different Movement).
    """
    pk = pos_key if pos_key is not None else key
    mv_modes = list(movement_modes) if movement_modes else list(mode_list)
    single = is_single_chord(mv_modes)
    cells = []
    kpc = root_pc(key)
    for i, (name, notes, mode) in enumerate(zip(cell_names, note_reps, mode_list)):
        degs = [s.strip() for s in ast.literal_eval(str(notes))]
        cells.append({
            "name": name,
            # First cell root from today's key (see cell_bridge.root_offset);
            # later cells' roots are derived from the pivots inside the chain.
            "root": (kpc + root_offset(mode, single)) % 12,
            "degrees": degs,
            "mode": mode,
            "movement": cell_movement(mv_modes[i], name),
        })

    def _ctx(roots, pivots):
        # Cell notes are eighths; each chord starts on its cell's pivot.
        chords = []
        for k in range(len(mode_list)):
            if mv_modes[k] == "Myxolidian" and mode_list[k] == "Dorian":
                # Translated Myxolidian cell: the derived root is the ii root;
                # the sounding chord is the dominant a 4th above it.
                sym = chord_symbol_for_root_pc((roots[k] + 5) % 12, "Myxolidian")
            elif k == 0:
                sym = chord_symbol_for_mode(key, mode_list[0], single)
            else:
                sym = chord_symbol_for_root_pc(roots[k], mode_list[k])
            start = 0 if k == 0 else cell_beat(pivots[k - 1])
            chords.append({"start_beat": start, "symbol": sym})
        return cell_context({"key": key, "chords": chords})

    if position not in POSITIONS:
        # Free: the cheapest fingering anywhere; try octave-shifted registers
        # (a chain can run off the neck in the default one).
        best = None
        for off in (0, 12, -12, 24):
            try:
                line, pivots, roots = build_chain_line(cells, base_midi=60 + off)
                cand = optimize_fingering(timed_cell_line(line), _ctx(roots, pivots),
                                          FingeringConfig())
            except (ValueError, KeyError):
                continue
            if best is None or cand.best.total_cost < best.best.total_cost:
                best = cand
        return [best] if best is not None else []

    out, seen = [], set()
    for box_cfg, box_root_midi in position_boxes(position, pk):
        box_cfg = box_cfg.with_overrides(window_overflow_frets=POSITION_SLACK)
        seen_lines = set()
        for off in (-24, -12, 0, 12, 24):
            try:
                line, pivots, roots = build_chain_line(cells, base_midi=box_root_midi + off)
                pitches = tuple(nt["pitch"] for nt in line)
                if pitches in seen_lines:
                    continue
                seen_lines.add(pitches)
                cands = enumerate_fingerings(timed_cell_line(line), _ctx(roots, pivots),
                                             box_cfg)
            except (ValueError, KeyError):
                continue
            for cand in cands:
                sig = _layout_sig(cand)
                if sig in seen or position not in classify_positions(cand.best.placed, pk):
                    continue
                seen.add(sig)
                out.append(cand)
    out.sort(key=lambda r: r.best.total_cost)
    return out


def _current_line_fingerings():
    """All fingerings of the current line (position + max cost applied)."""
    fings = line_fingerings(
        st.session_state.key,
        tuple(st.session_state.melodic_line),
        tuple(str(n) for n in st.session_state.note_representations),
        tuple(st.session_state.fing_mode_list),
        st.session_state.fingering_position,
        pos_key=_pos_key, shape_sig=_SHAPES,
        movement_modes=tuple(st.session_state.get(
            "fing_movement_modes", st.session_state.fing_mode_list)),
    )
    return fings, [f for f in fings if f.best.total_cost <= st.session_state.max_fing_cost]


if st.session_state.get("melodic_line") and st.session_state.get("fing_mode_list"):
    st.subheader("", divider="red")
    _pos = st.session_state.fingering_position
    st.write("## Fingering" + (f" in {_pos}" if _pos in POSITIONS else " (Free)")
             + " — cheapest first, click a row for its tab")
    with st.spinner("Fingering the line..."):
        _all_f, _fings = _current_line_fingerings()
    st.session_state.pop("current_fingering", None)
    if not _all_f:
        st.warning("This line does not fit the position." if _pos in POSITIONS
                   else "No playable fingering for this line.")
    elif not _fings:
        st.info(f"All {len(_all_f)} fingerings of this line cost more than the "
                f"sidebar's max ({st.session_state.max_fing_cost:g}) — raise it.")
    else:
        _shown = _fings[0]
        if len(_fings) > 1:
            _tbl_key = f"line_fings|{hash(tuple(map(_layout_sig, _fings)))}"
            st.dataframe(
                pd.DataFrame([{
                    "#": i + 1,
                    "Cost": f.best.total_cost,
                    "Frets": "{}–{}".format(min(p.fret for p in f.best.placed),
                                            max(p.fret for p in f.best.placed)),
                    "Upstrokes": sum(1 for p in f.best.placed if p.stroke == "U"),
                    "Flags": len(f.best.flags),
                    "Position(s)": ", ".join(classify_positions(f.best.placed, _pos_key))
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
            if _fsel and _fsel[0] < len(_fings):
                _shown = _fings[_fsel[0]]
        st.write(f"**{len(_fings)} fingering(s)** · showing cost "
                 f"{_shown.best.total_cost:.2f} · "
                 f"{classify_position(_shown.best.placed, _pos_key)}")
        st.session_state.current_fingering = _shown
        st.session_state.current_fingering_label = classify_position(_shown.best.placed, _pos_key)
        components.html(
            render_html(_shown, tempo=int(st.session_state.tempo)),
            height=380, scrolling=True)
        with st.expander("Full report (per-note table, flags, cost)"):
            st.code(format_report(_shown), language="text")


# --------------------------------------------------------------------------- #
# Batch mode: sample MANY lines under the current constraints, finger each
# (Free, best on the neck) and rank all of them by cost — best-lying first.
# --------------------------------------------------------------------------- #
st.subheader("", divider="red")
st.write("## Sample many lines & rank them by playability")
st.caption("Each line is ranked by its cheapest fingering "
           + (f"inside {st.session_state.fingering_position}" if st.session_state.fingering_position in POSITIONS else "anywhere on the neck")
           + f" under the sidebar's max cost; lines with none are dropped. "
           "Pick a line and 'Practice this line' to browse all its fingerings above.")
bc1, bc2 = st.columns((0.3, 0.7))
n_samples = bc1.number_input("Lines to sample", min_value=3, max_value=100, value=10)
if bc2.button("Sample & rank lines", type="primary"):
    batch, seen = [], set()
    prog = st.progress(0.0, text="Sampling and fingering lines...")
    attempts = 0
    # Generous attempt cap: pivot-constraint rejection can discard many samples.
    while len(batch) < n_samples and attempts < n_samples * 10:
        attempts += 1
        out = sample_line_from_path_with_connecting_note(
            line_type=st.session_state.line_type,
            include_bonus=st.session_state.include_bonus,
            mode_filter=False,
            loc_to_dom=False,
            dom_to_minor=st.session_state.dom_to_minor,
            sus_to_loc_dorian=st.session_state.sus_to_loc_dorian,
            length=st.session_state.length,
            movement=st.session_state.movement,
            starting_note=st.session_state.starting_note,
            ending_note=st.session_state.ending_note,
            connecting_notes=connecting_notes,
            n_dorian=st.session_state.n_dorian,
            n_myxo=st.session_state.n_myxo,
        )
        if out is None:
            continue
        ml, nr, mp = out
        if not _pivots_respected(nr, connecting_notes):
            continue
        sig = tuple(ml)
        if sig in seen:
            continue
        seen.add(sig)
        fings_ = line_fingerings(
            st.session_state.key, tuple(ml), tuple(str(n) for n in nr),
            tuple(_bridge_modes(mp)), st.session_state.fingering_position,
            pos_key=_pos_key, shape_sig=_SHAPES, movement_modes=tuple(mp))
        fings_ = [f for f in fings_ if f.best.total_cost <= st.session_state.max_fing_cost]
        if not fings_:
            continue
        best = fings_[0]
        batch.append({
            "cells": list(ml), "note_reps": [str(n) for n in nr],
            "modes": list(mp),
            "cost": best.best.total_cost,
            "position": st.session_state.fingering_position,
            "where": classify_position(best.best.placed, _pos_key),
            "n_fingerings": len(fings_),
            "n_up": sum(1 for p in best.best.placed if p.stroke == "U"),
            "result": best,
        })
        prog.progress(min(1.0, len(batch) / n_samples),
                      text=f"{len(batch)}/{n_samples} lines fingered")
    prog.empty()
    batch.sort(key=lambda r: r["cost"])  # best-lying line first
    st.session_state.batch_lines = batch

# For 2-cell line types the pair space is small: enumerate EVERY pivot-valid
# pair exhaustively (random sampling can miss rare ones), rank by playability.
if len(sample_path) == 2:
    if st.button("Enumerate ALL pairs & rank (exhaustive)"):
        _MV_ALLOWED = {None: None, "A and N": {"A", "N"}, "D and N": {"D", "N"},
                       "A": {"A"}, "D": {"D"}}[st.session_state.movement]
        dfs = [fetch_data_base(sampling_file(m), bonus=st.session_state.include_bonus)
               for m in sample_path]
        for df in dfs:
            df["Start Note"] = df["Start Note"].astype(str)
            df["End Note"] = df["End Note"].astype(str)
        # Reading modes for the fingering bridge; in the Dorian x Myxolidian
        # combo the Myxolidian cells are re-spelled ii-relative so the pivot
        # notes are comparable, and they then read as Dorian degrees.
        ex_modes = list(sample_path)
        if st.session_state.line_type == MYXO_TO_DORIAN_LINE_TYPE:
            dfs = [translate_dom_to_dorian(df) if m == "Myxolidian" else df
                   for m, df in zip(sample_path, dfs)]
            ex_modes = ["Dorian" if m == "Myxolidian" else m for m in sample_path]
        d1, d2 = dfs
        if _MV_ALLOWED:
            d1 = d1[d1["Movement"].astype(str).isin(_MV_ALLOWED)]
            d2 = d2[d2["Movement"].astype(str).isin(_MV_ALLOWED)]
        if st.session_state.starting_note not in (None, "None"):
            d1 = d1[d1["Start Note"] == str(st.session_state.starting_note)]
        elif connecting_notes[0]:
            d1 = d1[d1["Start Note"].astype(str).isin(connecting_notes[0])]
        if st.session_state.ending_note not in (None, "None"):
            d2 = d2[d2["End Note"] == str(st.session_state.ending_note)]
        # Row tuples (a .loc lookup returns a Series on duplicate cell names).
        recs1 = list(d1.reset_index()[["Cell Name", "End Note", "Notes"]]
                     .itertuples(index=False, name=None))
        recs2 = list(d2.reset_index()[["Cell Name", "Start Note", "Notes"]]
                     .itertuples(index=False, name=None))
        pairs = [((n1, notes1), (n2, notes2))
                 for n1, end1, notes1 in recs1
                 for n2, start2, notes2 in recs2
                 if str(end1) == str(start2)]
        batch = []
        prog = st.progress(0.0, text=f"Fingering all {len(pairs)} pairs...")
        for i, ((n1, notes1), (n2, notes2)) in enumerate(pairs):
            nr = [str(notes1), str(notes2)]
            if not _pivots_respected(nr, connecting_notes):
                continue
            # Raw representations -> plain mode names (combo: translated ->
            # Dorian reading; the Movement lookup keeps the original CSVs).
            fings_ = line_fingerings(
                st.session_state.key, (n1, n2), tuple(nr),
                tuple(ex_modes), st.session_state.fingering_position,
                pos_key=_pos_key, shape_sig=_SHAPES, movement_modes=tuple(sample_path))
            fings_ = [f for f in fings_ if f.best.total_cost <= st.session_state.max_fing_cost]
            if fings_:
                best = fings_[0]
                batch.append({
                    "cells": [n1, n2], "note_reps": nr, "modes": list(sample_path),
                    "cost": best.best.total_cost,
                    "position": st.session_state.fingering_position,
                    "where": classify_position(best.best.placed, _pos_key),
                    "n_fingerings": len(fings_),
                    "n_up": sum(1 for p in best.best.placed if p.stroke == "U"),
                    "result": best,
                })
            prog.progress((i + 1) / max(1, len(pairs)),
                          text=f"{i + 1}/{len(pairs)} pairs fingered")
        prog.empty()
        batch.sort(key=lambda r: r["cost"])
        st.session_state.batch_lines = batch
        st.caption(f"{len(batch)} playable pairs out of {len(pairs)} pivot-valid "
                   f"(exhaustive — every valid pair was tried).")

if st.session_state.get("batch_lines"):
    batch = st.session_state.batch_lines
    st.dataframe(
        pd.DataFrame([{
            "Cost": r["cost"],
            "Line": "  →  ".join(r["cells"]),
            "Fingerings": r.get("n_fingerings", 1),
            "Played at": r["where"],
            "Upstrokes": r["n_up"],
        } for r in batch]),
        use_container_width=True,
        selection_mode="single-row",
        on_select="rerun",
        key="batch_table",
    )
    _bsel = st.session_state.batch_table.selection["rows"]
    _brow = batch[_bsel[0]] if _bsel else batch[0]
    st.write(f"**{'  →  '.join(_brow['cells'])}**   ·   cost {_brow['cost']:.2f}   ·   "
             f"{_brow['where']}")
    st.session_state.current_fingering = _brow["result"]
    st.session_state.current_fingering_label = _brow["where"]
    components.html(
        render_html(_brow["result"], tempo=int(st.session_state.tempo)),
        height=380, scrolling=True)
    if st.button("Practice this line (make it the current line)"):
        st.session_state.melodic_line = _brow["cells"]
        st.session_state.note_representations = _brow["note_reps"]
        st.session_state.fing_mode_list = _bridge_modes(_brow["modes"])
        st.session_state.fing_movement_modes = list(_brow["modes"])
        st.session_state.tmp = True
        st.rerun()

st.session_state.grade = st.number_input(
    "How good was it?", min_value=1, max_value=5, value=5
)
if st.session_state.get("tmp"):
    # Prepare the session details
    st.session_state.text = st.text_input("Enter message")
    if st.button("Save line"):
        session_details = {
            "Date": datetime.date.today().strftime("%Y-%m-%d"),
            "Line type": st.session_state.line_type,
            "Line": st.session_state.melodic_line,
            "Note sequence": st.session_state.note_representations,
            "Grade": st.session_state.grade,
            "Comment": st.session_state.text,
            "Movement": st.session_state.movement,
        }
        # Persist the displayed fingering alongside the sequence: an SVG of
        # the tab plus a compact string/fret/stroke encoding in the log.
        _fing = st.session_state.get("current_fingering")
        if _fing is not None:
            os.makedirs(TABS_DIR, exist_ok=True)
            fname = f"tab_{int(_time.time())}.svg"
            fpath = os.path.join(TABS_DIR, fname)
            with open(fpath, "w") as f:
                f.write(render_svg(_fing, tempo=int(st.session_state.tempo)))
            session_details["Tab"] = " ".join(
                f"{p.string}/{p.fret}{p.stroke}" for p in _fing.best.placed)
            session_details["Tab file"] = os.path.relpath(fpath)
        save_practice_session(session_details, MELODIC_LINES_LOG)

        st.success("Line saved successfully!"
                   + (f"  (tab: {st.session_state.get('current_fingering_label','')})"
                      if _fing is not None else "  (no tab displayed — sequence only)"))


st.write("---")
st.write("## Saved melodic lines")

lines = load_practice_lines()

filtered_lines = lines.loc[lines["Line type"] == st.session_state.line_type]
filtered_lines["Start Note"] = filtered_lines["Note sequence"].str[4]
filtered_lines["Last Note"] = filtered_lines["Note sequence"].str[-5]


filtered_lines["sort_key"] = filtered_lines["Movement"].apply(
    lambda x: 0 if x == st.session_state.movement else 1
)
filtered_lines = filtered_lines.sort_values(
    by=["sort_key", "Grade"], ascending=[True, False]
).drop("sort_key", axis=1)
st.dataframe(
    filtered_lines.drop(columns=["Note sequence"]),
    use_container_width=True,
    selection_mode="single-row",
    on_select="rerun",
    key="selected_line_cb",
)

if len(st.session_state.selected_line_cb.selection["rows"]) > 0:
    (
        c1,
        c2,
    ) = st.columns((0.5, 0.5))
    line = filtered_lines.iloc[st.session_state.selected_line_cb.selection["rows"][0]]
    for name, notes in zip(
        ast.literal_eval(line["Line"]),
        ast.literal_eval(line["Note sequence"]),
    ):

        c1.write(f"##### {name}")
        c2.write(join_notes(notes))
    # Show the saved tab, if one was stored with this line.
    _tabfile = line.get("Tab file")
    if isinstance(_tabfile, str) and _tabfile and os.path.exists(_tabfile):
        components.html(open(_tabfile).read(), height=380, scrolling=True)
    elif isinstance(line.get("Tab"), str) and line.get("Tab"):
        st.code(line["Tab"], language="text")
