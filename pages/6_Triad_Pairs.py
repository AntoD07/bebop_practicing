"""Triad pairs & hexatonic scales — neck maps and alternating-triad exercises.

Pick two triads (default a whole tone apart: the Key's major triad + the major
triad a tone up — C + D, the classic Lydian / sus-dominant pair). The page maps
the pair on the WHOLE neck, then inside a named position's hand box, and then
offers the pentatonic-style exercises on the six-note union: a plain hexatonic
run, the x-notes grouping (1-2-3-4, 2-3-4-5…), and the triad-pair exercise
proper — x-note groups ALTERNATING between the two triads (every group up,
every group down, or zig-zag: one triad up, the other down, climbing or falling).
Every line is fingered by the Gypsy-jazz optimizer and ranked by cost, exactly
like the Pentatonics page (Free + the 5 positions, or EVERY fingering inside
today's position with "Enforce the position").
"""

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd

from scripts.utils import sidebar_practice_key, sidebar_metronome, PRACTICE_KEYS
from scripts.fingering.cell_bridge import root_pc
from scripts.fingering.config import FingeringConfig
from scripts.fingering.positions import POSITIONS
from scripts.fingering.render import format_report, render_html, render_svg
from scripts.pentatonics.fingering_rank import (
    rank_line_across_starts, enumerate_across_starts, PENTA_POSITION_SLACK,
)
from scripts.triad_pairs.triads import (
    ROOTS, QUALITY_NAMES, DEFAULT_PAIR_INTERVAL, Triad, TriadPair,
    SCALE_DIRECTIONS, ALTERNATING_DIRECTIONS,
    hexatonic_scale_run, hexatonic_pattern_run, alternating_triads_run,
)
from scripts.triad_pairs.neck_map import render_neck_svg, position_map_boxes

st.set_page_config(layout="wide")
st.title("Triad Pairs & Hexatonics")
st.caption(
    "Two triads, one hexatonic scale: see the pair on the whole neck and in position, "
    "then practise the scale, its x-notes groupings and the alternating-triad "
    "groupings — each fingered by the Gypsy-jazz optimizer and ranked by cost."
)

# --------------------------------------------------------------------------- #
# Sidebar — practice context, the pair, run parameters, fingering knobs.
# --------------------------------------------------------------------------- #
today_key, today_position = sidebar_practice_key()
tempo = sidebar_metronome()

_default_key_idx = PRACTICE_KEYS.index(today_key) if today_key in PRACTICE_KEYS else 0
key = st.sidebar.selectbox(
    "Key (anchors the positions)", PRACTICE_KEYS, index=_default_key_idx,
    help="Defaults to today's practice key. The position boxes are anchored on it, "
         "and it seeds the triad pair (its major triad + the one a whole tone up).",
)

st.sidebar.markdown("**Triad pair**")
_k1 = ROOTS.index(key)
_k2 = (root_pc(key) + DEFAULT_PAIR_INTERVAL) % 12  # ROOTS is in pitch-class order
_tc1, _tc2 = st.sidebar.columns(2)
root1 = _tc1.selectbox("Triad 1 root", ROOTS, index=_k1)
qual1 = _tc2.selectbox("Triad 1 quality", QUALITY_NAMES, index=0)
root2 = _tc1.selectbox("Triad 2 root", ROOTS, index=_k2)
qual2 = _tc2.selectbox("Triad 2 quality", QUALITY_NAMES, index=0)
pair = TriadPair(Triad(root1, qual1), Triad(root2, qual2))
hexa = pair.hexatonic

start_sel = st.sidebar.multiselect(
    "Starting note(s)", list(range(len(hexa))), default=[],
    format_func=lambda i: f"{hexa[i]['name']} ({hexa[i]['label']})",
    help="Which hexatonic tone the exercise starts on (for the alternating "
         "exercise it also picks the first triad: the one that owns the tone). "
         "Empty = explore ALL starting notes.",
)
n_octaves = st.sidebar.slider("Octaves", 1, 3, 2)
low_octave = st.sidebar.slider("Lowest octave (register)", 1, 4, 2)

