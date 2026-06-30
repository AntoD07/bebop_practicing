import streamlit as st
from scripts.database import fetch_data_base
from scripts.modes.mode_transposition import (
    translate_sus4_to_other_mode,
    translate_loc_to_dominant,
    translate_dom_to_minor,
)


def create_cell_frames(
    chord,
    mode_filter,
    permute_notes,
    bonus=False,
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

    if mode_filter and (chord in ["Dorian", "Locrian", "Myxolidian"]):
        df_cells = df_cells[df_cells["Modes"].apply(lambda x: chord in x)]

    df_cells_tmp_for_pivot_note = df_cells.copy(deep=False)
    if chord in ["Dorian", "Locrian"]:
        if permute_notes:
            df_cells_tmp_for_pivot_note = translate_sus4_to_other_mode(
                df_cells_tmp_for_pivot_note, chord
            )
        if chord == "Locrian":
            if loc_to_dominant:
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
