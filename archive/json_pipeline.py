"""RETIRED — JSON cell pipeline (reference only, not used by the app).

The app now runs entirely off the hand-edited ``data/sampling/*_sampling.csv`` files. The code
below used to load cells from the JSON definitions (``archive/cells/*.json``) and regenerate the
sampling CSVs from them:

- ``get_all_cells`` / ``create_starting_ending_cells`` — extracted from ``scripts/load_cells.py``;
  ``get_all_cells`` was never called (its only call site was commented out in ``Cell_Quizz.py``).
- ``create_data_base`` — extracted from ``scripts/database.py``; regenerated a sampling CSV from
  cells. Note: its output omits the ``Type`` column that ``database.fetch_data_base`` filters on,
  so the live CSVs were hand-augmented after generation.

Kept for reference in case the JSON-driven workflow is ever revived.
``compute_scores`` lives alongside this file in ``archive/mode_scores.py``.
"""

import json
from pathlib import Path

import pandas as pd

CELLS_DIR = Path(__file__).resolve().parent / "cells"


def create_starting_ending_cells(cells):
    starting_cells = {}
    ending_cells = {}
    for cell_name, notes in cells.items():
        start_note = notes[0]
        end_note = notes[-1]
        if start_note not in starting_cells:
            starting_cells[start_note] = {}
        starting_cells[start_note][cell_name] = notes
        if end_note not in ending_cells:
            ending_cells[end_note] = {}
        ending_cells[end_note][cell_name] = notes
    return starting_cells, ending_cells


def get_all_cells(chord, include_bonus=False):
    if chord == "MajorResolutions":
        file = CELLS_DIR / "maj_resolution.json"
    elif chord == "Maj7":
        file = CELLS_DIR / "maj7.json"
    elif chord == "MinorResolutions":
        file = CELLS_DIR / "minor_resolution.json"
    elif chord in ["7sus4", "Dorian", "Myxolidian", "Locrian"]:
        file = CELLS_DIR / "7sus4.json"
    else:
        raise ValueError("Unkown chord type")
    with open(file) as f:
        dic = json.load(f)
    unordered_cells = dic["essential"]
    if include_bonus:
        unordered_cells.update(dic["bonus"])
    cells = {key: value for key, value in sorted(unordered_cells.items())}
    if chord == "Locrian":
        with open(CELLS_DIR / "Locrian.json") as f:
            loc_cells = json.load(f)
        cells.update(loc_cells)
    starting_cells, ending_cells = create_starting_ending_cells(cells)
    if chord == "MajorResolutions":
        with open(CELLS_DIR / "7sus4.json") as f:
            dic = json.load(f)
        unordered_cells = dic["essential"]
        if include_bonus:
            unordered_cells.update(dic["bonus"])
        sus_cells = {key: value for key, value in sorted(unordered_cells.items())}
        _, ending_cells = create_starting_ending_cells(sus_cells)
    return cells, starting_cells, ending_cells


def create_data_base(cells, file_name, **kwargs):
    """Regenerate a sampling CSV from a dict of cells. Requires ``compute_scores`` from
    ``archive/mode_scores.py`` (run from the ``archive/`` directory)."""
    from mode_scores import compute_scores

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
        cells_data["Start Note"].append(notes[0])
        cells_data["End Note"].append(notes[-1])
        cells_data["Notes"].append(notes)
        cells_data["Modes"].append(mode_scores[cell_name].pop("Modes"))
        cells_data["Mode scores"].append(mode_scores[cell_name])
        cells_data["Sample Count"].append(0)
    df_cells = pd.DataFrame(cells_data)
    df_cells.to_csv(file_name, index=False)
    return df_cells