# Same controls as the Pentatonics page: enforce today's position (box on the
# Key above, ±1 fret) and list EVERY fingering inside it.
st.session_state.enforce_position = st.session_state.get("enforce_position", True)
st.sidebar.checkbox(
    "Enforce the position", key="enforce_position",
    help=f"On: only today's position (selected above), as a box on the Key, "
         f"±{PENTA_POSITION_SLACK} fret — and ALL its fingerings are listed. "
         "Off: rank Free and the five positions.",
)
enforced_position = (POSITIONS[today_position - 1]
                     if st.session_state.enforce_position else None)
st.session_state.tp_max_cost = st.session_state.get("tp_max_cost", 30.0)
st.sidebar.slider(
    "Max fingering cost to display", 0.0, 200.0, step=1.0, key="tp_max_cost",
    help="Fingerings (total cost) above this are hidden.",
)

with st.sidebar.expander("Fingering cost weights"):
    base_cfg = FingeringConfig(
        max_stretch=st.slider("max_stretch", 3, 6, 4),
        u_cost=st.slider("u_cost (upstroke)", 0.0, 5.0, 1.0, 0.25),
        drop_cost=st.slider("drop_cost", 0.0, 30.0, 10.0, 1.0),
        shift_cost=st.slider("shift_cost /fret", 0.0, 3.0, 0.5, 0.25),
        break_cost=st.slider("break_cost (2npS)", 0.0, 10.0, 3.0, 0.5),
        sweep_bonus=st.slider("sweep_bonus", 0.0, 3.0, 0.5, 0.25),
    )

# --------------------------------------------------------------------------- #
# The pair and its hexatonic.
# --------------------------------------------------------------------------- #
st.subheader(pair.title)
if pair.first == pair.second:
    st.warning("Both triads are identical — pick a different second triad.")
_common = [pair.name_for(pc) for pc in pair.common_pcs]
st.markdown(
    f"**Hexatonic:** {' '.join(pair.hexatonic_names)} &nbsp;·&nbsp; "
    f"roots {pair.interval_name} &nbsp;·&nbsp; "
    + (f"shared tone(s): {', '.join(_common)} ({len(hexa)} distinct notes)"
       if _common else "no common tone — a true six-note hexatonic")
)
with st.expander("Tones of the pair"):
    st.dataframe(
        pd.DataFrame([{
            "Note": t["name"],
            "Triad(s)": " / ".join(pair.triads[i].symbol for i in t["triads"]),
            "Degree(s)": " / ".join(lbl.split(":")[1] for lbl in t["labels"]),
        } for t in hexa]),
        use_container_width=True, hide_index=True,
    )

# --------------------------------------------------------------------------- #
# Neck maps: the whole neck, then a position's box.
# --------------------------------------------------------------------------- #
st.subheader("On the whole neck")
_label_mode = st.radio(
    "Marker labels", ["Note names", "Triad degrees"], horizontal=True,
    label_visibility="collapsed",
)
_labels = "name" if _label_mode == "Note names" else "degree"
st.markdown(render_neck_svg(pair, labels=_labels, max_fret=base_cfg.max_fret),
            unsafe_allow_html=True)

st.subheader("In position")
_pos_numbers = list(range(1, len(POSITIONS) + 1))
map_pos = st.selectbox(
    "Position to map", _pos_numbers, index=today_position - 1,
    format_func=lambda i: f"{i} · {POSITIONS[i - 1]}",
    help="Defaults to today's position. The exercises below enforce TODAY'S "
         "position (sidebar), like the Pentatonics page; this selector only "
         "changes the map.",
)
_map_name = POSITIONS[map_pos - 1]
st.markdown(
    render_neck_svg(pair, boxes=position_map_boxes(_map_name, key, base_cfg),
                    labels=_labels, max_fret=base_cfg.max_fret,
                    slack=PENTA_POSITION_SLACK,
                    title=f"{_map_name} · box on {key}"),
    unsafe_allow_html=True,
)
st.caption(
    f"Solid box = the hand position anchored on **{key}** (both octaves of the "
    f"shape when the upper one is on the neck); dashed = the ±{PENTA_POSITION_SLACK}-fret "
    "tolerance the position exercises accept; faded tones lie outside. Open strings "
    "are shown but never fingered."
)
with st.expander("All five positions"):
    for _name in POSITIONS:
        st.markdown(
            render_neck_svg(pair, boxes=position_map_boxes(_name, key, base_cfg),
                            labels=_labels, max_fret=base_cfg.max_fret,
                            slack=PENTA_POSITION_SLACK, title=f"{_name} · box on {key}"),
            unsafe_allow_html=True,
        )

