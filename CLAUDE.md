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

`data/sampling/*_sampling.csv` (one per mode: `Maj7`, `Minor`, `Dorian`, `Myxolidian`,
`Locrian`, `MajorResolutions`, `MinorResolutions`, `7sus4`) are the **hand-edited source of
truth** for the cells — edit them directly to add/change cells. `Minor` is the ii-relative
melodic-minor vocabulary (was named `Dorian` before 2026-08); `Dorian` is its `#7`-free
subset (derived once by filtering, but independently hand-editable since). Columns: `Cell Name`, `Start Note`, `End Note`,
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
contexts: sus4→Minor/Dorian/Locrian, Locrian→Dominant, Dominant→Minor/Major, and
Dominant→Dorian-ii — `dom_to_dorian_mapping` re-spells Myxolidian V-relative degrees from the
ii root, e.g. dom `1`→`4`, `5`→`1`, `#11`→`#7`; that last one is applied automatically for the
"Dorian x Myxolidian" line type, it is what makes the two vocabularies pivot-compatible) →
filter by
`Start Note`/`End Note` + `Movement` → render.

- `scripts/paths.py` — `sampling_file(chord)`, `PRACTICE_DETAILS`, `MELODIC_LINES_LOG`.
- `scripts/melodic_lines/combinations.py` — `find_combinations_on_pivot_new()` pairs ending ×
  starting cells on a pivot.
- `scripts/melodic_lines/melodic_lines.py` — `line_structure_dic` / `line_structure_mapping()`
  define the cell-mode sequence per line type (e.g. "Long Maj 2-5-1" → Myxolidian×3 +
  MajorResolutions; "Dorian x Myxolidian" → n Dorian + m Myxolidian cells, counts chosen in
  the UI, default 1-1, Myxolidian degrees auto-translated to the ii representation);
  `sample_line_from_path_with_connecting_note()` builds a line **backward
  from the ending cell** to keep note continuity, honoring movement/note constraints.
  The sampler itself enforces `connecting_notes[k]` on cell k's start note (the pivot it
  enters); for the combo, "chord tones" means the ENTERING chord's 1-3-5-7 — Myxolidian
  cells get the V7's tones in ii spelling (4-6-1-3) via `combo_chord_tone_connecting_notes`.
  Page 1 applies the same re-spelling when chord1 is Dorian/Minor and chord2 is Myxolidian
  (an `st.info` shows whenever the mapping is active, on pages 1–2).
  When a line's degrees are translated, the fingering bridge reads them with the
  translated mode (combo cells read as `Dorian`) while `movement_modes` keeps the ORIGINAL
  CSV names so Movement lookups hit the right file (cell names collide across CSVs).
