import streamlit as st
import streamlit.components.v1 as components

import ast
import time

import pandas as pd

from scripts.utils import (
    get_or_update_practice_details,
    join_notes,
)

from scripts.melodic_lines.combinations import find_combinations_on_pivot_new

from scripts.fingering.config import FingeringConfig
from scripts.fingering.optimizer import optimize_fingering
from scripts.fingering.render import render_html, format_report
from scripts.fingering.cell_bridge import (
    build_connection_line,
    chord_symbol_for_mode,
    chord_symbol_for_root_pc,
    DEFAULT_MODE_ROOT_OFFSET,
    root_pc,
)
from scripts.fingering.positions import (
    classify_position,
    position_config_for_key,
    POSITIONS,
)


from scripts.modes.mode_transposition import (
    translate_dom_to_minor,
    translate_dom_to_major,
)

from scripts.load_cells import create_cell_frames

st.set_page_config(layout="wide")
# Example of setting up the practice routine
st.title("Practicing Bebop Cell combinations")

st.session_state.key, st.session_state.position = get_or_update_practice_details()
st.sidebar.subheader(f"Today's Key: :blue[{st.session_state.key}]")
st.sidebar.subheader(
    f"Today's Position (for guitar): :blue[{st.session_state.position}]"
)
st.session_state.include_bonus = st.sidebar.checkbox(
    "Whether to include bonus cells", value=st.session_state.get("include_bonus", False)
)
_POS_OPTIONS = ["Free (best on the neck)"] + POSITIONS
_default_pos = (st.session_state.position
                if isinstance(st.session_state.position, int)
                and 1 <= st.session_state.position <= len(POSITIONS) else 0)
st.session_state.fingering_position = st.sidebar.selectbox(
    "Fingering position",
    _POS_OPTIONS,
    index=_default_pos,
    help="Free = the single cheapest fingering anywhere on the neck. Pick a "
         "named position to force every connection into that key-anchored box.",
)
# Use key and position in your Streamlit application
c1, c2 = st.columns((0.5, 0.5))

with c1:
    st.session_state.chord1 = st.selectbox(
        "Select first chord to practice",
        [
            "Maj7",
            # "7sus4",
            "Dorian",
            "Myxolidian",
            "Locrian",
            "MajorResolutions",
            "MinorResolutions",
        ],
        index=[
            "Maj7",
            # "7sus4",
            "Dorian",
            "Myxolidian",
            "Locrian",
            "MajorResolutions",
            "MinorResolutions",
        ].index(st.session_state.get("chord1", "Dorian")),
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
            "Dorian",
            "Myxolidian",
            "Locrian",
            "MajorResolutions",
            "MinorResolutions",
        ],
        index=2,
    )
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
    ]:
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


st.subheader("", divider="red")