# --------------------------------------------------------------------------- #
# Exercises.
# --------------------------------------------------------------------------- #
st.subheader("Exercises")

# Starting notes to explore: the selection, or every hexatonic tone.
if start_sel:
    start_degs = [(hexa[i]["name"], i) for i in start_sel]
else:
    start_degs = [(t["name"], i) for i, t in enumerate(hexa)]
_starts_note = "" if start_sel else " · all starts"


def _generate(title, lines_by_start, group=None):
    """Rank every (starting note × fingering) and stash the rows for rendering.

    ``group`` = grouping size: partial slices align to grouping boundaries so a
    truncated pattern keeps its identity (and its triad alternation).
    """
    lines_by_start = {k: v for k, v in lines_by_start.items() if v}
    if not lines_by_start:
        st.warning("Nothing to play — the grouping is longer than the run.")
        return
    with st.spinner("Optimizing fingerings…"):
        if enforced_position:
            rows = enumerate_across_starts(lines_by_start, key, enforced_position,
                                           base_cfg, group=group)
        else:
            rows = rank_line_across_starts(lines_by_start, key, base_cfg, group=group)
    # "ver" versions the fingering table's widget key: a dataframe's row
    # selection cannot be cleared programmatically in Streamlit, so each
    # generation gets a FRESH table — the display always follows the new result.
    ver = st.session_state.get("tp", {}).get("ver", 0) + 1
    st.session_state.tp = {"title": title, "rows": rows,
                           "multi": len(lines_by_start) > 1, "ver": ver,
                           "enforced": enforced_position}


exercise = st.radio(
    "Exercise",
    ["Hexatonic scale run", "x-notes grouping (hexatonic)",
     "Alternating triads (x-notes grouping)"],
    horizontal=True, key="tp_exercise",
)

if exercise == "Hexatonic scale run":
    direction = st.selectbox("Direction", SCALE_DIRECTIONS, index=0, key="tp_scale_dir")
    st.caption("The six notes played as a scale, straight through.")
    if st.button("Generate scale run", type="primary", key="tp_gen_scale"):
        lbs = {lbl: hexatonic_scale_run(pair, low_octave, n_octaves, direction, start_deg=sd)
               for lbl, sd in start_degs}
        _generate(f"{pair.title} hexatonic — {direction} ({n_octaves} oct){_starts_note}", lbs)

elif exercise == "x-notes grouping (hexatonic)":
    x1, x2 = st.columns((0.4, 0.6))
    x_notes = int(x1.number_input("Notes per group (x)", 2, 8, 4, key="tp_hex_x"))
    direction = x2.selectbox("Direction", SCALE_DIRECTIONS, index=0, key="tp_hex_dir")
    st.caption(f"Groups of {x_notes} consecutive hexatonic notes, each starting one "
               "scale note after the previous (1-2-3-4, 2-3-4-5, …); descending runs "
               "the same from the top. The tab brackets each group.")
    if st.button("Generate grouping", type="primary", key="tp_gen_hex"):
        lbs = {lbl: hexatonic_pattern_run(pair, low_octave, n_octaves, x_notes, direction,
                                          start_deg=sd)
               for lbl, sd in start_degs}
        _generate(f"{pair.title} — {x_notes}-notes grouping, {direction} ({n_octaves} oct)"
                  f"{_starts_note}", lbs, group=x_notes)

