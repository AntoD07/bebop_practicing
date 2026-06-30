# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the app

This is a Streamlit multi-page app. Run from the **repo root** (required — modules use
absolute `from scripts....` imports that only resolve from the root):

```bash
streamlit run Cell_Quizz.py        # Cell_Quizz.py is the home page; pages/ are auto-discovered
```

Serves on port 8501. Dependencies are not pinned anywhere — install manually:

```bash
pip install streamlit pandas       # plus stdlib: ast, json, datetime, random, re
```

Notes:
- There is **no** `requirements.txt`, test suite, or linter configured.
- `.devcontainer/devcontainer.json` references `app.py` and `requirements.txt`, **neither
  of which exist** — the real entry point is `Cell_Quizz.py`.

## Core domain concept: the "cell"

A *cell* is a short (~5-note) melodic motif expressed as **scale-degree strings**, not pitches:
chord tones `1/3/5/7`, extensions `9/11/6`, alterations `b7/#11/b9/#9/b6` (and `Locrian.json`
uses `#8` for octave displacement). Each cell carries a `Start Note`, `End Note`, a `Movement`
(`A` ascending / `D` descending / `N` neutral), and mode compatibility tags.

Two cells **connect** when the first cell's `End Note` equals the second's `Start Note` — this
shared note is the *pivot*. Melodic lines are chains of pivot-connected cells.

There is no MIDI/audio/notation rendering — everything is text (e.g. `"1-3-5-7"` via
`join_notes`), and the metronome is an embedded `guitarapp.com` iframe.

## Architecture (three layers)

**1. Cell definitions — source of truth**
- `scripts/cells/*.json` (`7sus4.json`, `maj7.json`, `maj_resolution.json`,
  `minor_resolution.json`, `Locrian.json`) define cells under `essential`/`bonus` keys.
- Root-level `*_sampling.csv` (one per mode: `Maj7`, `Dorian`, `Myxolidian`, `Locrian`,
  `MajorResolutions`, `MinorResolutions`, `7sus4`) are **pregenerated DataFrame caches** of
  those cells, with a `Sample Count` column used to bias sampling toward less-practiced cells.

**2. Logic — `scripts/`**
- `load_cells.py` — primary loader. `create_cell_frames(chord, ...)` returns a cell DataFrame;
  `get_all_cells()` / `create_starting_ending_cells()` build note→cell indices for connections.
- `modes/mode_transposition.py` — `change_note_representation(df, ...)` orchestrates remapping
  notes between harmonic contexts (sus4→Dorian/Locrian, Locrian→Dominant, Dominant→Minor/Major)
  via per-context mapping dicts.
- `modes/mode_scores.py` — `compute_scores()` rates a cell's affinity to Myxolidian/Dorian/
  Locrian by inspecting notes at indices `[0, 2, 4]`.
- `melodic_lines/combinations.py` — `find_combinations_on_pivot_new()` pairs ending cells ×
  starting cells that share a pivot note.
- `melodic_lines/melodic_lines.py` — `line_structure_dic` / `line_structure_mapping()` define
  the cell-mode sequence for each line type (e.g. "Long Maj 2-5-1" → Myxolidian×3 +
  MajorResolutions). `sample_line_from_path_with_connecting_note()` builds a line **backward
  from the ending cell** to guarantee note continuity, honoring movement/note constraints.
- `utils.py` — `join_notes` (display), `validate_results` (quiz checking),
  `get_or_update_practice_details` (daily key/position), `save_practice_session` (CSV logging).
- `database.py`, `main_fcts.py` — older/duplicate helpers largely superseded by `load_cells.py`.

**3. UI — Streamlit pages**
- `Cell_Quizz.py` (home) — memorization quiz on individual cells for a chosen chord.
- `pages/1_Cell_Connexions.py` — timed drill connecting two chords' cells at a pivot note.
- `pages/2_Melodic_Lines.py` — generate, grade, and log full melodic lines (2-5-1s etc.).

**Canonical data pipeline** (repeated across pages):
`create_cell_frames(chord)` → `change_note_representation(df, ...)` → filter by
`Start Note`/`End Note` + `Movement` → render.

## State & persistence

- Each page **re-initializes** its own `st.session_state` (daily `key`/`position`,
  `include_bonus`, chord selections, transposition flags, generated lines). State is **not**
  reliably shared across pages; pages re-read the day's context from `practice_details.json`.
- `practice_details.json` — daily `{date, key, position}`, rotated by `get_or_update_practice_details()`.
- `melodic_lines.csv` — graded melodic-line history (primary log).
- `practice_sessions.csv` — legacy session log.

## Gotchas

- Always run from the repo root (absolute `scripts.` imports).
- `scripts/cells/*.json` are the source of truth; editing them does **not** auto-update the
  `*_sampling.csv` caches — regenerate via `database.create_data_base()` if cell data changes.
- On macOS (case-insensitive FS) git may display `pages/2_Melodic_lines.py`; the real filename
  is `pages/2_Melodic_Lines.py`.
