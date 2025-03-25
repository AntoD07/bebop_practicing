import streamlit as st
import random

from scripts.load_cells import (
    get_all_cells,
    create_starting_ending_cells,
    create_cell_frames,
)

from scripts.utils import (
    validate_results,
    names_to_notes,
    join_notes,
    cell_from_string,
)

from scripts.modes.mode_transposition import (
    translate_sus4_to_other_mode,
    translate_loc_to_dominant,
    translate_dom_to_minor,
)

st.title("Bebop practice app")
previous_chord = st.session_state.get("chord")
st.session_state.include_bonus = st.sidebar.checkbox(
    "Whether to include bonus cells", value=st.session_state.get("include_bonus", False)
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


# all_cells, starting_cells, ending_cells = get_all_cells(
#     st.session_state.chord, st.session_state.include_bonus
# )
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