elif exercise == "Alternating triads (x-notes grouping)":
    a1, a2 = st.columns((0.4, 0.6))
    x_notes = int(a1.number_input("Notes per group (x)", 2, 8, 3, key="tp_alt_x"))
    direction = a2.selectbox("Direction", ALTERNATING_DIRECTIONS, index=0, key="tp_alt_dir")
    _t1, _t2 = pair.first.symbol, pair.second.symbol
    st.caption(
        f"Groups of {x_notes} arpeggio tones alternating **{_t1}** / **{_t2}**, each "
        "group starting on the next tone of its own triad — the inversions walk through "
        "the range. *Ascending*: every group up (C E G · D F# A · E G C …); "
        "*descending*: every group down, from the top; *alternating ↑↓*: one triad up, "
        "the other down from the next tone above, the pairs climbing "
        "(C E G · A F# D · E G C · D A F# …); *alternating ↓↑*: the mirror, falling. "
        "The tab brackets each group with its triad."
    )
    if st.button("Generate alternating triads", type="primary", key="tp_gen_alt"):
        lbs = {lbl: alternating_triads_run(pair, low_octave, n_octaves, x_notes, direction,
                                           start_deg=sd)
               for lbl, sd in start_degs}
        _generate(f"{pair.title} — alternating triads, {x_notes} notes, {direction} "
                  f"({n_octaves} oct){_starts_note}", lbs, group=x_notes)

# --------------------------------------------------------------------------- #
# Render: show the ranked fingerings and draw the selected tab.
# --------------------------------------------------------------------------- #
if st.session_state.get("tp"):
    tp = st.session_state.tp
    rows = tp["rows"]
    multi = tp["multi"]
    st.subheader(tp["title"])

    _n_all = len(rows)
    rows = [r for r in rows if r["cost"] is None or r["cost"] <= st.session_state.tp_max_cost]
    if len(rows) < _n_all:
        st.caption(f"{_n_all - len(rows)} fingering(s) hidden by the sidebar's max cost "
                   f"({st.session_state.tp_max_cost:g}).")
    if tp.get("enforced"):
        st.caption(f"**{len(rows)} fingerings in {tp['enforced']}** "
                   f"(±{PENTA_POSITION_SLACK} fret, box on {key}), cheapest per note first "
                   "— click a row for its tab.")
        view = rows
    else:
        _styles = list(dict.fromkeys(r["position"] for r in rows))
        style_filter = st.multiselect(
            "Filter by fingering style", _styles, default=[],
            help="Empty = all. Pick e.g. one position to compare it across starting notes.",
        )
        view = [r for r in rows if not style_filter or r["position"] in style_filter]

    def _mk(r):
        d = {"Start": r.get("start", "")} if multi else {}
        if not tp.get("enforced"):
            d["Fingering"] = r["position"]
        d["Cost/note"] = round(r["cpn"], 2) if r.get("cpn") is not None else None
        d["Cost"] = round(r["cost"], 2) if r["cost"] is not None else None
        d["Played at"] = r["where"]
        if tp.get("enforced"):
            pl = r["result"].best.placed
            d["Frets"] = f"{min(p.fret for p in pl)}–{max(p.fret for p in pl)}"
            d["Upstrokes"] = sum(1 for p in pl if p.stroke == "U")
            d["Layout (string/fret)"] = r.get("layout", "")
        return d

    # The table key is versioned per generation: dataframe selections cannot be
    # cleared programmatically, so a fresh key guarantees a fresh selection.
    _tbl_key = f"tp_fing_table_{tp.get('ver', 0)}"
    st.dataframe(
        pd.DataFrame([_mk(r) for r in view]),
        use_container_width=True, hide_index=True,
        selection_mode="single-row", on_select="rerun", key=_tbl_key,
    )
    sel = st.session_state[_tbl_key].selection["rows"]
    row = view[sel[0]] if sel and sel[0] < len(view) else next(
        (r for r in view if r["result"] is not None), view[0] if view else None)

    if row is None:
        st.warning("Nothing to show — raise the max cost, or untick 'Enforce the position'.")
    elif row["result"] is None:
        st.warning(f"'{row['position']}' has no feasible fingering — pick another row.")
    else:
        _lead = f"start on {row['start']} · " if multi and row.get("start") else ""
        st.caption(f"Showing: {_lead}**{row['position']}** · {row['where']}")
        components.html(render_html(row["result"], tempo=int(tempo)), height=380, scrolling=True)
        with st.expander("Full report (per-note table, flags, cost)"):
            st.code(format_report(row["result"]), language="text")
        st.download_button(
            "Download tab as SVG", render_svg(row["result"], int(tempo)),
            file_name="triad_pair_tab.svg", mime="image/svg+xml",
        )
