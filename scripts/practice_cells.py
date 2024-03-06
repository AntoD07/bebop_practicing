import streamlit as st
from scripts.cells.major7 import (
    maj_essential_starting_cells,
    maj_essential_ending_cells,
)
from scripts.cells.sus4 import (
    dominant_essential_starting_cells,
    dominant_essential_ending_cells,
)

import random


# All available cells
@st.cache_data
def get_all_cells(start_cells, ending_cells):
    all_cell_names = []
    all_cells = {}
    for dic in [start_cells, ending_cells]:
        # iterate over all starting/ending points
        for v in dic.values():
            all_cell_names += list(v.keys())
            # iterate over all cells starting from (ending at) a given note
            for key in v.keys():
                all_cells[key] = v[key]
    return list(set(all_cells)), all_cells


def load_cells(chord, include_bonus=False):
    if chord == "Maj7":
        starting_cells = maj_essential_starting_cells
        ending_cells = maj_essential_ending_cells
    elif chord == "7sus4":
        starting_cells = dominant_essential_starting_cells
        ending_cells = dominant_essential_ending_cells
    else:
        raise ValueError("Unkown chord type")

    st.session_state.name = random.choice(
        get_all_cells(starting_cells, ending_cells)[0]
    )
    st.session_state.starting_note = st.session_state.get(
        "starting_note", random.choice(list(starting_cells.keys()))
    )
    st.session_state.ending_note = random.choice(list(ending_cells.keys()))

    return starting_cells, ending_cells


@st.cache_data
def validate_results(answer, gt):
    # Keys in a but not in b
    extras = set(answer.keys()) - set(gt.keys())
    missing = set(gt.keys()) - set(answer.keys())
    return extras, missing


@st.cache_data
def names_to_notes(all_cells, names):
    return {name: all_cells[name] for name in names}


@st.cache_data
def join_notes(cell):
    return "-".join(cell)


@st.cache_data
def cell_from_string(string):
    return "-".join(string.split(" "))


@st.cache_data
def find_combinations_on_pivot(pivot, starting_cells, ending_cells):
    """
    Finds all possible combinations of two cells where the first one ends and the second one starts on the given pivot note.

    Parameters:
    - pivot: The pivot note as an integer.
    - starting_cells: Dictionary of starting cells organized by starting note.
    - ending_cells: Dictionary of ending cells organized by ending note.

    Returns:
    - combinations: A list of tuples, each containing two cell names representing a valid combination.
    """
    combinations = []

    # Find cells that end on the pivot note
    ending_cells_for_pivot = []
    if pivot in ending_cells:
        for cell_name, notes in ending_cells[pivot].items():
            ending_cells_for_pivot.append(
                "{} \n {}".format(cell_name, join_notes(notes))
            )

    # Find cells that start on the pivot note
    starting_cells_for_pivot = []
    if pivot in starting_cells:
        for cell_name, notes in starting_cells[pivot].items():
            starting_cells_for_pivot.append(
                "{} \n {}".format(cell_name, join_notes(notes))
            )

    # Create combinations of ending and starting cells on the pivot note
    for ending_cell in ending_cells_for_pivot:
        for starting_cell in starting_cells_for_pivot:
            combinations.append((ending_cell, starting_cell))

    return combinations
