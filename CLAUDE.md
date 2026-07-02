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

Cells are text (`"1-3-5-7"` via `join_notes`); the metronome is an embedded `guitarapp.com`
iframe. The **fingering engine** (below) is the one place cells become actual pitches and
rendered guitar tabs (SVG + Web-Audio play-along).

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

**UI pages:** `Cell_Quizz.py` (home; cell quiz + per-position fingering tabs),
`pages/1_Cell_Connexions.py` (timed pivot-connection drill + per-pair fingering/scores),
`pages/2_Melodic_Lines.py` (generate/grade/log lines; per-position fingering ranking; batch
"sample N lines & rank by playability"; Save line persists the tab), `pages/3_Fingering.py`
(standalone fingering playground), `pages/4_Score_To_Tab.py` (MusicXML/PDF score → tab).

## Fingering engine — `scripts/fingering/`

Converts fixed pitches to optimal Gypsy-jazz guitar fingering + picking via a
**Viterbi/DP shortest path** (never greedy). Read the module docstrings — they carry the
domain logic:

- `optimizer.py` — the DP over states `(string, fret, anchor, stroke, run_len)`;
  `optimize_fingering(line, context, config)` is the public entry point. Includes a
  consistency pass (repeated pitches keep one placement) and k-best for alternates.
- `costs.py` — THE cost model (single source for search *and* reporting). String/stroke
  conventions, finger-PAIR span matrix (3-4 spans 1 fret, 1-4 spans 4), shift/reach/open-string/
  stretch pricing, soft position-window overflow, soft root pin.
- `picking.py` — Gypsy picking rules (every string entry = rest-stroke D; same-string D-U
  alternation; U-invariant) and `verify_conventions()`, a pre-search sanity check that halts
  if the ascending-sweep/drop convention is ever inverted.
- `config.py` — `FingeringConfig`: every weight/limit, tunable ("debug by ear").
- `cell_bridge.py` — **jazz reading of cell degrees → pitches**: bare degree numbers are
  MODE-DIATONIC (Dorian `3` = minor 3rd, Myxolidian `7` = b7), accidental-spelled tokens
  (`b9`, `#11`, `maj7`) are absolute; octaves chosen by nearest-octave voice-leading;
  `Movement` (A/D) is a HARD contour constraint; explicit `(higher)`/`(lower)` suffixes in the
  CSV `Notes` force octave-displacement direction (e.g. the Honeysuckle cells); the displaced
  note in an unmarked cell is placed as EARLY as possible. `build_chain_line()` merges
  pivot-connected cells into one line (the pivot is ONE shared note).
- `positions.py` — the 5 named positions (CAGED E/A, Diagonal E/A, Horizontal D), key-anchored
  soft fret boxes + CAGED root-string pins; `classify_position()` names where a free fingering
  landed.
- `render.py` — per-note table, ASCII tab, SoundSlice-style SVG/HTML tab with chords, cell
  brackets, degree labels, picking marks, play-along.
- `score_import.py` / `vision_omr.py` — score → line: MusicXML (exact), oemer OMR (weak on
  jazz fonts; runs in an isolated venv `~/.venvs/oemer-omr`), or Claude-vision reading
  (`vision_omr.py`; needs `ANTHROPIC_API_KEY` in `.streamlit/secrets.toml`, git-ignored).
  All OMR output flows through a human review table before tabbing.
- `chords.py` / `ornaments.py` — chord-symbol parsing for labels; phase-2 ornament engine
  (built, ships disabled).

**Tests:** `python -m scripts.fingering.tests` (repo root) — T1–T5 + the U-invariant, each
printing the full per-note table. Run after touching costs/optimizer/picking; the convention
sanity check runs before every search and raises `ConventionError` on model inversion.

## Data & persistence

- `data/sampling/*_sampling.csv` — the cell library (see above); **versioned**.
- `data/logs/` — runtime data, **git-ignored** (`data/logs/*.csv`, `*.json`), regenerated by
  the app and created on first run. So a fresh clone/deploy starts with an empty log:
  - `practice_details.json` — daily `{date, key, position}`, rotated by
    `get_or_update_practice_details()`.
  - `melodic_lines.csv` — graded melodic-line history (written by page 2 via
    `save_practice_session`, read via `load_practice_lines`); carries `Tab`/`Tab file`
    columns (schema migrates automatically on save).
  - `tabs/` — saved fingering SVGs, one per saved line.
- `.streamlit/secrets.toml` — git-ignored; holds `ANTHROPIC_API_KEY` for the vision score reader.
- `archive/` — retired JSON pipeline + orphan data files, kept for reference only.
