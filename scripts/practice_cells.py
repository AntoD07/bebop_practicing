import streamlit as st
import json
from scripts.cells.modes import filter_cells_by_mode


@st.cache_data
def create_starting_ending_cells(cells):
    starting_cells = {}
    ending_cells = {}

    for cell_name, notes in cells.items():
        start_note = notes[0]
        end_note = notes[-1]

        # Add to starting_cells
        if start_note not in starting_cells:
            starting_cells[start_note] = {}
        starting_cells[start_note][cell_name] = notes

        # Add to ending_cells
        if end_note not in ending_cells:
            ending_cells[end_note] = {}
        ending_cells[end_note][cell_name] = notes
    return starting_cells, ending_cells


def get_all_cells(chord, include_bonus=False):
    if chord == "MajorResolutions":
        file = "scripts/cells/maj_resolution.json"
    elif chord == "Maj7":
        file = "scripts/cells/maj7.json"
    elif chord in ["7sus4", "Dorian", "Myxolidian", "Locrian"]:
        file = "scripts/cells/7sus4.json"
    else:
        raise ValueError("Unkown chord type")
    with open(file) as f:
        dic = json.load(f)
    unordered_cells = dic["essential"]
    if include_bonus:
        unordered_cells.update(dic["bonus"])
    cells = {key: value for key, value in sorted(unordered_cells.items())}
    if chord in ["Dorian", "Myxolidian", "Locrian"]:
        cells = filter_cells_by_mode(cells, chord)
    starting_cells, ending_cells = create_starting_ending_cells(cells)
    if chord == "MajorResolutions":
        with open("scripts/cells/7sus4.json") as f:
            dic = json.load(f)
        unordered_cells = dic["essential"]
        if include_bonus:
            unordered_cells.update(dic["bonus"])
        sus_cells = {key: value for key, value in sorted(unordered_cells.items())}
        _, ending_cells = create_starting_ending_cells(sus_cells)
    return cells, starting_cells, ending_cells


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
    start_names = []
    end_names = []

    # Find cells that end on the pivot note
    ending_cells_for_pivot = []
    if pivot in ending_cells:
        for cell_name, notes in ending_cells[pivot].items():
            ending_cells_for_pivot.append(
                "{} \n {}".format(cell_name, join_notes(notes))
            )
            end_names.append(cell_name)

    # Find cells that start on the pivot note
    starting_cells_for_pivot = []
    if pivot in starting_cells:
        for cell_name, notes in starting_cells[pivot].items():
            starting_cells_for_pivot.append(
                "{} \n {}".format(cell_name, join_notes(notes))
            )
            start_names.append(cell_name)

    # Create combinations of ending and starting cells on the pivot note
    for ending_cell in ending_cells_for_pivot:
        for starting_cell in starting_cells_for_pivot:
            combinations.append((ending_cell, starting_cell))
    names = []
    for name1 in end_names:
        for name2 in start_names:
            names.append((name1, name2))

    return combinations, names
