import streamlit as st
import streamlit.components.v1 as components
import ast
import pandas as pd
import datetime
import time

from scripts.utils import (
    get_or_update_practice_details,
    join_notes,
    save_practice_session,
    load_practice_lines,
)
from scripts.melodic_lines.melodic_lines import (
    sample_line_from_path_with_connecting_note,
    line_structure_mapping,
)
from scripts.paths import MELODIC_LINES_LOG, TABS_DIR
import os
import time as _time

from scripts.fingering.config import FingeringConfig
from scripts.fingering.optimizer import optimize_fingering, cost_of
from scripts.fingering.render import render_html, render_svg, format_report
from scripts.fingering.cell_bridge import (
    build_chain_line,
    cell_movement,
    chord_symbol_for_mode,
    chord_symbol_for_root_pc,
    DEFAULT_MODE_ROOT_OFFSET,
    root_pc,
)
from scripts.fingering.positions import (
    POSITIONS, classify_position, position_config_for_key,
)


st.set_page_config(layout="wide")
# Example of setting up the practice routine
st.title("Practicing Melodic Lines")

st.session_state.key, st.session_state.position = get_or_update_practice_details()

# Use key and position in your Streamlit application
c1, c2 = st.columns((0.5, 0.5))
st.sidebar.subheader(f"Today's Key: :blue[{st.session_state.key}]")
st.sidebar.subheader(
    f"Today's Position (for guitar): :blue[{st.session_state.position}]"
)
st.session_state.include_bonus = st.sidebar.checkbox(
    "Whether to include bonus cells", value=st.session_state.get("include_bonus", False)
)

st.session_state.sus_to_loc_dorian = c2.checkbox(
    "Whether to change to translate the intervals for other modes", value=False
)


st.session_state.dom_to_minor = c2.checkbox(
    "Whether to translate Dominant and Locrian cells to Minor/Major-I", value=False
)
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
            "Dorian",
            "Myxolidian",
            "Locrian",
            "Short Maj 2-5-1",
            "Long Maj 2-5-1",
            "Short Minor 2-5-1",
            "Long Minor 2-5-1",
            "Long Minor with double resolution",
            "Double resolution",
            "Dorian and Dominant 2-cells alternated",
            "Dorian x Dominant",
            "Major x Dominant",
        ],
        index=5,  # Default to "Long Maj 2-5-1"
    )

    sample_path = line_structure_mapping(
        st.session_state.line_type, st.session_state.length
    )
    if st.session_state.line_type not in [
        "Long Minor 2-5-1 with Dorian ending",
        "Long Maj 2-5-1 with Maj7 ending",
        "Dorian and Dominant 2-cells alternated",
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
                "11",
                "#11",
                "5",
                "6",
                "7",
                "b7",
                "b6",
                "b9",
                "#9",
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
                "11",
                "#11",
                "5",
                "6",
                "7",
                "b7",
                "b6",
                "b9",
                "#9",
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
        "11",
        "#11",
        "5",
        "6",
        "7",
        "b7",
        "b6",
        "b9",
        "#9",
        None,
    ]
    st.write("Melodic Lines sampled according to the following cells : ", sample_path)
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
chord_tones = st.checkbox("Connecting note are chord tones", value=False)
if chord_tones and ("2-5-1" in st.session_state.line_type):
    connecting_notes = [
        ["9", "6", "b6", "b9", "#9", "11", "#11", "5"],
        ["9", "6", "b6", "b9", "#9", "11", "#11", "5"],
        ["1", "3", "5", "7"],
        ["1", "3", "5", "7"],
    ]


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
    st.session_state.fing_mode_list = list(sample_path)
    st.session_state.tmp = True


