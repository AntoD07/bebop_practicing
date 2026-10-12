"""DataFrame adapter over ``scripts.domain.cells.cell_frames`` (legacy pages).

Returns the same ``(df_cells, mapped_notes, chord_tones_mapping)`` triple the
Streamlit pages consume: the raw cells of a chord as a DataFrame indexed by
``Cell Name`` (columns ``Start Note`` / ``End Note`` / ``Notes`` / ``Movement``
/ ``Type``), the unique pivot-representation values of ``field`` (an object
array), and the row-wise ``{mapped: raw}`` map.
"""

from scripts.domain.cells import cell_frames as _cell_frames


def create_cell_frames(
    chord,
    mode_filter,
    permute_notes,
    bonus,
    field="Start Note",
    loc_to_dominant=False,
    dom_to_minor=False,
):
    import numpy as np
    import pandas as pd

    cells, pivots, mapping = _cell_frames(
        chord, bonus=bonus, field=field, dom_to_minor=dom_to_minor,
        sus4=permute_notes, loc_to_dominant=loc_to_dominant,
    )
    if mode_filter and chord in ["Minor", "Dorian", "Locrian", "Myxolidian"]:
        cells = [c for c in cells if c.modes is not None and chord in c.modes]
    rows = []
    for c in cells:
        row = {
            "Cell Name": c.name, "Start Note": c.start, "End Note": c.end,
            "Notes": str(list(c.degrees)), "Movement": c.movement, "Type": c.type,
        }
        if c.modes is not None:
            row["Modes"] = str(list(c.modes))
        rows.append(row)
    cols = ["Cell Name", "Start Note", "End Note", "Notes", "Movement", "Type"]
    df = pd.DataFrame(rows, columns=cols + (["Modes"] if any("Modes" in r for r in rows) else []))
    df = df.set_index("Cell Name")
    return df, np.array(list(pivots), dtype=object), mapping
