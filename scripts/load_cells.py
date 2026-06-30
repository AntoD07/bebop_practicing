from scripts.database import fetch_data_base
from scripts.modes.mode_transposition import (
    translate_sus4_to_other_mode,
    translate_dom_to_minor,
    translate_dom_to_major,
)
from scripts.paths import sampling_file


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
        sampling_file(chord),
        bonus=bonus,
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
    chord_tones_mapping = dict(
        zip(
            df_cells_tmp_for_pivot_note[field].unique(),
            df_cells[field].unique(),
        )
    )
    return df_cells, df_cells_tmp_for_pivot_note[field].unique(), chord_tones_mapping
