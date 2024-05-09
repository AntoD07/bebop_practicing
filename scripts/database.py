import streamlit as st
import pandas as pd
from scripts.modes.mode_scores import compute_scores


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
        for name in df_cells["Cell Name"].unique():
            if name not in cells.keys():
                st.warning("Removing {} from database".format(name))
        rows = []
        for cell_name, notes in cells.items():
            if cell_name in df_cells["Cell Name"].unique():
                count = df_cells.loc[
                    df_cells["Cell Name"] == cell_name, "Sample Count"
                ].values[0]
            else:
                count = 0
                # st.success("Adding {} to {} database".format(cell_name, file_name))
            row = {
                "Cell Name": cell_name,
                "Start Note": notes[0],
                "End Note": notes[-1],
                "Notes": notes,
                "Modes": mode_scores[cell_name].pop("Modes"),
                "Mode scores": mode_scores[cell_name],
                "Sample Count": count,
            }
            rows.append(row)
        df_cells = pd.DataFrame(rows)
        df_cells.to_csv(file_name, index=False)
    except FileNotFoundError:
        st.warning("Creating and overwritting database {}".format(file_name))
        df_cells = create_data_base(cells, file_name, **kwargs)
    return df_cells.set_index("Cell Name")
