import streamlit as st
import random

from scripts.practice_cells import (
    get_all_cells,
    create_starting_ending_cells,
    validate_results,
    names_to_notes,
    join_notes,
    cell_from_string,
)


st.title("Bebop practice app")
previous_chord = st.session_state.get("chord")
st.session_state.chord = st.selectbox(
    "Select chord to practice",
    ["Maj7", "7sus4", "Dorian", "Myxolidian", "Locrian"],
    index=1,
)
all_cells = get_all_cells(st.session_state.chord, True)
names = list(all_cells.keys())
starting_cells, ending_cells = create_starting_ending_cells(all_cells)

if st.session_state.chord != previous_chord:
    st.session_state.name = random.choice(list(all_cells.keys()))
    st.session_state.starting_note = random.choice(list(starting_cells.keys()))


if st.button("Randomize again "):
    st.session_state.name = random.choice(list(all_cells.keys()))
    st.session_state.starting_note = random.choice(list(starting_cells.keys()))
    st.session_state.ending_note = random.choice(list(ending_cells.keys()))

st.subheader("", divider="red")

st.session_state.name = st.selectbox(
    "Refresh memory on any cell",
    all_cells.keys(),
    index=list(all_cells.keys()).index(
        st.session_state.get("name", random.choice(list(all_cells.keys())))
    ),
)
input = st.text_input("Cell notes (w.r.t. to the type of chord)")
c = cell_from_string(input)
answer = join_notes(all_cells[st.session_state.name])
st.write(c == answer)
with st.expander("See solution"):
    st.write(join_notes(all_cells[st.session_state.name]))

# Exercise 1
st.subheader("", divider="red")
st.session_state.starting_note = st.selectbox(
    "Select a pivot note to practice",
    starting_cells.keys(),
    index=list(starting_cells.keys()).index(
        st.session_state.get(
            "starting_note", random.choice(list(starting_cells.keys()))
        )
    ),
)
with st.expander("Show Cells"):
    c1, c2 = st.columns((0.5, 0.5))
    for n, notes in ending_cells[st.session_state.starting_note].items():
        c1.write(f"##### {n}")
        c1.write(join_notes(notes))
    for n, notes in starting_cells[st.session_state.starting_note].items():
        c2.write(f"##### {n}")
        c2.write(join_notes(notes))

st.write(
    "## Exercise 1 : Cells starting on {}".format(st.session_state.starting_note),
)
ex_2_names = st.multiselect(
    "Cells starting on {}".format(st.session_state.starting_note), options=all_cells
)
ex_2_cells = names_to_notes(all_cells, ex_2_names)
if st.button("Verify answer 2"):
    correct_names = starting_cells[st.session_state.starting_note]
    correct_cells = {name: all_cells[name] for name in correct_names}
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
    with st.expander("see solutions 2 "):
        for name, cell in correct_cells.items():
            st.write("**" + name + "** ------ " + join_notes(cell))
st.write("---")
# Exercise 2
st.write("## Exercise 2 : Cells ending on {}".format(st.session_state.starting_note))
ex_1_names = st.multiselect(
    "Cells ending on {}".format(st.session_state.starting_note), options=all_cells
)
ex_1_cells = names_to_notes(all_cells, ex_1_names)
if st.button("Verify answer 1"):
    correct_names = ending_cells[st.session_state.starting_note]
    correct_cells = {name: all_cells[name] for name in correct_names}
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
    with st.expander("see solutions 1 "):
        for name, cell in correct_cells.items():
            st.write("**" + name + "** ------ " + join_notes(cell))


st.write("---")

# Exercise 3

st.write("## Exercise 3 : Randomized path")
c1, c2 = st.columns((0.5, 0.5))
if c2.button("Randomize again ending note"):
    st.session_state.ending_note = random.choice(list(ending_cells.keys()))
st.session_state.ending_note = c1.selectbox(
    "Select a ending note to practice",
    ending_cells.keys(),
    index=list(ending_cells.keys()).index(
        st.session_state.get("ending_note", random.choice(list(ending_cells.keys())))
    ),
)
ex_3_names = st.multiselect(
    "Cells {} --> {}".format(
        str(st.session_state.starting_note), str(st.session_state.ending_note)
    ),
    options=all_cells,
)
ex_3_cells = names_to_notes(all_cells, ex_3_names)
if st.button("Verify answer 3"):
    correct_cells = {
        name: all_cells[name]
        for name in all_cells.keys()
        if (all_cells[name][0] == str(st.session_state.starting_note))
        and (all_cells[name][-1] == str(st.session_state.ending_note))
    }
    extras, missing = validate_results(ex_3_cells, correct_cells)
    if (len(extras) > 0) or (len(missing) > 0):
        if len(extras) > 0:
            st.error("{} are not part of the correct answer !!".format(extras))
        if len(missing) > 0:
            st.error("{} are missing !!".format(len(missing)))

    else:
        st.success("Correct !!!", icon="✅")
        for name, cell in correct_cells.items():
            st.write("**" + name + "** ------ " + join_notes(cell))
    with st.expander("see solutions 3 "):
        for name, cell in correct_cells.items():
            st.write("**" + name + "** ------ " + join_notes(cell))
st.subheader("", divider="red")
st.write("## Creating a beautiful line ")