- `scripts/utils.py` — `join_notes`, `validate_results`, `get_or_update_practice_details`
  (daily key/position), `sidebar_practice_key` (the shared "Today's Key" + "Today's
  Position" sidebar SELECTBOXES every page uses — changing either persists the override to
  `practice_details.json` via `set_practice_key`/`set_practice_position` so all pages agree;
  tomorrow's random draw is unaffected; position is 1-based into `positions.POSITIONS`),
  `sidebar_metronome` (called right after it on EVERY page: tempo input, default 85, in
  `st.session_state.tempo` — also the tabs' play-along tempo — plus the guitarapp iframe in a
  sidebar expander; kept at the top so it never moves/remounts and survives `st.stop()`),
  `save_practice_session` (appends a row, `os.makedirs`-es
  `data/logs/`, writes a header only on a fresh/empty file), and `load_practice_lines`
  (reads the log, or returns an empty `PRACTICE_LOG_COLUMNS` DataFrame when it's missing — so
  the UI works on a fresh Cloud deploy where the log isn't in git).

**UI pages:** `Cell_Quizz.py` (home; cell quiz + per-position fingering tabs),
`pages/1_Cell_Connexions.py` (timed pivot-connection drill + per-pair fingering/scores; a
"Enforce the position" makes today's position a HARD box anchored on TODAY'S KEY by default
(the I of the ii-V-I, or the chord itself for a single-chord pair), or on chord 1 / chord 2
(derived per pair from the pivot) via the "Anchor the position on" radio; unticked = Free.
**Widget rule:** sidebar/stateful widgets use `key=` + a one-time `st.session_state` seed —
NEVER `value=st.session_state.get(...)` written back from the same widget (Streamlit
rebuilds the widget when its default changes and swallows every second change). And a keyed widget drawn BELOW a button that calls `st.rerun()` is reset by that
rerun (its state is dropped as 'not drawn'); page 1's `_sticky_checkbox` (value kept in a
non-widget key, synced via on_change, re-seeded each run) is the pattern for those. With a position enforced, EVERY fingering of each
connection inside the shape is listed — both octaves of the box, every register, every
string/fret layout via `optimizer.enumerate_fingerings`, hard-filtered to the box and to the
sidebar's max cost. Curation is two-level and persisted in `data/logs/connection_picks.json`
per (chords, pivot, position, anchor): kept CONNECTIONS (`kept`) and, per connection, DELETED
FINGERINGS by layout signature (`deleted_fingerings` — deleted, not kept, so a fingering the
engine finds later shows by default). 'Show deleted fingerings' reveals/restores them. The
exercise walks the kept connections, one (cheapest kept) fingering each or every kept one
with the 'Practice all kept fingerings' checkbox — deleted fingerings are never practised),
`pages/2_Melodic_Lines.py` (generate/grade/log lines; per-position fingering ranking; batch
"sample N lines & rank by playability"; Save line persists the tab. Same fingering logic as
page 1: "Enforce the position" = today's position as a HARD box on today's key (or its V via
the sidebar checkbox), EVERY in-box fingering listed via `line_fingerings()`, click to
preview, sidebar max-cost filter; the batch/exhaustive rankings use each line's cheapest
in-box fingering), `pages/4_Score_To_Tab.py` (MusicXML/PDF score → tab;
ranks Free (+ alternate), the 5 named positions and 3 neck bands by feasibility via
`positions.rank_absolute_fingerings`; a start/end-note slider tabs just a slice of the score;
**score library** — `scripts/score_library.py` saves a
MusicXML under a sequence name into `data/scores/` for reload, and attaches the chosen best
fingering (SVG + compact encoding) to that sequence), `pages/5_Pentatonics.py` (pentatonic
runs/patterns/Bergonzi formulas/shifting, ranked fingerings — see `config.py` below),
`pages/6_Triad_Pairs.py` (triad pairs & hexatonics — see `scripts/triad_pairs/` below: neck
maps + the pentatonic-style exercises on the six-note union, incl. the alternating-triads
grouping; same "Enforce the position" / max-cost / cost-weights sidebar as page 5).

## Fingering engine — `scripts/fingering/`

Converts fixed pitches to optimal Gypsy-jazz guitar fingering + picking via a
**Viterbi/DP shortest path** (never greedy). Read the module docstrings — they carry the
domain logic:

- `optimizer.py` — the DP over states `(string, fret, anchor, stroke, run_len)`;
  `optimize_fingering(line, context, config)` is the public entry point. Includes a
  consistency pass (repeated pitches keep one placement) and k-best for alternates.
  `enumerate_fingerings()` lists EVERY layout a (boxed) config admits — one placement per
  distinct pitch, root pin as a hard filter, each solved for its best picking — ranked by
  REPORTED cost. Known gap: the DP searches on a pre-`relabel_fingers` cost, so
  `optimize_fingering` can return a layout whose reported cost is higher than another
  in-box layout's (seen: 20.1 vs 14.1); the enumeration catches those.
- `costs.py` — THE cost model (single source for search *and* reporting). String/stroke
  conventions, finger-PAIR span matrix (3-4 spans 1 fret, 1-4 spans 4), shift/reach/open-string/
  stretch pricing, soft position-window overflow, soft root pin.
  **Per-cell drop exception:** `FingeringConfig.cell_drop_scale` (cell name → multiplier,
  default `("Convert style", 0.25)`) scales the managed-drop charge when BOTH notes of a
  descending crossing belong to that cell (pivot crossings stay full price). Use it for
  idiomatic cells that leap downward repeatedly (Dorian "Convert style" 3-7-6-5-3 cost
  19–26 in connections, ~2 drops × 10); never lower `drop_cost` globally for one cell.
- `picking.py` — Gypsy picking rules (every string entry = rest-stroke D; same-string D-U
  alternation; U-invariant) and `verify_conventions()`, a pre-search sanity check that halts
  if the ascending-sweep/drop convention is ever inverted. **Downbeats want D:** a U on
  beat 1 is illegal (hard, like U-U and U on a string entry); a U on beat 3 is soft
  (`beat3_penalty`); a same-string D-D that lands a downbeat on D costs `downbeat_dd_penalty`
  (slightly above the plain `same_string_dd_penalty`, so the repeat moves to a weak beat when
  it can). A phrase opens on D, except an OFF-BEAT pickup, which may be U (H4).
- `config.py` — `FingeringConfig`: every weight/limit, tunable ("debug by ear").
  `allow_open_strings` defaults to **False** engine-wide (opens are not part of the fretted
  Gypsy vocabulary and kept polluting "best" fingerings near the nut); the ONE sanctioned
  exception is pentatonic runs — `scripts/pentatonics/fingering_rank.py` re-enables opens
  (its 3+2 open-string-pivot system PINS a fret-0 note, and pins filter through
  `candidate_placements`, so the override is load-bearing). A pitch only reachable open
  (e.g. E2) is now unplayable → the score page's octave-shift fallback covers it.
  Page 5 exercises: scale run, x-notes pattern (`notes_pattern_run`: x consecutive scale notes
  per group, next group one scale note up/down; groups tagged `cell` G1.. so slices align),
  chromatic passing tones, Bergonzi patterns, shifting. Page 5 also has "Enforce the position": today's position as a box on the page's Key with
  `PENTA_POSITION_SLACK` (±1 fret — runs, unlike cell connections, get the tolerance), EVERY
  in-box fingering of the run's longest PREFIX that fits listed via
  `enumerate_position_fingerings()` — the fingering always starts on the run's first note, so
  "Start on X" is literally what the tab starts on (a longest-slice-anywhere rule was tried: it
  picked a cheaper slice from the middle starting on another degree) — falls back to the single
  optimum above 4000 layouts, ranked by cost per note; its own max-cost slider
  (`pent_max_cost`, default 30 — page 6's `tp_max_cost` uses the same default — on TOTAL cost).
- `cell_bridge.py` — **jazz reading of cell degrees → pitches**: bare degree numbers are
  MODE-DIATONIC (Dorian `3` = minor 3rd, Myxolidian `7` = b7), accidental-spelled tokens
  (`b9`, `#11`, `maj7`) are absolute; octaves chosen by nearest-octave voice-leading;
  `Movement` (A/D) is a HARD contour constraint; explicit `(higher)`/`(lower)` suffixes in the
  CSV `Notes` force octave-displacement direction (e.g. the Honeysuckle cells); the displaced
  note in an unmarked cell is placed as EARLY as possible. `build_chain_line()` merges
  pivot-connected cells into one line (the pivot is ONE shared note). **Cell notes are
  EIGHTH notes** (the player's reading): `timed_cell_line()` / `cell_context()` /
  `cell_beat()` put every cell line on pages 1–2 and the home page on that grid — 4/4 bars,
  `density="eighth"` (drops priced at eighth pace), so pivot-chained 5-note cells stride
  2 beats and every pivot lands on beat 1 or 3. Chord `start_beat`s are in beats
  (`cell_beat(pivot_index)`). (The former standalone Fingering page was removed 2026-10-12 — pages 1–2 cover it.)
  **What "Today's Key" means** (single source: `is_single_chord()` / `root_offset()`, judged
  on ORIGINAL CSV modes, never translated reading modes): a SINGLE-CHORD line (Dorian→Dorian,
  Minor↔Dorian, Myxo→Myxo… — never with resolution cells) is played ON the key (Eb + Dorian
  = Ebm7); any multi-chord line reads the key as the I of a ii-V-I (`DEFAULT_MODE_ROOT_OFFSET`:
  Eb + Dorian→Myxolidian = Fm7→Bb7). Pages 1–2 show this as an info/caption
  (`melodic_lines.harmony_caption`); chord symbols use flat jazz spelling (Eb, Ab, Bb).
- `positions.py` — `position_boxes()` returns a shape's box at its root fret AND 12 frets up
  (`position_config_for_key` only gives the low one);
  **A position is a HAND BOX, nothing more** (user-validated 2026-10): CAGED X = root under
  the index (rf-1..rf+4, roots pinned to the shape's strings); Diagonal X = root under the
  PINKY (rf-3..rf, roots unpinned) — Eb: CAGED A 5–10, Diagonal A 3–6, CAGED E 10–15,
  Diagonal E 8–11. No climbing regions, no per-string slants (both were tried and rejected:
  a wide region let the E-shape box pass as "Diagonal A"; a slant rejected natural hand
  boxes). `classify_positions()` lists EVERY box a fingering fits; `POSITION_SLACK` (0 = the box is a HARD
  boundary — validated; it applies to BOTH page 1's enumeration and `classify_positions()` so
  'listed in' and 'labelled with' a position always agree. ±2 was tried and reverted: the
  boxes overlapped too much; a 1-fret slack without matching labelling produced 'none' rows).
  (`FingeringConfig.string_fret_windows` per-string boxes remain supported but unused.)
  `position_signature()` goes into page 1/2 `st.cache_data` keys so a shape change
  invalidates cached fingerings.
  the 5 named positions (CAGED E/A, Diagonal E/A, Horizontal D), key-anchored
  soft fret boxes + CAGED root-string pins; `classify_position()` names where a free fingering
  landed; `rank_absolute_fingerings()` ranks Free/positions/neck-band candidates for a FIXED
  absolute-pitch line (scores, page 4) — no re-voicing, identical placements merged, all scored
  under shared base weights so relaxed configs stay comparable. When a candidate's register
  doesn't fit as written (piano lines above string-1 fret 15 = G5) it retries the whole line
  transposed ±1–2 octaves (`shift` in the row); as-written rows ALWAYS outrank transposed ones.
- `render.py` — per-note table, ASCII tab, SoundSlice-style SVG/HTML tab with chords, cell
  brackets, degree labels, picking marks, play-along.
- `score_import.py` / `vision_omr.py` — score → line: MusicXML (exact), oemer OMR (weak on
  jazz fonts; runs in an isolated venv `~/.venvs/oemer-omr`), or Claude-vision reading.
  Multi-staff (piano) scores: only the top/right-hand staff becomes the melody (music21 path
  picks the highest-median-pitch part; the stdlib fallback keeps staff 1 voice 1), chord
  symbols are gathered from every staff, and music21's `-` flats are normalized (`E-m7` →
  `Ebm7`) so `degree_for`/`parse_chord` keep labeling chord tones
  (`vision_omr.py`; needs `ANTHROPIC_API_KEY` in `.streamlit/secrets.toml`, git-ignored).
  All OMR output flows through a human review table before tabbing.
- `chords.py` / `ornaments.py` — chord-symbol parsing for labels; phase-2 ornament engine
  (APPLY model, off by default): ONE device only, the upper-neighbor TURN/mordent
  (pick → hammer up → pull back, `8h10p8`) on target notes (chord tone on a bar downbeat,
  tagged resolution, or final note) — single string, no crossing, mechanically idle, pure
  phrasing colour; strip above ~180 bpm. With `config.ornament_engine_enabled` on it is
  applied to a COPY of the solution (`result.ornamented`, rendered with colour-coded
  bands/H-P slur arcs) alongside the untouched phase-1 line. Inserted notes are grace-timed
  (`Note.is_grace`). The mechanical families (drop cushions, slides, enclosures, chromatic
  triplets) were built, tried and REMOVED — they cluttered the tab; don't re-add without
  a display design.

**Tests:** `python -m scripts.fingering.tests` (repo root) — T1–T8 + the U-invariant, each
printing the full per-note table (T6 off-beat pickup U, T7 downbeat D-D pricing, T8 cell
eighth-note grid). Run after touching costs/optimizer/picking; the convention
sanity check runs before every search and raises `ConventionError` on model inversion.

## Triad pairs & hexatonics — `scripts/triad_pairs/` (page 6)

- `triads.py` — `Triad(root, quality)` (major/minor/diminished/augmented/sus4/sus2; tones
  spelled by LETTER — D major is D F# A — with Cb/E#/doubles folded to the plain enharmonic),
  `TriadPair(first, second)` whose `hexatonic` is the union of both triads ascending from the
  FIRST root (6 tones when disjoint; a shared tone is *owned* by the first triad for labels).
  `default_pair(key)` = the key's major triad + the major triad a WHOLE TONE up (C + D).
  Lines are engine dicts whose `degree` label is `"<symbol>:<degree>"` (`C:3`, `Dm:b3`) so
  the tab always says which triad a note belongs to; groupings are `cell`-tagged for the
  brackets (`G1…` for scale groupings, `C↑`/`D↓` for triad groups) and `group=x` keeps
  partial slices on grouping boundaries. Generators: `hexatonic_scale_run`,
  `hexatonic_pattern_run` (the pentatonic x-notes rules on the hexatonic) and
  `alternating_triads_run` — x arpeggio tones per group, triads alternating, each group
  starting on the next tone of ITS triad: `ascending` (every group up, inversions walking
  up, closing on the top-octave start tone), `descending` (mirror from the top),
  `alternating ↑↓ (climbing)` (one triad up, the other DOWN from the next tone above the
  previous group's last note — C E G · A F# D · E G C · D A F# …) and `alternating ↓↑
  (falling)`. The first group's triad is the one owning the starting tone.
- `neck_map.py` — pure-SVG fretboard map (frets 0–`max_fret`, high e on top like the tab):
  every tone of the pair coloured by triad (`TRIAD_COLOURS`), shared tones two-colour, roots
  ringed, open strings hollow (shown, never fingered). `position_map_boxes(position, key)`
  → the shape's hand box(es) from `positions.position_boxes` (both octaves), drawn solid
  with the ±`PENTA_POSITION_SLACK` band dashed and out-of-box tones faded; the page embeds
  the SVG with `st.markdown(unsafe_allow_html=True)` (responsive, no iframe).
- Ranking reuses the pentatonic module: `fingering_rank.rank_line_fingerings` /
  `rank_line_across_starts` are the GENERIC Free + 5-positions rankers (fretted-only — no
  3+2/open-string systems, no open strings; position rows covering under a third of the run
  are demoted to "fits only N/M notes"), and `enumerate_position_fingerings` /
  `enumerate_across_starts` serve "Enforce the position" unchanged (today's position as a
  box on the page's Key, ±1 fret, longest prefix from the chosen starting note).

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
- `data/scores/` — the **score library** (page 4 via `scripts/score_library.py`): `index.csv`
  (one row per named sequence + its chosen best fingering), `files/` (the saved MusicXML),
  `tabs/` (the best-fingering SVG). User-uploaded, NOT regenerable — **versioned**, unlike
  `data/logs/`; paths in the index are repo-root-relative (CWD-independent).
- `.streamlit/secrets.toml` — git-ignored; holds `ANTHROPIC_API_KEY` for the vision score reader.
- `archive/` — retired JSON pipeline + orphan data files, kept for reference only.
