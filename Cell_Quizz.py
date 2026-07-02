import streamlit as st
import streamlit.components.v1 as components
import random

from scripts.load_cells import create_cell_frames

from scripts.utils import (
    validate_results,
    join_notes,
    cell_from_string,
    get_or_update_practice_details,
)

from scripts.modes.mode_transposition import translate_dom_to_minor
from scripts.fingering.config import FingeringConfig
from scripts.fingering.cell_bridge import cell_degrees, cell_movement
from scripts.fingering.positions import optimize_all_positions, POSITION_DESC, POSITIONS
from scripts.fingering.render import render_html, format_note_table

st.title("Bebop practice app")
previous_chord = st.session_state.get("chord")

# Today's rotating practice key + position (shared with the other pages).
st.session_state.practice_key, st.session_state.practice_position = (
    get_or_update_practice_details()
)
st.sidebar.subheader(f"Today's Key: :blue[{st.session_state.practice_key}]")
st.sidebar.subheader(
    f"Today's Position (for guitar): :blue[{st.session_state.practice_position}]"
)

st.session_state.include_bonus = st.sidebar.checkbox(
    "Whether to include bonus cells", value=st.session_state.get("include_bonus", False)
)
_KEYS = ["C", "G", "D", "A", "E", "B", "F#", "Db", "Ab", "Eb", "Bb", "F"]
_default_key_idx = (
    _KEYS.index(st.session_state.practice_key)
    if st.session_state.practice_key in _KEYS else 0
)
st.session_state.fingering_key = st.sidebar.selectbox(
    "Key (for the fingering tabs)", _KEYS, index=_default_key_idx,
    help="Defaults to today's practice key; change it to transpose the fingering.",
)

st.session_state.chord = st.selectbox(
    "Select chord to practice",
    [
        "Maj7",
        "Dorian",
        "Myxolidian",
        "Locrian",
        "MajorResolutions",
        "MinorResolutions",
    ],
    index=1,
)

if st.session_state.chord == "Locrian":
    st.session_state.loc_2_dominant = st.checkbox(
        "Translate Locrian to Dominant", value=True
    )
else:
    st.session_state.loc_2_dominant = False
if st.session_state.chord in ["MinorResolutions", "Locrian"]:
    st.session_state.dom_to_minor = st.checkbox(
        "Translate Dominant to Minor-I", value=True
    )
else:
    st.session_state.dom_to_minor = False

df_cells, _, mapping_1 = create_cell_frames(
    st.session_state.chord,
    False,
    False,
    st.session_state.include_bonus,
    "End Note",
    st.session_state.loc_2_dominant,
    st.session_state.dom_to_minor,
)

# if st.session_state.permute and (st.session_state.chord in ["Dorian", "Locrian"]):
#     df_cells = translate_sus4_to_other_mode(df_cells, st.session_state.chord)
#     if st.session_state.chord == "Locrian" and st.session_state.loc_2_dom:
#         df_cells = translate_loc_to_dominant(df_cells)
if (
    st.session_state.chord in ["MinorResolutions", "Locrian"]
) and st.session_state.dom_to_minor:
    df_cells = translate_dom_to_minor(df_cells)


names = list(df_cells.index)

if st.session_state.chord != previous_chord:
    st.session_state.name = random.choice(names)
    st.session_state.starting_note = random.choice(
        list(df_cells["Start Note"].unique())
    )


if st.button("Randomize again "):
    st.session_state.name = random.choice(names)
    st.session_state.starting_note = random.choice(
        list(df_cells["Start Note"].unique())
    )
    st.session_state.ending_note = random.choice(list(df_cells["End Note"].unique()))

st.subheader("", divider="red")
st.write(
    "## Refresh memory on cells",
)
st.session_state.name = st.selectbox(
    "Refresh memory on any cell",
    names,
    index=list(names).index(st.session_state.get("name", random.choice(names))),
)
input = st.text_input("Cell notes (w.r.t. to the type of chord)")
c = cell_from_string(input)
answer = df_cells.loc[st.session_state.name]
if st.button("Submit"):
    if c == join_notes(answer["Notes"]):
        st.success("Good Answer !")
    else:
        st.error("Incorrect !")
with st.expander("See solution"):
    st.write(join_notes(answer["Notes"]), answer["Movement"])

# --- Fingering for the selected cell, in all five positions ----------------
st.subheader("", divider="red")
st.write(f"## Fingering for **{st.session_state.name}**  "
         f"(:blue[{st.session_state.fingering_key} {st.session_state.chord}])")
