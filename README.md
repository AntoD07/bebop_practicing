# Bebop Practicing

A Streamlit app for practicing bebop improvisation: memorizing melodic **cells**, drilling how
they **connect** at pivot notes, and generating full **melodic lines** (2-5-1s, modal lines).

## Setup & run

This project uses [Poetry](https://python-poetry.org/) for dependency management.

```bash
poetry install
poetry run streamlit run Cell_Quizz.py
```

The app serves on http://localhost:8501. `Cell_Quizz.py` is the home page; Streamlit
auto-discovers the other pages from `pages/`.

> Don't have Poetry? Install it with `pipx install poetry` (or `brew install poetry`).
> Alternatively, run directly with an environment that has `streamlit` and `pandas`:
> `streamlit run Cell_Quizz.py`.

## Layout

```
Cell_Quizz.py            # home page (cell memorization quiz)
pages/                   # additional Streamlit pages
  1_Cell_Connexions.py   # drill connecting two chords' cells at a pivot note
  2_Melodic_Lines.py     # generate, grade, and log full melodic lines
scripts/                 # application logic (imported as `scripts.*`)
  paths.py               # resolves data paths relative to the repo root
  load_cells.py          # create_cell_frames() — loads cell DataFrames from the CSVs
  database.py            # fetch_data_base() — reads a sampling CSV
  utils.py               # display/validation helpers, daily key/position, session logging
  modes/                 # note transposition between harmonic contexts
  melodic_lines/         # cell combinations and melodic-line sampling
data/
  sampling/*_sampling.csv  # the cell library — source of truth (see below)
  logs/                    # runtime data written by the app
archive/                 # retired code/data, kept for reference (not used at runtime)
```

## The cell library is the CSVs

The per-mode files in `data/sampling/` (`Maj7_sampling.csv`, `Dorian_sampling.csv`, …) are the
**hand-edited source of truth** for the cells. Edit them directly to add/change cells. Columns:
`Cell Name`, `Start Note`, `End Note`, `Notes`, `Movement` (A/D/N), `Type` (Essential/Bonus),
plus `Modes`/`Mode scores`.

Cells are written as **scale-degree strings**, not pitches: chord tones `1/3/5/7`, extensions
`9/11/6`, alterations `b7/#11/b9/#9/b6`. Two cells connect when one's `End Note` equals the
next's `Start Note` (the *pivot*).

The original JSON cell definitions and the JSON→CSV generation code are retired in `archive/`.
