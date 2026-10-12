import streamlit as st
import ast
import random

from scripts.load_cells import create_cell_frames
from scripts.modes.mode_transposition import (
    change_note_representation,
    dom_to_dorian_mapping,
)
from scripts.fingering.cell_bridge import chord_symbol_for_mode, is_single_chord


# "Minor" is the old "Dorian" vocabulary (ii-relative melodic-minor cells, #7
# included); "Dorian" is its #7-free subset. "Dorian x Myxolidian" chains
# Dorian cells into Myxolidian cells — the Myxolidian (V-relative) degrees are
# translated to the ii-relative representation so the pivots line up (see
# ``dom_to_dorian_mapping``); the translation is intrinsic to the line type.
MYXO_TO_DORIAN_LINE_TYPE = "Dorian x Myxolidian"

line_structure_dic = {
    "Maj7": ["Maj7", "Maj7", "Maj7", "Maj7"],
    "7sus4 Infinity Loop": ["Myxolidian", "Myxolidian", "Myxolidian", "Myxolidian"],
    "Minor": ["Minor", "Minor", "Minor", "Minor"],
    "Dorian": ["Dorian", "Dorian", "Dorian", "Dorian"],
    "Myxolidian": ["Myxolidian", "Myxolidian", "Myxolidian", "Myxolidian"],
    "Short Maj 2-5-1": ["Myxolidian", "MajorResolutions"],
    "Long Maj 2-5-1": ["Myxolidian", "Myxolidian", "Myxolidian", "MajorResolutions"],
    "Long Maj 2-5-1 with Maj7 ending": [
        "7sus4",
        "7sus4",
        "7sus4",
        "MajorResolutions",
        "Maj7",
        "Maj7",
    ],
    "Short Minor 2-5-1": ["Locrian", "MinorResolutions"],
    "Long Minor 2-5-1": ["Locrian", "Locrian", "Locrian", "MinorResolutions"],
    "Long Minor with double resolution": [
        "Locrian",
        "Locrian",
        "MinorResolutions",
        "MinorResolutions",
    ],
    "Long Minor 2-5-1 with Minor ending": [
        "Locrian",
        "Locrian",
        "Locrian",
        "MinorResolutions",
        "Minor",
        "Minor",
    ],
    "Double resolution": ["Locrian", "Locrian", "MinorResolutions", "MinorResolutions"],
    "Minor and Dominant 2-cells alternated": [
        "Minor",
        "Minor",
        "Locrian",
        "MinorResolutions",
        "Minor",
        "Minor",
        "Locrian",
        "MinorResolutions",
        "Minor",
        "Minor",
        "Locrian",
        "MinorResolutions",
    ],
    "Minor x Dominant": [
        "Minor",
        "Minor",
        "MinorResolutions",
        "MinorResolutions",
        "Minor",
        "Minor",
        "MinorResolutions",
        "MinorResolutions",
        "Minor",
        "Minor",
        "MinorResolutions",
        "MinorResolutions",
    ],
}


CHORD_TONES = ["1", "3", "5", "7"]


def combo_chord_tone_connecting_notes(mode_list):
    """Allowed pivot notes per cell for the Dorian x Myxolidian combo.

    A pivot is the first note of the cell it enters, so it must be a chord
    tone of THAT cell's chord. Myxolidian cells are spelled ii-relative in the
    combo, so the V7 chord tones 1-3-5-7 appear as 4-6-1-3.
    """
    myxo = [dom_to_dorian_mapping[d] for d in CHORD_TONES]
    return [list(myxo) if m == "Myxolidian" else list(CHORD_TONES)
            for m in mode_list]


def combo_mapping_info():
    """User-facing note explaining the Myxolidian -> Dorian (ii) re-spelling."""
    pairs = ", ".join(f"{d}→{dom_to_dorian_mapping[d]}"
                      for d in ["1", "9", "3", "4", "5", "6", "7", "#11", "b9"])
    return (
        "**Mapping applied:** Myxolidian cells are re-spelled from the ii "
        "(Dorian) root, so both chords share one note representation and the "
        f"pivots line up. V7 degree → ii degree: {pairs}. "
        "Myxolidian notes shown below (and the start/end/connecting-note "
        "pickers) use this ii spelling."
    )


