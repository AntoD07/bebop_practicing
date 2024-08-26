import streamlit as st
import json


from scripts.database import fetch_data_base
from scripts.modes.mode_transposition import (
    translate_sus4_to_other_mode,
    translate_loc_to_dominant,
    translate_dom_to_minor,
    translate_dom_to_major,
)


from scripts.utils import join_notes


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
    elif chord == "MinorResolutions":
        file = "scripts/cells/minor_resolution.json"
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
    if chord == "Locrian":
        with open("scripts/cells/Locrian.json") as f:
            loc_cells = json.load(f)
        cells.update(loc_cells)
    # if chord in ["Dorian", "Myxolidian", "Locrian"]:
    #    cells = filter_cells_by_mode(cells, chord)
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


def create_cell_frames(
    chord,
    mode_filter,
    permute_notes,
    bonus,
    field="Start Note",
    loc_to_dominant=False,
    dom_to_minor=False,
):
    df_cells = fetch_data_base(
        "{}_sampling.csv".format(chord),
        bonus=bonus,
        # all_cells,
        # majchord=chord == "Maj7",
    )
    df_cells["Start Note"] = df_cells["Start Note"].astype(str)
    df_cells["End Note"] = df_cells["End Note"].astype(str)

    if mode_filter and (chord in ["Dorian", "Locrian", "Myxolidian"]):
        df_cells = df_cells[df_cells["Modes"].apply(lambda x: chord in x)]

    df_cells_tmp_for_pivot_note = df_cells.copy(deep=False)
    if chord in ["Dorian", "Locrian"]:
        if permute_notes:
            df_cells_tmp_for_pivot_note = translate_sus4_to_other_mode(
                df_cells_tmp_for_pivot_note, chord
            )
        if chord in ["Locrian", "Myxolidian"]:
            if chord == loc_to_dominant:
                df_cells_tmp_for_pivot_note_2 = translate_loc_to_dominant(
                    df_cells_tmp_for_pivot_note
                )
            else:
                df_cells_tmp_for_pivot_note_2 = df_cells_tmp_for_pivot_note
            if dom_to_minor:
                df_cells_tmp_for_pivot_note_2 = translate_dom_to_minor(
                    df_cells_tmp_for_pivot_note_2
                )

            chord_tones_mapping = dict(
                zip(
                    df_cells_tmp_for_pivot_note_2[field].unique(),
                    df_cells[field].unique(),
                )
            )
            return (
                df_cells,
                df_cells_tmp_for_pivot_note_2[field].unique(),
                chord_tones_mapping,
            )
    elif chord == "MinorResolutions":
        if dom_to_minor:

            df_cells_tmp_for_pivot_note_2 = translate_dom_to_minor(
                df_cells_tmp_for_pivot_note
            )
        else:
            df_cells_tmp_for_pivot_note_2 = df_cells_tmp_for_pivot_note
        chord_tones_mapping = dict(
            zip(
                df_cells_tmp_for_pivot_note_2[field].unique(),
                df_cells[field].unique(),
            )
        )

        return (
            df_cells,
            df_cells_tmp_for_pivot_note_2[field].unique(),
            chord_tones_mapping,
        )
    elif chord in ["MajorResolutions", "Myxolidian"]:
        if dom_to_minor:
            df_cells_tmp_for_pivot_note_2 = translate_dom_to_major(
                df_cells_tmp_for_pivot_note
            )
        else:
            df_cells_tmp_for_pivot_note_2 = df_cells_tmp_for_pivot_note
        chord_tones_mapping = dict(
            zip(
                df_cells_tmp_for_pivot_note_2[field].unique(),
                df_cells[field].unique(),
            )
        )
        return (
            df_cells,
            df_cells_tmp_for_pivot_note_2[field].unique(),
            chord_tones_mapping,
        )
    #     if loc_to_dominant:
    #         df_cells_tmp_for_pivot_note_2 = translate_loc_to_dominant(
    #             df_cells_tmp_for_pivot_note
    #         )

    # if loc_to_dominant:
    #     chord_tones_mapping = dict(
    #         zip(
    #             df_cells_tmp_for_pivot_note_2[field].unique(),
    #             df_cells[field].unique(),
    #         )
    #     )
    chord_tones_mapping = dict(
        zip(
            df_cells_tmp_for_pivot_note[field].unique(),
            df_cells[field].unique(),
        )
    )
    return df_cells, df_cells_tmp_for_pivot_note[field].unique(), chord_tones_mapping
