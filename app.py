import streamlit as st
import random

from scripts.practice_cells import (
    get_all_cells,
    load_cells,
    validate_results,
    names_to_notes,
)

names, all_cells = get_all_cells()

st.title("Test")
chord = st.selectbox("Select chord to practice", ["Maj7"])
starting_cells, ending_cells = load_cells(chord)
notes = list(set(list(starting_cells.keys()) + list(ending_cells.keys())))
available_notes = st.multiselect(
    "Select possible notes picked for training", notes, default=notes
)

if st.button("Randomize again"):
    st.session_state.starting_note = random.choice(list(starting_cells.keys()))
    st.session_state.ending_note = random.choice(list(ending_cells.keys()))

starting_note = st.session_state.get("starting_note", 1)
ending_note = st.session_state.get("ending_note", 5)

if st.checkbox("Display notes for help", value=True):
    display_notes = True
    to_choose_from = all_cells
else:
    to_choose_from = names


# Exercise 1
st.write("## Exercise 1 : Cells ending on {}".format(starting_note))
ex_1_names = st.multiselect(
    "Cells ending on {}".format(starting_note), options=all_cells
)
ex_1_cells = names_to_notes(all_cells, ex_1_names)
if st.button("Submit answer"):
    st.write(ex_1_cells)
    correct_names = ending_cells[starting_note]
    correct_cells = {name: all_cells[name] for name in correct_names}
    extras, missing = validate_results(ex_1_cells, correct_cells)
    if (len(extras) > 0) or (len(missing) > 0):
        if len(extras) > 0:
            st.write("{} are not part of the correct answer !!".format(extras))
        if len(missing) > 0:
            st.write("{} are missing !!".format(missing))
    else:
        st.write("Correct !!!")


# Exercise 2
st.write("## Exercise 2 : Cells starting on {}".format(starting_note))
ex_2_names = st.multiselect(
    "Cells starting on {}".format(starting_note), options=all_cells
)
ex_2_cells = names_to_notes(all_cells, ex_2_names)
if st.button("Submit answer 2"):
    st.write(ex_2_cells)
    correct_names = starting_cells[starting_note]
    correct_cells = {name: all_cells[name] for name in correct_names}
    extras, missing = validate_results(ex_2_cells, correct_cells)
    if (len(extras) > 0) or (len(missing) > 0):
        if len(extras) > 0:
            st.write("{} are not part of the correct answer !!".format(extras))
        if len(missing) > 0:
            st.write("{} are missing !!".format(missing))

    else:
        st.write("Correct !!!")


st.write(
    "## Exercise 3 : Randomized path = {} --> {}".format(
        str(starting_note), str(ending_note)
    )
)
ex_3_names = st.multiselect("Cells", options=all_cells)
ex_3_cells = names_to_notes(all_cells, ex_3_names)
if st.button("Submit answer 3"):
    st.write(ex_3_cells)
    correct_cells = {
        name: all_cells[name]
        for name in all_cells.keys()
        if (all_cells[name][0] == str(starting_note))
        and (all_cells[name][-1] == str(ending_note))
    }
    extras, missing = validate_results(ex_3_cells, correct_cells)
    if (len(extras) > 0) or (len(missing) > 0):
        if len(extras) > 0:
            st.write("{} are not part of the correct answer !!".format(extras))
        if len(missing) > 0:
            st.write("{} are missing !!".format(missing))
    else:
        st.write("Correct !!!")

# Simple interaction
if st.button("Click me"):
    st.write("Welcome to your music practice session!")
    st.write("something else")