def harmony_caption(key, modes):
    """How today's key maps onto the line's chords (shared by pages 2-3)."""
    modes = list(modes)
    single = is_single_chord(modes)
    first = chord_symbol_for_mode(key, modes[0], single)
    if single:
        return (f"Harmony: one chord, **{first}** — today's key ({key}) is its root.")
    return (f"Harmony: today's key **{key}** is read as the I of a ii-V-I — the "
            f"line starts on **{first}**; later chords follow from the pivots.")


def combo_chord_tones_info():
    myxo = ", ".join(dom_to_dorian_mapping[d] for d in CHORD_TONES)
    return (
        "**Chord-tone pivots:** a pivot is the first note of the cell it enters, "
        "so it must be a chord tone of THAT cell's chord. Entering a Dorian cell: "
        f"{', '.join(CHORD_TONES)} (ii-7 chord tones). Entering a Myxolidian cell: "
        f"{myxo} (the V7's 1-3-5-7, in ii spelling)."
    )


def _allowed_starts(connecting_notes, k):
    """Allowed start notes of cell ``k``, or None for no constraint.

    ``k == 0`` is the line's FIRST note: pages fill ``connecting_notes[0]``
    only when it should be constrained (chord tones), else leave it empty.
    """
    if not connecting_notes or k < 0 or k >= len(connecting_notes):
        return None
    allowed = {str(a) for a in (connecting_notes[k] or []) if a is not None}
    return allowed or None


def line_structure_mapping(type, length=None, n_dorian=1, n_myxo=1):
    if type == MYXO_TO_DORIAN_LINE_TYPE:
        return ["Dorian"] * int(n_dorian) + ["Myxolidian"] * int(n_myxo)
    if type not in [
        "Major x Dominant",
        "Minor",
        "Dorian",
        "Myxolidian",
        "Maj7",
        "Locrian",
    ]:
        return line_structure_dic[type]
    elif type in ("Minor", "Dorian", "Maj7", "Myxolidian", "Locrian"):
        return [type] * length
    elif type == "Major x Dominant":
        return [random.choice(["Maj7", "MajorResolutions"]) for _ in range(length)]


