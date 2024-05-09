import streamlit as st

import re


@st.cache_data
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
            # Recombine into the full note string
            translated_note = f"{prefix}{new_number}{suffix}"
            translated_cells.append(translated_note)
        else:
            # Handle the case where the note might not contain a number
            translated_cells.append("0")
    if simple_string:
        translated_cells = translated_cells[0]
    return translated_cells


@st.cache_data
def translate_sus4_to_other_mode(df_cells, mode):
    new_df = df_cells.copy()
    new_df["Notes"] = df_cells["Notes"].apply(translate_note_cells, mode=mode)
    new_df["Start Note"] = df_cells["Start Note"].apply(translate_note_cells, mode=mode)
    new_df["End Note"] = df_cells["End Note"].apply(translate_note_cells, mode=mode)
    return new_df


loc_to_dom_mapping = {
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
    "#6": "3",
}

dom_to_min_mapping = {
    "1": "5",
    "4": "1",
    "7": "4",
    "3": "#7",
    "9": "6",
    "5": "9",
    "6": "maj3",
    "#9": "7",
    "b9": "b6",
    "b6": "3",
    "maj7": "b5",
    "#11": "b9",
}


@st.cache_data
def map_loc_to_dom_notes(note_cells):
    simple_string = False
    if isinstance(note_cells, str):
        note_cells = [note_cells]
        simple_string = True
    translated_cells = []
    for note in note_cells:
        new_note = loc_to_dom_mapping[note]
        # Recombine into the full note string
        translated_cells.append(new_note)
    if simple_string:
        translated_cells = translated_cells[0]
    return translated_cells


@st.cache_data
def translate_loc_to_dominant(df_cells):
    new_df = df_cells.copy()
    new_df["Notes"] = df_cells["Notes"].apply(map_loc_to_dom_notes)
    new_df["Start Note"] = df_cells["Start Note"].apply(map_loc_to_dom_notes)
    new_df["End Note"] = df_cells["End Note"].apply(map_loc_to_dom_notes)
    return new_df


@st.cache_data
def map_dom_to_minor(note_cells):
    simple_string = False
    if isinstance(note_cells, str):
        note_cells = [note_cells]
        simple_string = True
    translated_cells = []
    for note in note_cells:
        new_note = dom_to_min_mapping[note]
        # Recombine into the full note string
        translated_cells.append(new_note)
    if simple_string:
        translated_cells = translated_cells[0]
    return translated_cells


@st.cache_data
def translate_dom_to_minor(df_cells):
    new_df = df_cells.copy()
    new_df["Notes"] = df_cells["Notes"].apply(map_dom_to_minor)
    new_df["Start Note"] = df_cells["Start Note"].apply(map_dom_to_minor)
    new_df["End Note"] = df_cells["End Note"].apply(map_dom_to_minor)
    return new_df
