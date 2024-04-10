import streamlit as st
import pandas as pd


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


def sample_melodic_line_backward_for_251(
    d_resolutions,
    mode,
    num_cells,
    required_connecting_note,
    notes_to_be_present=df_sus4["Start Note"].unique(),
):
    """
    Samples a sequence of cells for a 2-5-1 line where the first num_cells - 1 are from df_7sus4,
    and the last cell connects at the required connecting note from df, favoring less frequently sampled cells.
    The construction of the line is done backward, ensuring the final note is the required connecting note.

    Parameters:
    - df_7sus4: The DataFrame containing 7sus4 cell data.
    - df: The DataFrame containing cell data for the final cell.
    - mode: The mode to filter cells by.
    - num_cells: The number of cells to be connected in the melodic line.
    - required_connecting_note: The required note that must be present as the connecting note among the sampled cells.

    Returns:
    - A list of cell names representing the sampled melodic line, or a message if the criteria cannot be met.
    """
    melodic_line = []
    df = d_resolutions.copy(deep=True).reset_index()
    # Start with the final cell from df ensuring it ends with the required connecting note
    final_candidates = df[df["Start Note"].astype(str) == required_connecting_note]
    if final_candidates.empty:
        st.error(
            "Unable to find suitable final cell with the required connecting note.",
        )

    final_cell = final_candidates.sample(
        weights=(1 / (final_candidates["Sample Count"] + 1)), n=1
    ).iloc[0]
    melodic_line.append(final_cell["Cell Name"])
    df.loc[df["Cell Name"] == final_cell.name, "Sample Count"] += 1

    current_end_note = final_cell["Start Note"]

    df_7sus4 = df_sus4[
        (df_sus4["Start Note"].isin(notes_to_be_present))
        | (df_sus4["End Note"].isin(notes_to_be_present))
    ]
    # Construct the line backward from the second last cell to the first
    for _ in range(num_cells - 1):
        previous_candidates = df_7sus4[
            df_7sus4["End Note"].astype(str) == str(current_end_note)
        ]

        if previous_candidates.empty:
            st.error("Unable to find connecting cells to continue the melodic line.")

        previous_cell = previous_candidates.sample(
            weights=(1 / (previous_candidates["Sample Count"] + 1)), n=1
        ).iloc[0]
        melodic_line.insert(0, previous_cell["Cell Name"])  # Insert at the beginning
        df_7sus4.loc[
            df_7sus4["Cell Name"] == previous_cell["Cell Name"], "Sample Count"
        ] += 1

        current_end_note = previous_cell["Start Note"]

    return melodic_line, df
