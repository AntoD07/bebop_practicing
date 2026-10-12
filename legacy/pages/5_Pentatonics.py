"""Pentatonic practice — scale runs, chromaticism, Bergonzi patterns, shifting.

Generates pentatonic note-lines and runs them through the Gypsy-jazz fingering
engine, showing a cost-ranked set of fingerings (Free, the user's 3+2 layout, an
open-string reposition pivot, and the 5 named neck positions). Exercises can start
on any pentatonic note; leaving the "Starting note" selector empty explores them
all. Pick a row to render its SoundSlice-style tab with picking and a play-along.
"""

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd

from scripts.utils import sidebar_practice_key, sidebar_metronome
from scripts.fingering.config import FingeringConfig
from scripts.fingering.render import format_report, render_html, render_svg
from scripts.pentatonics.pentatonics import (
    PENTATONICS,
    PENTATONIC_NAMES,
    DIRECTIONS,
    SHIFT_CHOICES,
    shift_offsets,
    scale_run,
    chromatic_run,
    notes_pattern_run,
    shift_run,
)
from scripts.pentatonics.bergonzi import load_patterns, apply_pattern, shift_pattern
from scripts.pentatonics.fingering_rank import (
    rank_pentatonic_fingerings, rank_across_starts, enumerate_across_starts,
    enumerate_position_fingerings, PENTA_POSITION_SLACK,
)
from scripts.fingering.positions import POSITIONS

_KEYS = ["C", "G", "D", "A", "E", "B", "F#", "F", "Bb", "Eb", "Ab", "Db"]

st.set_page_config(layout="wide")
st.title("Pentatonic Practice")
st.caption(
    "Scale runs, chromaticism, Bergonzi shapes and shifting — each fingered by the "
    "Gypsy-jazz optimizer and ranked by cost across neck positions and run styles."
)

# --------------------------------------------------------------------------- #
# Sidebar — practice context + scale choice + fingering knobs.
# --------------------------------------------------------------------------- #
st.session_state.key, st.session_state.position = sidebar_practice_key()
tempo = sidebar_metronome()

_default_key_idx = _KEYS.index(st.session_state.key) if st.session_state.key in _KEYS else 0
key = st.sidebar.selectbox(
    "Key", _KEYS, index=_default_key_idx,
    help="Defaults to today's practice key; change it to transpose.",
)
penta = st.sidebar.selectbox("Pentatonic", PENTATONIC_NAMES, index=0)  # minor default
_degrees = PENTATONICS[penta]["degrees"]
start_notes = st.sidebar.multiselect(
    "Starting note(s)", _degrees, default=[],
    help="Which pentatonic note the run starts on. Empty = explore ALL starting notes.",
)
n_octaves = st.sidebar.slider("Octaves", 1, 3, 3)
low_octave = st.sidebar.slider("Lowest octave (register)", 1, 4, 1)

# Same controls as Cell Connexions / Melodic Lines: enforce today's position
# (box on the Key above, ±1 fret) and list EVERY fingering inside it.
st.session_state.enforce_position = st.session_state.get("enforce_position", True)
st.sidebar.checkbox(
    "Enforce the position", key="enforce_position",
    help=f"On: only today's position (selected above), as a box on the Key, "
         f"±{PENTA_POSITION_SLACK} fret — and ALL its fingerings are listed. "
         "Off: compare every fingering system (Free, 3+2, sliding, all positions).",
)
enforced_position = (POSITIONS[st.session_state.position - 1]
                     if st.session_state.enforce_position else None)