def sample_line_from_path_with_connecting_note(
    line_type,
    include_bonus,
    mode_filter,
    loc_to_dom,
    dom_to_minor,
    sus_to_loc_dorian,
    length,
    movement=None,
    starting_note=None,
    ending_note=None,
    connecting_notes=None,
    n_dorian=1,
    n_myxo=1,
):
    """
    Samples a sequence of cells that connect to each other and include a required connecting note,
    favoring less frequently sampled cells.

    Parameters:
    - df: The DataFrame containing cell data.
    - mode: The mode to filter cells by.
    - num_cells: The number of cells to be connected in the melodic line.
    - required_connecting_note: The required note that must be present as a connecting note among the sampled cells.

    Returns:
    - A list of cell names representing the sampled melodic line, or a message if the criteria cannot be met.
    """

    success = False
    count = 0
    # Myxolidian cells in the Dorian->Myxolidian combo are ALWAYS re-spelled in
    # the ii-relative (Dorian) representation — that is what makes the two
    # vocabularies pivot-compatible.
    myxo_to_dorian = line_type == MYXO_TO_DORIAN_LINE_TYPE

    # Start by the ending cell to take into account the pivot note
    while not success and count < 2000:
        try:
            melodic_line = []
            note_representations = []
            mode_list = line_structure_mapping(
                line_type, length=length, n_dorian=n_dorian, n_myxo=n_myxo
            )
            df_cells, mapped_notes, mapping = create_cell_frames(
                mode_list[-1],
                mode_filter,
                sus_to_loc_dorian,
                include_bonus,
                "Start Note",
                loc_to_dom,
                dom_to_minor,
            )
            df_cells = df_cells.reset_index()
            df_cells = change_note_representation(
                df_cells, mode_list[-1], loc_to_dom, dom_to_minor, sus_to_loc_dorian,
                myxo_to_dorian=myxo_to_dorian,
            )
            if movement is not None:
                if movement in ["A and N", "D and N"]:
                    filtered_df = df_cells[
                        df_cells["Movement"].astype(str).isin(["N", movement[0]])
                    ]
                else:
                    filtered_df = df_cells[
                        df_cells["Movement"].astype(str).isin([movement])
                    ]
                if filtered_df.empty:
                    # st.write("No cells match the movement criteria.")
                    return None
            else:
                filtered_df = df_cells.reset_index(drop=True)
                # st.write("DataFrame after filtering by movement:", df_cells)
            if ending_note not in ["None", None]:
                filtered_df = filtered_df[filtered_df["End Note"] == ending_note]
            if filtered_df.empty:
                st.write("No cells match the end note criteria.")
                return None
            # The last cell's first note is a pivot too (when the line has >1
            # cell): it must be one of that cell's allowed connecting notes.
            allowed = _allowed_starts(connecting_notes, len(mode_list) - 1)
            if allowed:
                filtered_df = filtered_df[
                    filtered_df["Start Note"].astype(str).isin(allowed)
                ]
                if filtered_df.empty:
                    return None
            # st.write(filtered_df)
            final_cell = filtered_df.sample(
                weights=1 / (filtered_df.index + 1), n=1
            ).iloc[0]
            # final_cell = filtered_df.sample(n=1).iloc[0]
            melodic_line.append(final_cell["Cell Name"])
            note_representations.append(str(final_cell["Notes"]))

            # st.write("Last cell df", df_cells)
            # st.write("Last cell sampled", melodic_line)
            # st.write("Last cell notes", note_representations)
            # Construct the line backward from the second last cell to the first
            for i, mode in enumerate(mode_list[:-1][::-1]):
                # st.write(mode)
                df_cells, mapped_notes, mapping = create_cell_frames(
                    mode,
                    mode_filter,
                    sus_to_loc_dorian,
                    include_bonus,
                    "Start Note",
                    loc_to_dom,
                    dom_to_minor,
                )

                df_cells = df_cells.reset_index()
                if movement is not None:
                    if movement in ["A and N", "D and N"]:
                        df_cells = df_cells.loc[
                            df_cells["Movement"].isin(["N", movement[0]])
                        ]
                    else:
                        df_cells = df_cells.loc[df_cells["Movement"].isin([movement])]

                # st.write(df_cells)
                df_cells = change_note_representation(
                    df_cells, mode, loc_to_dom, dom_to_minor, sus_to_loc_dorian,
                    myxo_to_dorian=myxo_to_dorian,
                )
                # Pivot: this cell must END on the note the (already sampled)
                # next cell STARTS on. Parse the actual first degree — degrees
                # can be multi-character ("#7", "b9", "11").
                next_first = str(ast.literal_eval(note_representations[-1])[0]).strip()
                df_cells = df_cells[
                    df_cells["End Note"].astype(str) == next_first
                ]
                if None in connecting_notes:
                    connecting_notes_reversed = connecting_notes[:-1][::-1]
                    # st.write(i)
                    # st.write(mode)
                    # st.write(connecting_notes_reversed[i])
                    # st.write(connecting_notes_reversed[i - 1])

                    df_cells = df_cells[
                        (df_cells["Start Note"].isin(connecting_notes_reversed[i]))
                        & (df_cells["End Note"].isin(connecting_notes_reversed[i - 1]))
                    ]
                allowed = _allowed_starts(connecting_notes, len(mode_list) - 2 - i)
                if allowed:
                    df_cells = df_cells[df_cells["Start Note"].astype(str).isin(allowed)]
                if i == len(mode_list) - 2:
                    # st.write("Last cells options", df_cells)
                    if starting_note not in ["None", None]:
                        #    st.write(starting_note)
                        df_cells = df_cells[df_cells["Start Note"] == starting_note]
                    else:
                        # No explicit first note: the line's first note must be
                        # one of connecting_notes[0] (chord tones when ticked).
                        allowed0 = _allowed_starts(connecting_notes, 0)
                        if allowed0:
                            df_cells = df_cells[
                                df_cells["Start Note"].astype(str).isin(allowed0)]
                    if df_cells.empty:
                        # st.write(
                        #     "No cells match the start note, end note, connecting notes criteria."
                        # )
                        raise ValueError

                sampled_cell = df_cells.sample(n=1).iloc[0]
                # sampled_cell = df_cells.sample(
                #     weights=1 / (df_cells.index + 1), n=1
                # ).iloc[0]
                melodic_line.append(sampled_cell["Cell Name"])
                note_representations.append(str(sampled_cell["Notes"]))

                # st.write("Sampled cell", sampled_cell["Cell Name"])
                # st.write("Last cell sampled", melodic_line)
                # st.write("Last cell notes", note_representations)

            success = True
        except ValueError:
            # st.write("Sampling melodic line failed, retrying")
            success = False
            count += 1
    if not success:
        return None
    return melodic_line[::-1], note_representations[::-1], mode_list
