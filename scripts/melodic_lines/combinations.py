import streamlit as st

from scripts.utils import join_notes


@st.cache_data
def find_combinations_on_pivot_new(pivot_on, starting_cells, ending_cells):
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
    # ending_cells = df_cells.loc[df_cells["End Note"] == pivot]
    for i, cell in ending_cells.reset_index().iterrows():
        name = cell["Cell Name"]
        notes = cell["Notes"]
        ending_cells_for_pivot.append("{} \n {}".format(name, join_notes(notes)))
        end_names.append(name)
    # Find cells that start on the pivot note
    starting_cells_for_pivot = []
    # starting_cells = df_cells.loc[df_cells["Start Note"] == pivot]
    for i, cell in starting_cells.reset_index().iterrows():
        name = cell["Cell Name"]
        notes = cell["Notes"]
        starting_cells_for_pivot.append("{} \n {}".format(name, join_notes(notes)))
        start_names.append(name)

    # Create combinations of ending and starting cells on the pivot note
    for ending_cell in ending_cells_for_pivot:
        for starting_cell in starting_cells_for_pivot:
            combinations.append((ending_cell, starting_cell))
    names = []
    for name1 in end_names:
        for name2 in start_names:
            names.append((name1, name2))

    return combinations, names