st.session_state.pent_max_cost = st.session_state.get("pent_max_cost", 30.0)
st.sidebar.slider(
    "Max fingering cost to display", 0.0, 200.0, step=1.0, key="pent_max_cost",
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

# Starting notes to explore: the selection, or all pentatonic degrees.
if start_notes:
    start_degs = [(lbl, _degrees.index(lbl)) for lbl in start_notes]
else:
    start_degs = [(lbl, i) for i, lbl in enumerate(_degrees)]


def _generate(title, lines_by_start, group=None):
    """Rank every (starting note × fingering) and stash the rows for rendering.

    ``group`` = pattern grouping size (4 for Bergonzi formulas): partial slices
    align to grouping boundaries so a truncated pattern keeps its identity.
    """
    with st.spinner("Optimizing fingerings…"):
        if enforced_position:
            rows = enumerate_across_starts(lines_by_start, key, enforced_position,
                                           base_cfg, group=group)
        else:
            rows = rank_across_starts(lines_by_start, key, base_cfg, root=key,
                                      penta=penta, group=group)
    # "ver" versions the fingering table's widget key: a dataframe's row
    # selection cannot be cleared programmatically in Streamlit, so each
    # generation gets a FRESH table — the display always follows the new result.
    ver = st.session_state.get("pent", {}).get("ver", 0) + 1
    st.session_state.pent = {"title": title, "rows": rows,
                             "multi": len(lines_by_start) > 1, "ver": ver,
                             "enforced": enforced_position}


# --------------------------------------------------------------------------- #
# Exercise selector + per-exercise parameters.
# --------------------------------------------------------------------------- #
exercise = st.radio(
    "Exercise",
    ["Scale run", "x-notes pattern", "Chromatic passing tones", "Bergonzi patterns", "Shifting"],
    horizontal=True,
)
_starts_note = "" if start_notes else " · all starts"

if exercise == "Scale run":
    direction = st.selectbox("Direction", DIRECTIONS, index=0)
    if st.button("Generate scale run", type="primary"):
        lbs = {lbl: scale_run(key, penta, low_octave, n_octaves, direction, start_deg=sd)
               for lbl, sd in start_degs}
        _generate(f"{key} {penta} pentatonic — {direction} ({n_octaves} oct){_starts_note}", lbs)

elif exercise == "x-notes pattern":
    x1, x2 = st.columns((0.4, 0.6))
    x_notes = int(x1.number_input("Notes per group (x)", 2, 8, 4))
    direction = x2.selectbox("Direction", DIRECTIONS, index=0, key="xpat_dir")
    st.caption(f"Groups of {x_notes} consecutive pentatonic notes, each starting one "
               "scale note after the previous (1-2-3-4, 2-3-4-5, …); descending runs "
               "the same from the top. The tab brackets each group.")
    if st.button("Generate pattern", type="primary"):
        lbs = {lbl: notes_pattern_run(key, penta, low_octave, n_octaves, x_notes, direction,
                                      start_deg=sd)
               for lbl, sd in start_degs}
        _generate(f"{key} {penta} — {x_notes}-notes pattern, {direction} ({n_octaves} oct)"
                  f"{_starts_note}", lbs, group=x_notes)

elif exercise == "Chromatic passing tones":
    c1, c2 = st.columns((0.5, 0.5))
    direction = c1.selectbox("Direction", DIRECTIONS, index=0)
    add_b6 = c2.checkbox("Add b6", value=False, help="Also fill the 5→b7 gap with b6.")
    st.caption("Fills each whole-step gap with a passing tone "
               "(minor: 1-b3-**3**-4-**#4**-5-b7-**7**).")
    if st.button("Generate chromatic run", type="primary"):
        lbs = {lbl: chromatic_run(key, penta, low_octave, n_octaves, direction, add_b6, start_deg=sd)
               for lbl, sd in start_degs}
        _generate(f"{key} {penta} + chromatics — {direction}"
                  + (" +b6" if add_b6 else "") + _starts_note, lbs)

elif exercise == "Bergonzi patterns":
    patterns = load_patterns()
    names = [p["name"] for p in patterns]
    st.caption("Formulas 1-4 descend, 5-8 ascend (direction is built into the contour). "
               "Bergonzi formulas define their own start, so the Starting-note selector "
               "doesn't apply here.")
    sel_name = st.selectbox("Formula", names)
    shift_choice = st.selectbox(
        "Shift the formula (side-slip)", ["No shift — sweep the scale"] + SHIFT_CHOICES,
        help="Sweep the whole scale, or take the 4-note formula cell and side-slip it "
             "by an interval (shifting is usually done with a pattern).",
    )
    use_shift = shift_choice != "No shift — sweep the scale"
    if use_shift:
        sc1, sc2 = st.columns((0.5, 0.5))
        groups_per_shift = sc1.number_input(
            "Groupings before each shift", 1, 6, 2, key="berg_gps",
            help="How many 4-note groupings of the formula to play in a key "
                 "before side-slipping to the next key.")
        n_shifts = sc2.number_input("Number of key shifts", 1, 8, 3, key="berg_nshifts")
        st.caption("After each shift the pattern CONTINUES from the new key's "
                   "pentatonic tone closest to the last note (voice-leading), "
                   "not a restart of the same cell.")

    def _berg_line(pat):
        """The exercise line for a formula, honouring the side-slip selector."""
        if use_shift:
            offs = shift_offsets(shift_choice, int(n_shifts) + 1)
            return shift_pattern(key, penta, pat, offs, low_octave,
                                 groups_per_shift=int(groups_per_shift))
        return apply_pattern(key, penta, pat, low_octave, n_octaves)

    _shift_note = (f", {int(groups_per_shift)} grp/key, shift by {shift_choice.lower()} "
                   f"×{int(n_shifts)}" if use_shift else "")
    b1, b2 = st.columns((0.6, 0.4))
    if b1.button("Generate this formula", type="primary"):
        pat = patterns[names.index(sel_name)]
        _generate(f"{key} {penta} — {sel_name}{_shift_note}",
                  {sel_name: _berg_line(pat)}, group=len(pat["offsets"]))
    if b2.button("Rank ALL formulas easiest→hardest"):
        ranked = []
        for pat in patterns:
            ln = _berg_line(pat)
            if enforced_position:
                rows = enumerate_position_fingerings(ln, key, enforced_position, base_cfg,
                                                     group=len(pat["offsets"]))
            else:
                rows = rank_pentatonic_fingerings(ln, key, base_cfg, root=key, penta=penta,
                                                  group=len(pat["offsets"]))
            feas = [r for r in rows if r["result"] is not None]
            # Best = fullest coverage first, then cheapest per note — a cheap
            # 8-note fragment must not outrank a 20-note fingering.
            best = max(feas, key=lambda r: (r["covered"], -r["cpn"])) if feas else None
            ranked.append({"Formula": pat["name"],
                           "Cost/note": round(best["cpn"], 2) if best else None,
                           "Played at": best["where"] if best else "—",
                           "_line": ln, "_group": len(pat["offsets"])})
        ranked.sort(key=lambda r: (r["Cost/note"] is None, r["Cost/note"] or 0.0))
        st.session_state.berg_ranked = ranked
        st.session_state.berg_title_note = _shift_note
        # Versioned key: a dataframe selection cannot be cleared programmatically,
        # so each fresh ranking gets a fresh table (and a fresh selection).
        st.session_state.berg_ver = st.session_state.get("berg_ver", 0) + 1
        st.session_state.berg_loaded = None
    if st.session_state.get("berg_ranked"):
        st.markdown("**Formulas ranked by playability** (select one to load it):")
        rk = st.session_state.berg_ranked
        _btbl = f"berg_table_{st.session_state.get('berg_ver', 0)}"
        st.dataframe(
            pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in rk]),
            use_container_width=True, hide_index=True,
            selection_mode="single-row", on_select="rerun", key=_btbl,
        )
        bsel = st.session_state[_btbl].selection["rows"]
        # Load only when the SELECTION CHANGES — a sticky selection must not
        # stomp later manual generates.
        if bsel:
            chosen = rk[bsel[0]]
            if st.session_state.get("berg_loaded") != chosen["Formula"]:
                st.session_state.berg_loaded = chosen["Formula"]
                _generate(f"{key} {penta} — {chosen['Formula']}"
                          f"{st.session_state.get('berg_title_note', '')}",
                          {chosen["Formula"]: chosen["_line"]}, group=chosen["_group"])

