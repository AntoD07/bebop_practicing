import streamlit as st

import re
import ast


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


def translate_sus4_to_other_mode(df_cells, mode):
    new_df = df_cells.copy()

    # Helper function to convert string representations of lists into actual list objects
    def convert_string_to_list(string):
        try:
            return ast.literal_eval(string)  # Safely evaluate the string to a list
        except ValueError:
            return string  # Return the string itself if conversion is not possible

    # Convert string representations to lists
    new_df["Notes"] = new_df["Notes"].apply(convert_string_to_list)

    # Apply the mode-specific translation function to each of the list-converted columns
    new_df["Notes"] = new_df["Notes"].apply(translate_note_cells, mode=mode)
    new_df["Start Note"] = new_df["Start Note"].apply(translate_note_cells, mode=mode)
    new_df["End Note"] = new_df["End Note"].apply(translate_note_cells, mode=mode)

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
    "maj7": "#11",
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

dom_to_maj_mapping = {
    "1": "5",
    "4": "1",
    "7": "4",
    "3": "7",
    "9": "6",
    "2": "6",
    "5": "9",
    "6": "3",
    "#9": "b7",
    "#9(higher)": "b7(higher)",
    "b9": "b6",
    "b9(higher)": "b6(higher)",
    "#5": "b6",
    "b6": "min3",
    "maj7": "b5",
    "#11": "b9",
    "b6(lower)": "min3(lower)",
}


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


def translate_loc_to_dominant(df_cells):
    # Define a helper function to safely convert string representations to lists
    def convert_string_to_list(string):
        try:
            # Attempt to evaluate the string as a list
            return ast.literal_eval(string)
        except ValueError:
            # Return the input as-is if conversion fails
            return string

    # Convert string representations to lists before applying the mapping function
    df_cells["Notes"] = df_cells["Notes"].apply(convert_string_to_list)

    # Now apply the domain-specific mapping function
    df_cells["Notes"] = df_cells["Notes"].apply(map_loc_to_dom_notes)
    df_cells["Start Note"] = df_cells["Start Note"].apply(map_loc_to_dom_notes)
    df_cells["End Note"] = df_cells["End Note"].apply(map_loc_to_dom_notes)

    return df_cells


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


def translate_dom_to_minor(df_cells):
    new_df = df_cells.copy()

    # Define a helper function to convert string representation of a list to a list
    def convert_string_to_list(string):
        try:
            return ast.literal_eval(string)
        except ValueError:
            # Handle the case where the string cannot be converted to a list
            return string

    # Apply the helper function to convert string representations to lists
    new_df["Notes"] = new_df["Notes"].apply(convert_string_to_list)

    # Apply the mapping function after conversion
    new_df["Notes"] = new_df["Notes"].apply(map_dom_to_minor)
    new_df["Start Note"] = new_df["Start Note"].apply(map_dom_to_minor)
    new_df["End Note"] = new_df["End Note"].apply(map_dom_to_minor)

    return new_df


def map_dom_to_major(note_cells):
    simple_string = False
    if isinstance(note_cells, str):
        note_cells = [note_cells]
        simple_string = True
    translated_cells = []
    for note in note_cells:
        new_note = dom_to_maj_mapping[note]
        # Recombine into the full note string
        translated_cells.append(new_note)
    if simple_string:
        translated_cells = translated_cells[0]
    return translated_cells


def translate_dom_to_major(df_cells):
    new_df = df_cells.copy()

    # Define a helper function to convert string representation of a list to a list
    def convert_string_to_list(string):
        try:
            return ast.literal_eval(string)
        except ValueError:
            # Handle the case where the string cannot be converted to a list
            return string

    # Apply the helper function to convert string representations to lists
    new_df["Notes"] = new_df["Notes"].apply(convert_string_to_list)

    # Apply the mapping function after conversion
    new_df["Notes"] = new_df["Notes"].apply(map_dom_to_major)
    new_df["Start Note"] = new_df["Start Note"].astype(str).apply(map_dom_to_major)
    new_df["End Note"] = new_df["End Note"].astype(str).apply(map_dom_to_major)

    return new_df


def change_note_representation(
    df_cells, mode, loc_to_dom, dom_to_minor, sus_to_loc_dorian
):
    if (mode in ["Dorian", "Locrian"]) and sus_to_loc_dorian:
        df_cells = translate_sus4_to_other_mode(df_cells, mode)
    if (mode in ["Locrian"]) and loc_to_dom:
        df_cells = translate_loc_to_dominant(df_cells)
    if (mode in ["Locrian", "MinorResolutions"]) and dom_to_minor:
        df_cells = translate_dom_to_minor(df_cells)
    if (mode in ["MajorResolutions"]) and dom_to_minor:
        df_cells = translate_dom_to_major(df_cells)
    return df_cells
