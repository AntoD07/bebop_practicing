import streamlit as st
from scripts.cells.major7 import (
    maj_essential_starting_cells,
    maj_essential_ending_cells,
)


# All available cells
@st.cache_data
def get_all_cells(include_bonus=False):
    all_cell_names = []
    all_cells = {}
    for dic in [maj_essential_starting_cells, maj_essential_ending_cells]:
        # iterate over all starting/ending points
        for v in dic.values():
            all_cell_names += list(v.keys())
            # iterate over all cells starting from (ending at) a given note
            for key in v.keys():
                all_cells[key] = v[key]
    return list(set(all_cells)), all_cells


@st.cache_data
def load_cells(chord):
    if chord == "Maj7":
        starting_cells = maj_essential_starting_cells
        ending_cells = maj_essential_ending_cells
    else:
        raise ValueError("Unkown chord type")

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
