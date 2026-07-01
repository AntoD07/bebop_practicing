# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the app

This is a Streamlit multi-page app managed with [Poetry](https://python-poetry.org/):

```bash
poetry install
poetry run streamlit run Cell_Quizz.py     # home page; pages/ are auto-discovered
```

Serves on port 8501. Without Poetry, any env with `streamlit` + `pandas` works:
`streamlit run Cell_Quizz.py`. There is no test suite or linter configured.

**Two dependency manifests, by design:**
- `pyproject.toml` — Poetry, for local dev (`streamlit`, `pandas`, Python `>=3.10,<3.13`;
  pinned to the numpy-1.x line — see the note in the file before bumping).
- `requirements.txt` — what **Streamlit Community Cloud** installs (a plain file builds faster
  and more deterministically on the server). Keep it in sync with `pyproject.toml`.

`.streamlit/config.toml` holds settings safe for both local and Cloud (notably
`server.runOnSave = true` for the fast edit→reload loop).

**Fast phone preview:** `./scripts/dev_preview.sh` runs Streamlit behind a public `cloudflared`
quick tunnel (auto-reload on save) so you can check the app on a phone. Requires `cloudflared`;
tunnel-only server relaxations live in that script, not in `config.toml`, so they never weaken
the hosted deploy. `DRY_RUN=1 ./scripts/dev_preview.sh` validates setup without launching.

Data paths are resolved relative to the repo root via `scripts/paths.py`, so the app is
CWD-independent for data files. (Imports are absolute `from scripts...`; Streamlit puts the
entry-script dir — the repo root — on `sys.path`, so launching via the entry script is what
makes those imports resolve.)

## Core domain concept: the "cell"

A *cell* is a short (~5-note) melodic motif expressed as **scale-degree strings**, not pitches:
chord tones `1/3/5/7`, extensions `9/11/6`, alterations `b7/#11/b9/#9/b6`. Each cell carries a
`Start Note`, `End Note`, a `Movement` (`A` ascending / `D` descending / `N` neutral), and
(in some CSVs) mode tags. Two cells **connect** when the first cell's `End Note` equals the
second's `Start Note` — the *pivot*. Melodic lines are chains of pivot-connected cells.

No MIDI/audio/notation — everything is text (`"1-3-5-7"` via `join_notes`); the metronome is an
embedded `guitarapp.com` iframe.

## The cell library is the CSVs

`data/sampling/*_sampling.csv` (one per mode: `Maj7`, `Dorian`, `Myxolidian`, `Locrian`,
`MajorResolutions`, `MinorResolutions`, `7sus4`) are the **hand-edited source of truth** for the
cells — edit them directly to add/change cells. Columns: `Cell Name`, `Start Note`, `End Note`,
`Notes`, `Movement`, `Type` (Essential/Bonus); some also carry `Modes`/`Mode scores`.
`fetch_data_base` filters to `Type == "Essential"` unless bonus cells are requested.

> Schema note: the CSVs are inconsistent — only `7sus4`/`MinorResolutions` have a `Modes`
> column. Live code only reads `Modes` when `mode_filter=True`, and every call site passes
> `mode_filter=False`, so this is latent, not active.

The original JSON cell definitions and the JSON→CSV generation code (`get_all_cells`,
`create_data_base`, `compute_scores`) are **retired in `archive/`** — not used at runtime.

## Architecture

**Runtime pipeline:** `scripts/load_cells.create_cell_frames(chord, ...)` →
`scripts/database.fetch_data_base` (reads the CSV) → optional
`scripts/modes/mode_transposition.change_note_representation` (remaps notes between harmonic
contexts: sus4→Dorian/Locrian, Locrian→Dominant, Dominant→Minor/Major) → filter by
`Start Note`/`End Note` + `Movement` → render.

- `scripts/paths.py` — `sampling_file(chord)`, `PRACTICE_DETAILS`, `MELODIC_LINES_LOG`.
- `scripts/melodic_lines/combinations.py` — `find_combinations_on_pivot_new()` pairs ending ×
  starting cells on a pivot.
- `scripts/melodic_lines/melodic_lines.py` — `line_structure_dic` / `line_structure_mapping()`
  define the cell-mode sequence per line type (e.g. "Long Maj 2-5-1" → Myxolidian×3 +
  MajorResolutions); `sample_line_from_path_with_connecting_note()` builds a line **backward
  from the ending cell** to keep note continuity, honoring movement/note constraints.
- `scripts/utils.py` — `join_notes`, `validate_results`, `get_or_update_practice_details`
  (daily key/position), `save_practice_session` (appends a row, `os.makedirs`-es
  `data/logs/`, writes a header only on a fresh/empty file), and `load_practice_lines`
  (reads the log, or returns an empty `PRACTICE_LOG_COLUMNS` DataFrame when it's missing — so
  the UI works on a fresh Cloud deploy where the log isn't in git).

**UI pages:** `Cell_Quizz.py` (home; cell memorization quiz, builds start/end indices from the
CSV DataFrame), `pages/1_Cell_Connexions.py` (timed pivot-connection drill),
`pages/2_Melodic_Lines.py` (generate, grade, and log melodic lines).

## Data & persistence

- `data/sampling/*_sampling.csv` — the cell library (see above); **versioned**.
- `data/logs/` — runtime data, **git-ignored** (`data/logs/*.csv`, `*.json`), regenerated by
  the app and created on first run. So a fresh clone/deploy starts with an empty log:
  - `practice_details.json` — daily `{date, key, position}`, rotated by
    `get_or_update_practice_details()`.
  - `melodic_lines.csv` — graded melodic-line history (written by page 2 via
    `save_practice_session`, read via `load_practice_lines`).
- `archive/` — retired JSON pipeline + orphan data files, kept for reference only.
