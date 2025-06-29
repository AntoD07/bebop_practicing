import streamlit as st
import pandas as pd
import random
import numpy as np

from scripts.load_cells import create_cell_frames
from scripts.modes.mode_transposition import (
    translate_dom_to_minor,
    translate_loc_to_dominant,
    translate_sus4_to_other_mode,
    change_note_representation,
)


line_structure_dic = {
    "Maj7": ["Maj7", "Maj7", "Maj7", "Maj7"],
    "7sus4 Infinity Loop": ["Myxolidian", "Myxolidian", "Myxolidian", "Myxolidian"],
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
    "Long Minor 2-5-1 with Dorian ending": [
        "Locrian",
        "Locrian",
        "Locrian",
        "MinorResolutions",
        "Dorian",
        "Dorian",
    ],
    "Double resolution": ["Locrian", "Locrian", "MinorResolutions", "MinorResolutions"],
    "Dorian and Dominant 2-cells alternated": [
        "Dorian",
        "Dorian",
        "Locrian",
        "MinorResolutions",
        "Dorian",
        "Dorian",
        "Locrian",
        "MinorResolutions",
        "Dorian",
        "Dorian",
        "Locrian",
        "MinorResolutions",
    ],
}


def sample_melodic_line_with_connecting_note(
    df, mode, num_cells, required_connecting_note, notes_to_be_present
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
    # Filter cells by mode
    df = df.reset_index()
    filtered_df = df[
        (df["Start Note"].isin(notes_to_be_present))
        | (df["End Note"].isin(notes_to_be_present))
    ]
    filtered_df = filtered_df[filtered_df["Modes"].apply(lambda x: mode in x)].copy()
    melodic_line = []
    # Try to find a starting cell that includes the required connecting note
    starting_candidates = filtered_df[
        (filtered_df["Start Note"].astype(str) == required_connecting_note)
        | (filtered_df["End Note"].astype(str) == required_connecting_note)
    ]
    if starting_candidates.empty:
        st.warning("No cells found with the required connecting note.")
    current_cell = starting_candidates.sample(
        weights=(1 / (starting_candidates["Sample Count"] + 1)), n=1
    ).iloc[0]

    melodic_line.append(current_cell["Cell Name"])

    # Update sample count and remove the current cell from further selection
    df.loc[df["Cell Name"] == current_cell["Cell Name"], "Sample Count"] += 1
    filtered_df = filtered_df[filtered_df["Cell Name"] != current_cell["Cell Name"]]

    # Sample additional cells that connect to each other
    for _ in range(1, num_cells):
        next_cells = filtered_df[
            filtered_df["Start Note"].astype(str) == str(current_cell["End Note"])
        ]
        if next_cells.empty:
            st.write("Unable to find connecting cells to continue the melodic line.")
        else:
            current_cell = next_cells.sample(
                weights=(1 / (next_cells["Sample Count"] + 1)), n=1
            ).iloc[0]
            melodic_line.append(current_cell["Cell Name"])

        # Update sample count
        df.loc[df["Cell Name"] == current_cell["Cell Name"], "Sample Count"] += 1
        filtered_df = filtered_df[filtered_df["Cell Name"] != current_cell["Cell Name"]]

    return melodic_line, df


df_sus4 = pd.read_csv("7sus4_sampling.csv")


# def sample_melodic_line_backward_for_251(
#     d_resolutions,
#     mode,
#     num_cells,
#     required_connecting_note,
#     notes_to_be_present=df_sus4["Start Note"].unique(),
# ):
#     """
#     Samples a sequence of cells for a 2-5-1 line where the first num_cells - 1 are from df_7sus4,
#     and the last cell connects at the required connecting note from df, favoring less frequently sampled cells.
#     The construction of the line is done backward, ensuring the final note is the required connecting note.

#     Parameters:
#     - df_7sus4: The DataFrame containing 7sus4 cell data.
#     - df: The DataFrame containing cell data for the final cell.
#     - mode: The mode to filter cells by.
#     - num_cells: The number of cells to be connected in the melodic line.
#     - required_connecting_note: The required note that must be present as the connecting note among the sampled cells.

#     Returns:
#     - A list of cell names representing the sampled melodic line, or a message if the criteria cannot be met.
#     """
#     melodic_line = []
#     df = d_resolutions.copy(deep=True).reset_index()
#     # Start with the final cell from df ensuring it ends with the required connecting note
#     final_candidates = df[df["Start Note"].astype(str) == required_connecting_note]
#     if final_candidates.empty:
#         st.error(
#             "Unable to find suitable final cell with the required connecting note.",
#         )

#     final_cell = final_candidates.sample(
#         weights=(1 / (final_candidates["Sample Count"] + 1)), n=1
#     ).iloc[0]
#     melodic_line.append(final_cell["Cell Name"])
#     df.loc[df["Cell Name"] == final_cell.name, "Sample Count"] += 1

#     current_end_note = final_cell["Start Note"]

#     df_7sus4 = df_sus4[
#         (df_sus4["Start Note"].isin(notes_to_be_present))
#         | (df_sus4["End Note"].isin(notes_to_be_present))
#     ]
#     # Construct the line backward from the second last cell to the first
#     for _ in range(num_cells - 1):
#         previous_candidates = df_7sus4[
#             df_7sus4["End Note"].astype(str) == str(current_end_note)
#         ]

#         if previous_candidates.empty:
#             st.error("Unable to find connecting cells to continue the melodic line.")

#         previous_cell = previous_candidates.sample(
#             weights=(1 / (previous_candidates["Sample Count"] + 1)), n=1
#         ).iloc[0]
#         melodic_line.insert(0, previous_cell["Cell Name"])  # Insert at the beginning
#         df_7sus4.loc[
#             df_7sus4["Cell Name"] == previous_cell["Cell Name"], "Sample Count"
#         ] += 1

#         current_end_note = previous_cell["Start Note"]

#     return melodic_line, df


def line_structure_mapping(type, length=None):
    if type not in [
        "Dorian x Dominant",
        "Major x Dominant",
        "Dorian",
        "Maj7",
        "Locrian",
    ]:
        return line_structure_dic[type]
    elif type == "Dorian":
        return [random.choice(["Dorian"]) for _ in range(length)]
    elif type == "Maj7":
        return [random.choice(["Maj7"]) for _ in range(length)]
    elif type == "Locrian":
        return [random.choice(["Locrian"]) for _ in range(length)]
    elif type == "Dorian x Dominant":
        return [random.choice(["Dorian", "MinorResolutions"]) for _ in range(length)]
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

    # Start by the ending cell to take into account the pivot note
    while not success and count < 2000:
        try:
            melodic_line = []
            note_representations = []
            mode_list = line_structure_mapping(line_type, length=length)
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
                df_cells, mode_list[-1], loc_to_dom, dom_to_minor, sus_to_loc_dorian
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
                    df_cells, mode, loc_to_dom, dom_to_minor, sus_to_loc_dorian
                )
                # st.write(df_cells)
                # st.write(mode)
                # st.write(note_representations[-1][0])
                df_cells = df_cells[
                    df_cells["End Note"].astype(str) == note_representations[-1][2]
                ]
                if connecting_notes is not None:
                    connecting_notes_reversed = connecting_notes[:-1][::-1]
                    # st.write(i)
                    # st.write(mode)
                    # st.write(connecting_notes_reversed[i])
                    # st.write(connecting_notes_reversed[i - 1])

                    df_cells = df_cells[
                        (df_cells["Start Note"].isin(connecting_notes_reversed[i]))
                        & (df_cells["End Note"].isin(connecting_notes_reversed[i - 1]))
                    ]
                if i == len(mode_list) - 2:
                    # st.write("Last cells options", df_cells)
                    if starting_note not in ["None", None]:
                        #    st.write(starting_note)
                        df_cells = df_cells[df_cells["Start Note"] == starting_note]
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
    return melodic_line[::-1], note_representations[::-1], mode_list
