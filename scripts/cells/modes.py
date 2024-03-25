import streamlit as st

# Weights

myxolidian_weights = {"1": 4, "3": 3, "5": 2, "7": 1}
dorian_weights = {"5": 4, "7": 3, "9": 2, "11": 1, "6": 2, "3": 2}
locrian_weights = {"3": 4, "5": 3, "7": 2, "9": 1}


@st.cache_data
def compute_scores(cells, majchord=False):
    scores = {}
    for cell_name, notes in cells.items():
        score = {}
        if majchord:
            score["Modes"] = ["Maj7"]
        else:
            myxolidian_score = 0
            dorian_score = 0
            locrian_score = 0

            # Compute the scores based on specified positions
            for index in [0, 2, 4]:
                note = notes[index]
                myxolidian_score += myxolidian_weights.get(note, 0)
                dorian_score += dorian_weights.get(note, 0)
                locrian_score += locrian_weights.get(note, 0)
            # Average score per cell = average score per note * 3
            score["Myxolidian"] = round(myxolidian_score / 7.5, 1)
            score["Dorian"] = round(dorian_score / 7, 1)
            score["Locrian"] = round(locrian_score / 7.5, 1)
            score = dict(sorted(score.items(), key=lambda item: item[1], reverse=True))
            # Determine the mode based on higher score
            modes = ["7sus4"]
            for mode, _score in score.items():
                if _score > 0.5:
                    modes.append(mode)
            score["Modes"] = modes
        scores[cell_name] = score

    return scores


@st.cache_data
def filter_cells_by_mode(cells, target_mode):
    """
    Filters cells based on a given mode and extracts their initial notes.

    Parameters:
    - cells: A dictionary of cells and their notes.
    - target_mode: The mode to filter cells by (e.g., "Myxolidian", "Dorian", "Locrian").

    Returns:
    - A dictionary with cell names as keys and their initial notes as values for cells that predominantly align with the target mode.
    """
    # First, compute the scores and modes for each cell
    scores = compute_scores(cells)

    # Filter cells based on the target mode and extract their initial notes
    filtered_cells = {
        cell_name: cells[cell_name]
        for cell_name, score in scores.items()
        if target_mode in score["Modes"]
    }

    return filtered_cells
