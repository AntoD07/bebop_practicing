import streamlit as st

# Weights

myxolidian_weights = {"1": 4, "3": 3, "5": 2, "7": 1}
dorian_weights = {"5": 4, "7": 3, "9": 2, "11": 1, "6": 1, "3": 1}
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
            score["Dorian"] = round(dorian_score / 8, 1)
            score["Locrian"] = round(locrian_score / 5.0, 1)
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


import re


def translate_note_cells(note_cells, mode):
    """
    Translates note cells by applying an arithmetic shift and taking modulo 8 to the numeric part of each note,
    while retaining any prefixes or suffixes.

    Parameters:
    - note_cells: List of notes as strings, possibly containing prefixes or suffixes.
    - shift: Integer, the arithmetic shift for the translation, reflecting the mode change.

    Returns:
    - List of translated notes.
    """
    if mode == "Dorian":
        shift = 3
    elif mode == "Locrian":
        shift = 5
    simple_string = False
    if isinstance(note_cells, str):
        note_cells = [note_cells]
        simple_string = True
    translated_cells = []
    for note in note_cells:
        # st.write(note)
        # Extract the numeric part and any prefixes/suffixes
        match = re.match(r"([a-zA-Z#b]*)(\d+)([^\d]*)", note)
        if match:
            prefix, number, suffix = match.groups()
            # st.write("old number ", number)
            # Convert the number to an integer, apply the shift and modulo 8
            new_number = (int(number) - 1 + shift) % 7 + 1
            # st.write("new number ", new_number)
            if new_number == 2:
                new_number = 9
            if (new_number == 4) and bool(prefix):
                new_number = 11
            # new_number = 8 if new_number == 0 else new_number  # Adjust for musical notation (no '0' note)
            # Recombine into the full note string
            translated_note = f"{prefix}{new_number}{suffix}"
            translated_cells.append(translated_note)
        else:
            # Handle the case where the note might not contain a number
            translated_cells.append("0")
    if simple_string:
        translated_cells = translated_cells[0]
    return translated_cells


def translate_sus4_to_other_mode(df_cells, mode):
    new_df = df_cells.copy()
    new_df["Notes"] = df_cells["Notes"].apply(translate_note_cells, mode=mode)
    new_df["Start Note"] = df_cells["Start Note"].apply(translate_note_cells, mode=mode)
    new_df["End Note"] = df_cells["End Note"].apply(translate_note_cells, mode=mode)
    return new_df


note_mapping = {
    "1": "5",
    "4": "1",
    "7": "4",
    "3": "7",
    "9": "b6",
    "5": "b9",
    "6": "#9",
    "#9": "6",
    "maj5": "9",
    "#3": "maj7",
    "#7": "#11",
}


def map_loc_to_dom_notes(note_cells):
    note_mapping = {
        "1": "5",
        "4": "1",
        "7": "4",
        "3": "7",
        "9": "b6",
        "5": "b9",
        "6": "#9",
        "#9": "6",
        "maj5": "9",
        "#3": "maj7",
        "#7": "#11",
    }
    simple_string = False
    if isinstance(note_cells, str):
        note_cells = [note_cells]
        simple_string = True
    translated_cells = []
    for note in note_cells:
        new_note = note_mapping[note]
        # Recombine into the full note string
        translated_cells.append(new_note)
    if simple_string:
        translated_cells = translated_cells[0]
    return translated_cells


def translate_loc_to_dominant(df_cells):
    new_df = df_cells.copy()
    new_df["Notes"] = df_cells["Notes"].apply(map_loc_to_dom_notes)
    new_df["Start Note"] = df_cells["Start Note"].apply(map_loc_to_dom_notes)
    new_df["End Note"] = df_cells["End Note"].apply(map_loc_to_dom_notes)
    return new_df