st.session_state.tone_modified = st.selectbox(
    "Select a pivot note (starting second cell)",
    set(
        list(
            set(mapped_names_2.astype(str)).intersection(
                set(mapped_names_1.astype(str))
            )
        )
        + list(
            set(mapped_names_1.astype(str)).intersection(
                set(mapped_names_2.astype(str))
            )
        )
    ),
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

st.session_state.tempo = st.number_input(
    "Metronome tempo (bpm) : ",
    min_value=30,
    max_value=300,
    value=160,
    help="Setup the metronome to 2 beats, stressing first beat, without time",
)

with st.expander("🎵 Metronome"):
    metronome_html = f"""
<iframe src="https://guitarapp.com/metronome.html?embed=true&tempo={st.session_state.tempo}&timeSignature=2&pattern=0"
        title="Online Metronome"
        style="width: 360px; height:520px; border:none; border-radius:4px;">
</iframe>
"""
    components.html(metronome_html, height=540, width=380)

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


@st.cache_data(show_spinner=False)
def score_connections(key, chord1, chord2, end_records, start_records,
                      position="Free (best on the neck)"):
    """Score each ending->starting pair as ONE merged line.

    The pivot note is SHARED — the last note of the first cell IS the first
    note of the second (len1 + len2 - 1 notes total) — and the whole line goes
    through a single DP, so the cost is the cost of the entire connection.
    Cell 2's root is derived from the pivot pitch, so the join is seamless.

    ``position``: "Free" searches the whole neck for the single cheapest
    fingering; a named position constrains the search to that key-anchored box
    (trying each octave the line fits in, keeping the cheapest).
    """
    sym1 = chord_symbol_for_mode(key, chord1)
    kpc = root_pc(key)
    constrained = position in POSITIONS
    if constrained:
        pos_cfg, pos_root_midi = position_config_for_key(position, key)
    rows = []
    for n1, d1, mv1 in end_records:
        for n2, d2, mv2 in start_records:
            cell1 = {"name": n1,
                     "root": (kpc + DEFAULT_MODE_ROOT_OFFSET.get(chord1, 0)) % 12,
                     "degrees": list(d1), "mode": chord1, "movement": mv1}
            cell2 = {"name": n2, "root": 0,  # derived from the pivot
                     "degrees": list(d2), "mode": chord2, "movement": mv2}
            # Overlapping 5-note cells stride every 4 beats: the pivot lands
            # on beat 1 of the second bar (a rest-stroke downbeat).
            bpb = max(1, len(d1) - 1)
            result, pivot_index, err = None, len(d1) - 1, None
            if constrained:
                # Try each octave register of the position's box, keep cheapest.
                for off in (-12, 0, 12, 24):
                    try:
                        line, pivot_index, root2_pc = build_connection_line(
                            cell1, cell2, base_midi=pos_root_midi + off)
                        ctx = {"key": key, "beats_per_bar": bpb,
                               "chords": [{"start_beat": 0, "symbol": sym1},
                                          {"start_beat": pivot_index,
                                           "symbol": chord_symbol_for_root_pc(root2_pc, chord2)}]}
                        cand = optimize_fingering(
                            line, ctx, pos_cfg.with_overrides(beats_per_bar=bpb))
                    except (ValueError, KeyError) as e:
                        err = e
                        continue
                    if result is None or cand.best.total_cost < result.best.total_cost:
                        result = cand
                if result is None:
                    rows.append({"end": n1, "start": n2, "cost": None,
                                 "pivot": "does not fit this position",
                                 "position": "-", "result": None,
                                 "n_up": None, "n_flags": None})
                    continue
            else:
                try:
                    line, pivot_index, root2_pc = build_connection_line(cell1, cell2)
                    sym2 = chord_symbol_for_root_pc(root2_pc, chord2)
                    ctx = {"key": key, "beats_per_bar": bpb,
                           "chords": [{"start_beat": 0, "symbol": sym1},
                                      {"start_beat": pivot_index, "symbol": sym2}]}
                    cfg = FingeringConfig(beats_per_bar=bpb)
                    result = optimize_fingering(line, ctx, cfg)
                except (ValueError, KeyError) as e:
                    rows.append({"end": n1, "start": n2, "cost": None,
                                 "pivot": f"error: {e}", "position": "-",
                                 "result": None, "n_up": None, "n_flags": None})
                    continue
            pv = result.notes[pivot_index]
            rows.append({
                "end": n1, "start": n2,
                "cost": result.best.total_cost,
                "pivot": f"{pv.name} ({d1[-1]}={d2[0]})",
                "position": classify_position(result.best.placed, key),
                "n_up": sum(1 for p in result.best.placed if p.stroke == "U"),
                "n_flags": len(result.best.flags),
                "result": result,
            })
    # Rank by cost, decreasing (hardest first); failures sink to the bottom.
    rows.sort(key=lambda r: (r["cost"] is None,
                             -(r["cost"] if r["cost"] is not None else 0.0)))
    return rows


st.subheader("", divider="red")
st.write("## Fingering for each connection (one line, ranked by cost — "
         "click a row to see its tab)")

conn_rows = []
if combinations:
    with st.spinner("Scoring all pairwise connections..."):
        conn_rows = score_connections(
            st.session_state.key,
            st.session_state.chord1,
            st.session_state.chord2,
            _cell_records(ending_cells_filtered),
            _cell_records(starting_cells_filtered),
            position=st.session_state.fingering_position,
        )

if conn_rows:
    st.dataframe(
        pd.DataFrame([
            {"Ending cell": r["end"], "Starting cell": r["start"],
             "Cost": r["cost"], "Pivot": r["pivot"], "Position": r["position"],
             "Upstrokes": r["n_up"], "Flags": r["n_flags"]}
            for r in conn_rows
        ]),
        use_container_width=True,
        selection_mode="single-row",
        on_select="rerun",
        key="conn_table",
    )
    # Row click selects the connection; default to the hardest one.
    _sel_rows = st.session_state.conn_table.selection["rows"]
    _row = conn_rows[_sel_rows[0]] if _sel_rows else conn_rows[0]
    st.write(f"**{_row['end']}  →  {_row['start']}**   ·   cost "
             + (f"{_row['cost']:.2f}" if _row["cost"] is not None else "n/a")
             + f"   ·   {_row['position']}")
    if _row["result"] is None:
        st.warning(f"No playable fingering: {_row['pivot']}")
    else:
        components.html(
            render_html(_row["result"], tempo=int(st.session_state.get("tempo", 160))),
            height=360, scrolling=True)
        with st.expander("Full report (per-note table, flags, cost)"):
            st.code(format_report(_row["result"]), language="text")

_conn_lookup = {(r["end"], r["start"]): r["result"] for r in conn_rows}
st.session_state.show_tab_in_exercise = st.checkbox(
    "Show fingering tab during the exercise", value=True)
# Total duration for practicing all combinations
total_time_minutes = st.sidebar.number_input(
    "Total practice time (min) : ", min_value=1, max_value=120, value=10
)

# Calculate time per combination
if combinations:
    time_per_combination = int((total_time_minutes * 60) / len(combinations))
    st.sidebar.write(
        f"Time per combination : :blue[{time_per_combination}] seconds"
    )
else:
    time_per_combination = 0
# Calculate display time per combination
if combinations:
    st.write(
        f"Each combination will be displayed for :green[{time_per_combination}] seconds."
    )
else:
    st.write("No combinations available for the selected pivot note.")

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
    for i, _ in enumerate(combinations):
        # Inject JavaScript for auto-scrolling
        js = """
        <script>
        window.scrollTo(0, document.body.scrollHeight);
        </script>
        """
        st.markdown(js, unsafe_allow_html=True)
        c1, c2, c3 = st.columns((0.45, 0.45, 0.1))
        try:
            current_combination = combinations[
                st.session_state.current_combination_index
            ]
            current_name = names[st.session_state.current_combination_index]

            c1.markdown(f"##### {current_combination[0]}")
            c2.markdown(f"##### {current_combination[1]}")
            if st.session_state.get("show_tab_in_exercise"):
                _r = _conn_lookup.get(tuple(current_name))
                if _r is not None:
                    components.html(
                        render_html(_r, tempo=int(st.session_state.tempo)),
                        height=340, scrolling=True)
            ph = c3.empty()
            N = int(time_per_combination)
            for secs in range(N, -1, -1):
                mm, ss = secs // 60, secs % 60
                ph.metric(
                    f"{i+1}/{len(combinations)}",
                    f"{mm:02d}:{ss:02d}",
                    label_visibility="collapsed",
                )
                time.sleep(1)
            next_combination()

        except IndexError:
            st.success("Completed all combinaisons")