# --------------------------------------------------------------------------- #
# Fingering for the sampled line: rank Free + the five positions by cost and
# display the tab (same engine as the Connections/Quiz pages; whole line = ONE
# DP, pivots shared between cells).
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False)
def rank_line_fingerings(key, cell_names, note_reps, mode_list):
    cells = []
    kpc = root_pc(key)
    for i, (name, notes, mode) in enumerate(zip(cell_names, note_reps, mode_list)):
        degs = [s.strip() for s in ast.literal_eval(str(notes))]
        cells.append({
            "name": name,
            # First cell root from the ii-V interpretation of today's key;
            # later cells' roots are derived from the pivots inside the chain.
            "root": (kpc + DEFAULT_MODE_ROOT_OFFSET.get(mode, 0)) % 12,
            "degrees": degs,
            "mode": mode,
            "movement": cell_movement(mode, name),
        })
    cell_len = len(cells[0]["degrees"])
    bpb = max(1, cell_len - 1)  # overlapping cells stride bpb beats
    base = FingeringConfig(beats_per_bar=bpb)

    def _ctx(roots):
        chords = [{"start_beat": 0,
                   "symbol": chord_symbol_for_mode(key, mode_list[0])}]
        for k in range(1, len(mode_list)):
            chords.append({"start_beat": k * bpb,
                           "symbol": chord_symbol_for_root_pc(roots[k], mode_list[k])})
        return {"key": key, "beats_per_bar": bpb, "chords": chords}

    rows = []
    # Free: the single cheapest fingering anywhere on the neck.
    try:
        line, _, roots = build_chain_line(cells)
        res = optimize_fingering(line, _ctx(roots), base)
        rows.append({"position": "Free (best on the neck)",
                     "cost": res.best.total_cost,
                     "where": classify_position(res.best.placed, key),
                     "result": res})
    except (ValueError, KeyError) as e:
        rows.append({"position": "Free (best on the neck)", "cost": None,
                     "where": f"error: {e}", "result": None})
    # Each named position: try the box in several octaves, keep the cheapest.
    for pos in POSITIONS:
        cfg, root_midi = position_config_for_key(pos, key, base)
        best = None
        for off in (-12, 0, 12, 24):
            try:
                line, _, roots = build_chain_line(cells, base_midi=root_midi + off)
                cand = optimize_fingering(line, _ctx(roots),
                                          cfg.with_overrides(beats_per_bar=bpb))
            except (ValueError, KeyError):
                continue
            if best is None or cand.best.total_cost < best.best.total_cost:
                best = cand
        if best is None:
            rows.append({"position": pos, "cost": None,
                         "where": "does not fit", "result": None})
        else:
            rows.append({"position": pos,
                         "cost": cost_of(best.best.placed, base),
                         "where": classify_position(best.best.placed, key),
                         "result": best})
    # Best position on the neck first (lowest cost); unplayable ones sink.
    rows.sort(key=lambda r: (r["cost"] is None,
                             r["cost"] if r["cost"] is not None else 0.0))
    return rows


if st.session_state.get("melodic_line") and st.session_state.get("fing_mode_list"):
    st.subheader("", divider="red")
    st.write("## Fingering (best position on the neck first — click a row for its tab)")
    with st.spinner("Ranking fingerings..."):
        fing_rows = rank_line_fingerings(
            st.session_state.key,
            tuple(st.session_state.melodic_line),
            tuple(str(n) for n in st.session_state.note_representations),
            tuple(st.session_state.fing_mode_list),
        )
    st.dataframe(
        pd.DataFrame([{"Position": r["position"],
                       "Cost": r["cost"],
                       "Played at": r["where"]} for r in fing_rows]),
        use_container_width=True,
        selection_mode="single-row",
        on_select="rerun",
        key="line_fing_table",
    )
    _sel = st.session_state.line_fing_table.selection["rows"]
    _row = fing_rows[_sel[0]] if _sel else next(
        (r for r in fing_rows if r["result"] is not None), fing_rows[0])
    st.write(f"**{_row['position']}**   ·   cost "
             + (f"{_row['cost']:.2f}" if _row["cost"] is not None else "n/a")
             + f"   ·   {_row['where']}")
    if _row["result"] is None:
        st.warning("No playable fingering here.")
    else:
        st.session_state.current_fingering = _row["result"]
        st.session_state.current_fingering_label = _row["position"]
        components.html(
            render_html(_row["result"], tempo=int(st.session_state.get("tempo", 160))),
            height=380, scrolling=True)
        with st.expander("Full report (per-note table, flags, cost)"):
            st.code(format_report(_row["result"]), language="text")