st.caption(
    "Pitches fixed by the cell; the solver finds each position's string/fret "
    "layout and derives Gypsy picking (⊓ rest-stroke down, ∨ parity upstroke)."
)
try:
    _degs = cell_degrees(st.session_state.chord, st.session_state.name)
    _mv = cell_movement(st.session_state.chord, st.session_state.name)
    _cell = {
        "name": st.session_state.name,
        "root": st.session_state.fingering_key,
        "degrees": _degs,
        "mode": st.session_state.chord,
        "movement": _mv,
    }
    _ctx = {
        "key": st.session_state.fingering_key,
        "chords": [{"start_beat": 0,
                    "symbol": f"{st.session_state.fingering_key} {st.session_state.chord}"}],
    }
    # Positions are anchored to today's KEY and returned ranked by cost (desc).
    _positions = optimize_all_positions(_cell, _ctx, FingeringConfig())

    # Today's rotating position (1..5) maps to a fixed position name (order-independent).
    _today_pos = st.session_state.practice_position
    _today_name = (POSITIONS[_today_pos - 1]
                   if isinstance(_today_pos, int) and 1 <= _today_pos <= len(POSITIONS)
                   else None)
    if _today_name:
        st.caption(f"⭐ Today's focus position: {_today_pos} — {_today_name}  "
                   f"(tabs ranked by cost, hardest first)")

    def _pos_label(p):
        star = "⭐ " if p["name"] == _today_name else ""
        c = f" · {p['best_cost']:.1f}" if p["best_cost"] is not None else " · n/a"
        return f"{star}{p['name']}{c}"

    _tabs = st.tabs([_pos_label(p) for p in _positions])
    for _tab, p in zip(_tabs, _positions):
        with _tab:
            st.caption(POSITION_DESC.get(p["name"], ""))
            octs = p["octaves"]
            if not octs:
                st.warning("this cell's range does not fit this position.")
                continue
            # Every octave this cell can be played in, cheapest first + its cost.
            st.markdown("**Octaves available here** (cheapest first):")
            for o in octs:
                extra = f"  _({o['note']})_" if o["note"] else ""
                st.write(f"- {o['register']} — **cost {o['cost']:.2f}**{extra}")
            _opts = [f"{o['register']}  ·  cost {o['cost']:.2f}" for o in octs]
            _sel = st.selectbox("Show octave", _opts, key=f"oct_{p['name']}")
            chosen = octs[_opts.index(_sel)]
            if chosen["note"]:
                st.info(chosen["note"])
            components.html(render_html(chosen["result"], tempo=160), height=340,
                            scrolling=True)
            with st.expander("Per-note detail"):
                st.code(format_note_table(chosen["result"].best.placed), language="text")
except KeyError:
    st.info("Fingering unavailable for this cell (not found in the sampling table).")
except Exception as e:  # noqa: BLE001 — never break the quiz on a fingering hiccup
    st.warning(f"Could not compute fingering: {e}")

# Exercise 1
st.subheader("", divider="red")
st.session_state.starting_note = st.selectbox(
    "Select a pivot note to practice",
    list(
        set(list(df_cells["Start Note"].unique()) + list(df_cells["End Note"].unique()))
    ),
    index=list(
        set(list(df_cells["Start Note"].unique()) + list(df_cells["End Note"].unique()))
    ).index(
        st.session_state.get(
            "starting_note",
            list(
                set(
                    list(df_cells["Start Note"].unique())
                    + list(df_cells["End Note"].unique())
                )
            ),
        )
    ),
)
ending_cells = df_cells.loc[df_cells["End Note"] == st.session_state.starting_note]
starting_cells = df_cells.loc[df_cells["Start Note"] == st.session_state.starting_note]

with st.expander("Show Cells"):
    c1, c2 = st.columns((0.5, 0.5))
    with c1:
        for n in ending_cells.index:
            st.write(f"##### {n}")
            st.write(join_notes(df_cells.loc[n, "Notes"]), df_cells.loc[n, "Movement"])
    with c2:
        for n in starting_cells.index:
            st.write(f"##### {n}")
            st.write(join_notes(df_cells.loc[n, "Notes"]), df_cells.loc[n, "Movement"])

st.write(
    "## Exercise 1 : Cells starting on {}".format(st.session_state.starting_note),
)
ex_1_names = st.multiselect(
    "Cells starting on {}".format(st.session_state.starting_note),
    options=df_cells.index,
)
ex_1_cells = {name: df_cells.loc[name, "Notes"] for name in ex_1_names}
if st.button("Verify answer 1"):
    correct_names = starting_cells.index
    correct_cells = {name: df_cells.loc[name, "Notes"] for name in correct_names}
    extras, missing = validate_results(ex_1_cells, correct_cells)
    if (len(extras) > 0) or (len(missing) > 0):
        if len(extras) > 0:
            st.error("{} are not part of the correct answer !!".format(extras))
        if len(missing) > 0:
            st.error("{} are missing !!".format(len(missing)))
    else:
        st.success("Correct !!!", icon="✅")
        for name, cell in correct_cells.items():
            st.write("**" + name + "** ------ " + join_notes(cell))
    with st.expander("see solutions 2 "):
        for name, cell in correct_cells.items():
            st.write("**" + name + "** ------ " + join_notes(cell))
st.write("---")

# Exercise 2
st.write("## Exercise 2 : Cells ending on {}".format(st.session_state.starting_note))
ex_2_names = st.multiselect(
    "Cells ending on {}".format(st.session_state.starting_note),
    options=df_cells.index,
)
ex_2_cells = {name: df_cells.loc[name, "Notes"] for name in ex_2_names}
if st.button("Verify answer 2"):
    correct_names = ending_cells[st.session_state.starting_note]
    correct_cells = {name: df_cells.loc[name, "Notes"] for name in correct_names}
    extras, missing = validate_results(ex_2_cells, correct_cells)
    if (len(extras) > 0) or (len(missing) > 0):
        if len(extras) > 0:
            st.error("{} are not part of the correct answer !!".format(extras))
        if len(missing) > 0:
            st.error("{} are missing !!".format(len(missing)))

    else:
        st.success("Correct !!!", icon="✅")
        for name, cell in correct_cells.items():
            st.write("**" + name + "** ------ " + join_notes(cell))
    with st.expander("see solutions 1 "):
        for name, cell in correct_cells.items():
            st.write("**" + name + "** ------ " + join_notes(cell))


st.write("---")
