import streamlit as st
import random

from scripts.load_cells import create_cell_frames
from scripts.modes.mode_transposition import change_note_representation


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
    "Long Minor with double resolution": [
        "Locrian",
        "Locrian",
        "MinorResolutions",
        "MinorResolutions",
    ],
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
    "Dorian x Dominant": [
        "Dorian",
        "Dorian",
        "MinorResolutions",
        "MinorResolutions",
        "Dorian",
        "Dorian",
        "MinorResolutions",
        "MinorResolutions",
        "Dorian",
        "Dorian",
        "MinorResolutions",
        "MinorResolutions",
    ],
}


def line_structure_mapping(type, length=None):
    if type not in [
        # "Dorian x Dominant",
        "Major x Dominant",
        "Dorian",
        "Myxolidian",
        "Maj7",
        "Locrian",
    ]:
        return line_structure_dic[type]
    elif type == "Dorian":
        return [random.choice(["Dorian"]) for _ in range(length)]
    elif type == "Maj7":
        return [random.choice(["Maj7"]) for _ in range(length)]
    elif type == "Myxolidian":
        return [random.choice(["Myxolidian"]) for _ in range(length)]
    elif type == "Locrian":
        return [random.choice(["Locrian"]) for _ in range(length)]
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