elif exercise == "Shifting":
    s1, s2, s3 = st.columns((0.4, 0.3, 0.3))
    interval_name = s1.selectbox("Shift interval / cycle", SHIFT_CHOICES, index=2)
    n_shifts = s2.number_input("Number of key shifts", 1, 8, 3)
    direction = s3.selectbox("Direction (each block)", DIRECTIONS, index=0, key="shift_dir")
    st.caption("Side-slipping: play the pentatonic once per key block. Cycles "
               "(e.g. home → +semitone → tritone) return to the home key each round.")
    if st.button("Generate shifting exercise", type="primary"):
        offs = shift_offsets(interval_name, int(n_shifts) + 1)
        lbs = {lbl: shift_run(key, penta, offs, direction, low_octave,
                              octaves_per_block=1, start_deg=sd)
               for lbl, sd in start_degs}
        _generate(f"{key} {penta} — {interval_name.lower()} "
                  f"×{int(n_shifts)}{_starts_note}", lbs)

# --------------------------------------------------------------------------- #
# Render: show the ranked fingerings and draw the selected tab.
# --------------------------------------------------------------------------- #
if st.session_state.get("pent"):
    pent = st.session_state.pent
    rows = pent["rows"]
    multi = pent["multi"]
    st.subheader(pent["title"])

    _n_all = len(rows)
    rows = [r for r in rows if r["cost"] is None or r["cost"] <= st.session_state.pent_max_cost]
    if len(rows) < _n_all:
        st.caption(f"{_n_all - len(rows)} fingering(s) hidden by the sidebar's max cost "
                   f"({st.session_state.pent_max_cost:g}).")
    if pent.get("enforced"):
        st.caption(f"**{len(rows)} fingerings in {pent['enforced']}** "
                   f"(±{PENTA_POSITION_SLACK} fret, box on {key}), cheapest per note first "
                   "— click a row for its tab.")
        view = rows
    else:
        # Filter by fingering style (empty = show all).
        _styles = list(dict.fromkeys(r["position"] for r in rows))
        style_filter = st.multiselect(
            "Filter by fingering style", _styles, default=[],
            help="Empty = all styles. Pick e.g. only '3+2 per string' to compare it "
                 "across starting notes.",
        )
        view = [r for r in rows if not style_filter or r["position"] in style_filter]

    def _mk(r):
        d = {"Start": r.get("start", "")} if multi else {}
        if not pent.get("enforced"):
            d["Fingering"] = r["position"]
        d["Cost/note"] = round(r["cpn"], 2) if r.get("cpn") is not None else None
        d["Cost"] = round(r["cost"], 2) if r["cost"] is not None else None
        d["Played at"] = r["where"]
        if pent.get("enforced"):
            pl = r["result"].best.placed
            d["Frets"] = f"{min(p.fret for p in pl)}–{max(p.fret for p in pl)}"
            d["Upstrokes"] = sum(1 for p in pl if p.stroke == "U")
            d["Layout (string/fret)"] = r.get("layout", "")
        return d

    # The table key is versioned per generation: dataframe selections cannot be
    # cleared programmatically, so a fresh key guarantees a fresh selection.
    _tbl_key = f"pent_fing_table_{pent.get('ver', 0)}"
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
            file_name="pentatonic_tab.svg", mime="image/svg+xml",
        )
