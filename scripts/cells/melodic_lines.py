import pandas as pd
from scripts.cells.modes import compute_scores
import streamlit as st


def create_data_base(cells, file_name, **kwargs):
    """
    Converts a dictionary of cells into a structure suitable for creating a pandas DataFrame.

    Parameters:
    - cells: A dictionary with cell names as keys and lists of notes as values.

    Returns:
    - A dictionary with lists for 'Cell Name', 'Start Note', 'End Note', and 'Sample Count'.
    """
    cells_data = {
        "Cell Name": [],
        "Start Note": [],
        "End Note": [],
        "Notes": [],
        "Modes": [],
        "Mode scores": [],
        "Sample Count": [],
    }

    mode_scores = compute_scores(cells, **kwargs)

    for cell_name, notes in cells.items():
        cells_data["Cell Name"].append(cell_name)
        cells_data["Start Note"].append(notes[0])  # First note in the list
        cells_data["End Note"].append(notes[-1])  # Last note in the list
        cells_data["Notes"].append(notes)  # Last note in the list
        cells_data["Modes"].append(mode_scores[cell_name].pop("Modes"))
        cells_data["Mode scores"].append(mode_scores[cell_name])
        cells_data["Sample Count"].append(0)  # Initialize sample count to 0
    df_cells = pd.DataFrame(cells_data)
    df_cells.to_csv(file_name, index=False)
    return df_cells


def fetch_and_update_data_base(file_name, cells, **kwargs):
    mode_scores = compute_scores(cells, **kwargs)
    try:
        df_cells = pd.read_csv(file_name)
        for cell_name, notes in cells.items():
            if cell_name not in df_cells["Cell Name"].unique():
                row = {
                    "Cell Name": cell_name,
                    "Start Note": notes[0],
                    "End Note": notes[-1],
                    "Notes": notes,
                    "Modes": mode_scores[cell_name].pop("Modes"),
                    "Mode scores": mode_scores[cell_name],
                    "Sample Count": 0,
                }
                df_cells.append(row, ignore_index=True)
                st.success("Added row {} to {} database".format(row, file_name))
        df_cells.to_csv(file_name, index=False)
    except FileNotFoundError:
        st.warning("Creating and overwritting database {}".format(file_name))
        df_cells = create_data_base(cells, file_name, **kwargs)

    return df_cells


def sample_melodic_line_with_connecting_note(
    df, mode, num_cells, required_connecting_note
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
    filtered_df = df[df["Modes"].str.contains(mode)].copy()
    # Initialize the melodic line
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