# --------------------------------------------------------------------------- #
# Batch mode: sample MANY lines under the current constraints, finger each
# (Free, best on the neck) and rank all of them by cost — best-lying first.
# --------------------------------------------------------------------------- #
def _free_fingering_for(melodic_line, note_reps, mode_list, key):
    """Build the pivot-merged chain for one sampled line and solve it (Free)."""
    kpc = root_pc(key)
    cells = []
    for i, (name, notes, mode) in enumerate(zip(melodic_line, note_reps, mode_list)):
        degs = [s.strip() for s in ast.literal_eval(str(notes))]
        cells.append({
            "name": name,
            "root": (kpc + DEFAULT_MODE_ROOT_OFFSET.get(mode, 0)) % 12,
            "degrees": degs,
            "mode": mode,
            "movement": cell_movement(mode, name),
        })
    bpb = max(1, len(cells[0]["degrees"]) - 1)
    line, _, roots = build_chain_line(cells)
    chords = [{"start_beat": 0, "symbol": chord_symbol_for_mode(key, mode_list[0])}]
    for k in range(1, len(mode_list)):
        chords.append({"start_beat": k * bpb,
                       "symbol": chord_symbol_for_root_pc(roots[k], mode_list[k])})
    ctx = {"key": key, "beats_per_bar": bpb, "chords": chords}
    return optimize_fingering(line, ctx, FingeringConfig(beats_per_bar=bpb))


st.subheader("", divider="red")
st.write("## Sample many lines & rank them by playability")
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
        try:
            res = _free_fingering_for(ml, [str(n) for n in nr], list(mp),
                                      st.session_state.key)
        except (ValueError, KeyError):
            continue
        batch.append({
            "cells": list(ml), "note_reps": [str(n) for n in nr],
            "modes": list(mp),
            "cost": res.best.total_cost,
            "where": classify_position(res.best.placed, st.session_state.key),
            "n_up": sum(1 for p in res.best.placed if p.stroke == "U"),
            "result": res,
        })
        prog.progress(min(1.0, len(batch) / n_samples),
                      text=f"{len(batch)}/{n_samples} lines fingered")
    prog.empty()
    batch.sort(key=lambda r: r["cost"])  # best-lying line first
    st.session_state.batch_lines = batch

if st.session_state.get("batch_lines"):
    batch = st.session_state.batch_lines
    st.dataframe(
        pd.DataFrame([{
            "Cost": r["cost"],
            "Line": "  →  ".join(r["cells"]),
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
        render_html(_brow["result"], tempo=int(st.session_state.get("tempo", 160))),
        height=380, scrolling=True)
    if st.button("Practice this line (make it the current line)"):
        st.session_state.melodic_line = _brow["cells"]
        st.session_state.note_representations = _brow["note_reps"]
        st.session_state.fing_mode_list = _brow["modes"]
        st.session_state.tmp = True
        st.rerun()

st.session_state.tempo = st.sidebar.number_input(
    "Metronome tempo (bpm) : ",
    min_value=30,
    max_value=300,
    value=160,
    help="Setup the metronome to 2 beats, stressing first beat, without time",
)
metronome_html = f"""
<iframe src="https://guitarapp.com/metronome.html?embed=true&tempo={st.session_state.tempo}&timeSignature=2&pattern=0"
        title="Online Metronome"
        style="width: 360px; height:520px; border:none; border-radius:4px;">
</iframe>
"""

components.html(metronome_html, height=540, width=380)

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
                f.write(render_svg(_fing, tempo=int(st.session_state.get("tempo", 160))))
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
