# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single-user guitar practice app (bebop cells, pivot connections, melodic lines, pentatonics,
triad pairs, score → tab). Since 2026-10 it is a **Next.js 16 app** (`src/`) in front of a
**Python compute API** (`api/`, FastAPI) that wraps the fingering engine (`scripts/`). Both live
in ONE Vercel project (`api/index.py` is the Vercel Python function; `vercel.json` rewrites
`/api/py/*` to it). State is in **Turso** (libSQL) via Drizzle so phone and laptop agree. The
previous Streamlit app was retired in milestone 8 of the migration (branch `nextjs-migration`;
`git log` has it under `legacy/` before commit "Playwright specs, retire legacy").

Decisions taken with the user (2026-10-12): engine stays Python (no TS port); Vercel Hobby +
Python functions, Fly.io container as the fallback (`Dockerfile`, `fly.toml`); one shared
password; native Web-Audio metronome AND the guitarapp.com iframe panel; Turso + Drizzle.

## Running

```bash
uv sync && npm install && cp .env.example .env.local      # once (Node 24: ~/.local/node/bin if not on PATH)
BEBOP_API_KEY=<ENGINE_API_KEY> uv run uvicorn api.index:app --port 8000 --reload
npm run dev                                                # http://localhost:3000, sign in with APP_PASSWORD
./scripts/dev_preview.sh                                   # both + a cloudflared tunnel for the phone
```
No `TURSO_DATABASE_URL` → local libSQL file `data/logs/bebop.db` (tables created lazily by
`src/lib/db/client.ts`). `BEBOP_DEV=1` lets the API accept localhost without a key.

**Tests** — `python -m scripts.fingering.tests` (engine T1–T9; run after touching
costs/optimizer/picking), `BEBOP_DEV=1 uv run pytest tests/api -q` (78 tests incl. the
no-pandas/no-streamlit import guard, auth, domain parity, pick-key parity, golden fixtures),
`uv run python -m scripts.golden.dump --update` (refresh `tests/golden/responses/` after an
INTENDED engine change — the golden test diffs every response to 1e-6),
`uv run python -m scripts.golden.bench` (2400 random connection requests, each < 3.5 s),
`npm run typecheck && npm run lint && npm test` (Vitest: stores, geometry, pick keys, queue,
drill transitions, migration parsers), `npm run build && npm run e2e` (Playwright: login,
drill resume; needs the API up, `E2E_PASSWORD`).

## Core domain concept: the "cell"

A *cell* is a short (~5-note) melodic motif expressed as **scale-degree strings**, not pitches:
chord tones `1/3/5/7`, extensions `9/11/6`, alterations `b7/#11/b9/#9/b6`. Each cell carries a
`Start Note`, `End Note`, a `Movement` (`A` ascending / `D` descending / `N` neutral). Two cells
**connect** when the first cell's `End Note` equals the second's `Start Note` — the *pivot*.
Melodic lines are chains of pivot-connected cells. The fingering engine is the one place cells
become actual pitches and rendered tabs.

## The cell library is the CSVs

`data/sampling/*_sampling.csv` (`Maj7`, `Minor`, `Dorian`, `Myxolidian`, `Locrian`,
`MajorResolutions`, `MinorResolutions`, `7sus4`) are the **hand-edited source of truth**. `Minor`
is the ii-relative melodic-minor vocabulary (was named `Dorian` before 2026-08); `Dorian` is its
`#7`-free subset. Columns: `Cell Name`, `Start Note`, `End Note`, `Notes`, `Movement`, `Type`
(Essential/Bonus; missing → Essential, i.e. 7sus4). `scripts/domain/catalog.py` reads them ONCE
(`csv` + `ast.literal_eval`, every token stripped) into frozen `Cell` dataclasses with stable ids
`"<mode>:<sha1(mode|name|degrees)[:8]>"`. Data oddities are SURFACED, never silently fixed:
`Catalog.warnings` (served by `GET /health` and `/cells`) lists the 5 MajorResolutions rows
whose Start/End ≠ Notes[0]/[-1] (pivots match on the nominal columns, as the legacy pages did)
and the duplicate names. `pivot_hint()` reads "(from #9)"-style names (the pivot is re-pitched).

## Architecture

**Runtime pipeline:** `scripts/domain` (pure stdlib) → `scripts/fingering` (engine) →
`api/serialize.py` (JSON) → `api/routers/*` → Next.js `/api/engine/[...path]` proxy → React.

### `scripts/domain/` (pure stdlib — pandas/streamlit are gone; the import guard enforces it)
- `catalog.py` — `load_catalog()` (lru_cache), `cells(mode, bonus)`, `cell_by_id`, `find_cell`.
- `transposition.py` — the 4 mapping dicts (`dom_to_minor`, `dom_to_major`, `dom_to_dorian`,
  `loc_to_dom`) + the `sus4` arithmetic shift; `translate_token` is marker-aware
  (`9(lower)`) and raises `TranslationError` (→ HTTP 422 naming the token) on a gap. Fills
  added 2026-10: `#7 → #11` in dom→minor and dom→major (same pitch as `maj7`; confirm musically).
- `cells.py` — `CellView` (a cell read through translation steps); `pivot_steps` /
  `connection_steps` / `sampler_steps` reproduce EXACTLY which translation each legacy page
  applied; `cell_frames()` builds the `(cells, pivots, mapping)` triple row-wise (the old
  `zip(unique, unique)` was misaligned).
- `connections.py` — `pivot_options`, `pairs_for_pivot` (ending × starting on a pivot, in the
  FINGERING representation), `score_connection_pair()` = page 1's body for ONE pair: Free →
  `optimize_fingering`; a named position → EVERY in-box layout (both octaves of the box ×
  every register × every string/fret layout, root pinned hard) through the budget planner,
  deduped, sorted by `(cost, layout)`; `pick_key()` reproduces the legacy
  `connection_picks.json` key byte for byte; `reading_mode()`, `is_myxo_to_dorian()`.
- `sampling.py` — `line_structure_dic`, `line_structure_mapping(rng)`, `sample_line(rng)` (the
  backward sampler, faithful port incl. the 1/(row+1) last-cell weights), `sample_many`,
  `all_pairs` (exhaustive 2-cell), `connecting_note_lists()` (page 2's per-cell pivot lists),
  `pivots_respected`, `bridge_modes`. A sampled line CARRIES its rolled structure.
- `lines.py` — `line_cells`, `line_context`, `line_fingerings()` (page 2's logic with the
  budget planner + `classify_positions` filter).
- `budget.py` — `LayoutBudget` (max layouts + wall clock), `plan_chunk` (uses
  `optimizer.count_layouts`), `enumerate_chunks` (smallest chunk first; the rest fall back to
  the single optimum → `truncated`), `dedupe_sorted`, `layout_sig`.
- `notes.py` — constants (`PRACTICE_KEYS`, `DEGREE_ORDER`, `CHORD_TONES`, `NOTE_OPTIONS`, …),
  `harmony_caption`, the combo info strings.

### `api/` (FastAPI; every route under `/api/py`; `X-API-Key` on all but `/health`)
`settings.py` (BEBOP_* env), `auth.py`, `cache.py` (LRU keyed by endpoint + canonical request
+ `ENGINE_VERSION`; ETag/304; `meta: {engine_version, elapsed_ms, cached}` on every body),
`version.py` (`ENGINE_VERSION` = sha1 of engine + domain + CSVs + serializer — part of every
cache key on both sides), `budget.py`, `serialize.py` (THE wire shapes: `FingeringJSON`
{layout, encoding, cost, n_up, fret_lo/hi, positions[], where, placed[], chords, report,
alternate…}), `schemas.py` (pydantic requests; `ConfigOverrides` whitelist).
Routers: `health`, `cells` (+ `/translate`, `/positions` with the shared constants),
`connections` (`/connections/pairs`, `/fingering/connection` with `box` split + `max_layouts`),
`lines` (`/lines/sample` seedable, `/lines/pairs`, `/fingering/line`), `fingering`
(`/fingering/positions` home, `/fingering/rank-absolute` ≤ 64 notes), `pentatonics`
(`/patterns`, `/generate`, `/rank` — also the triads ranker with `generic: true`), `triads`
(`/pair` with neck markers + boxes, `/generate`), `score` (`/parse-musicxml` stdlib,
`/read-vision` Claude; anthropic/PIL imported lazily). "Sample N & rank", "Enumerate ALL pairs",
"Rank ALL formulas" are NOT endpoints — the frontend fans out per item.
Performance: default `BEBOP_MAX_LAYOUTS=2000` (≈3 s worst case; container sets 10000),
`BEBOP_TIME_BUDGET_MS=6000`; an unseeded `/lines/sample` is never cached.

### `scripts/fingering/` — the engine (unchanged domain logic; read the module docstrings)
- `optimizer.py` — Viterbi/DP over `(string, fret, anchor, stroke, run_len)`;
  `optimize_fingering` (consistency pass, k-best alternate), `enumerate_fingerings` (every
  layout a boxed config admits), `count_layouts` (the candidate-product arithmetic, no DP —
  the planner's input). `_backtrack` returns COPIES of trellis nodes (2026-10 fix: the
  alternate's `relabel_fingers` used to mutate the best path; T9 guards it).
- `costs.py` — THE cost model (search and reporting): finger-PAIR spans, shift/reach/
  open-string/stretch pricing, soft window overflow, soft root pin, `cell_drop_scale`
  ("Convert style" 0.25 — never lower `drop_cost` globally for one cell).
- `picking.py` — Gypsy picking rules + `verify_conventions()` (runs before every search, at API
  startup too). Downbeats want D: U on beat 1 illegal, beat 3 soft; off-beat pickup may be U.
- `config.py` — `FingeringConfig`; `allow_open_strings=False` engine-wide — the ONE exception is
  pentatonic runs (`scripts/pentatonics/fingering_rank.py` re-enables them; load-bearing).
- `cell_bridge.py` — jazz reading of degrees → pitches: bare numbers are MODE-DIATONIC
  (Dorian `3` = minor 3rd), accidental tokens absolute; nearest-octave voice-leading; Movement
  is a HARD contour constraint; `(higher)/(lower)` markers; the displaced note goes EARLY;
  `build_chain_line` shares pivots; **cell notes are EIGHTH notes** (`timed_cell_line`,
  `cell_context`, `cell_beat`: 4/4, pivots on beats 1/3). "Today's key": `is_single_chord()` /
  `root_offset()` judged on ORIGINAL CSV modes — a single-chord line is played ON the key,
  any multi-chord line reads the key as the I of a ii-V-I. Cell lookups (`cell_degrees`,
  `first_cell`, `cell_movement`) now go through the catalog.
- `positions.py` — a position is a HAND BOX (user-validated): CAGED X = root under the index
  (rf-1..rf+4, roots pinned), Diagonal X = root under the PINKY (rf-3..rf, unpinned),
  More Horizontal D (strings 2-5, wide window). `position_boxes()` = the box at the root fret AND
  12 frets up; `POSITION_SLACK = 0` (hard; validated) for connections/lines, `PENTA_POSITION_SLACK
  = 1` for runs; `classify_positions()`; `rank_absolute_fingerings()` (scores: Free + 5 positions
  + 3 neck bands, octave-shift fallback, as-written rows always first); `optimize_all_positions`.
- `render.py` — `format_report` (served as `FingeringJSON.report`), `render_svg` (the geometry
  the TS `TabSvg` mirrors: left 70, top 96, row 26, col 62, grace 36, lanes 22/40/64, colours
  `#1a3a8f/#b06a00/#3a7d3a/#c0392b`, upstroke box `#fdeaea`), `render_html` (reference for the
  play-along voices). `score_import.py` (MusicXML; oemer retired), `vision_omr.py` (Claude;
  `BEBOP_VISION_MODEL` overrides the model), `chords.py`, `ornaments.py` (turn only; off).

### `scripts/pentatonics/`, `scripts/triad_pairs/` — generators + rankers, unchanged
(`rank_pentatonic_fingerings` incl. the 3+2 / open-string-pivot / sliding systems,
`rank_line_fingerings` generic, `enumerate_position_fingerings` for "Enforce the position",
`Triad`/`TriadPair`/`alternating_triads_run`, `neck_markers`/`position_map_boxes` — the SVG
neck map itself is drawn in TS, `src/components/triads/NeckMap.tsx`).

### `src/` (Next.js 16 App Router, TS strict, Tailwind v4, TanStack Query, Zustand)
- `src/proxy.ts` — Next 16's middleware (file renamed `proxy.ts`): every route but `/login`,
  `/api/auth/login`, assets, manifest/icons and `/api/py` needs the `bp_session` HS256 cookie
  (`src/lib/auth.ts`, jose, 400 days). Pages redirect to `/login?next=`, APIs get 401.
- `src/app/(app)/layout.tsx` — mounted ONCE: `PracticeHeader` (today's key/position selects,
  tempo stepper, native metronome play/stop + beat dots, settings sheet with per-page options
  registered via `usePageSettings`), `DrillController`, `MetronomePanel` (iframe), side/bottom nav.
- `src/app/api/` — route handlers (Node runtime): `engine/[...path]` (adds the API key, checks
  the Turso `engine_cache` keyed by sha256(engine version + request), `maxDuration = 300`),
  `practice-day` (the SERVER draws today's key/position on the first request of the local date),
  `settings/[key]`, `picks/[pickKey]`, `lines`, `scores`, `drill/[id]`, `auth/*`.
- `src/lib/db/` — Drizzle schema (`practice_days`, `connection_picks`, `melodic_line_logs`,
  `scores`, `drill_sessions`, `settings`, `engine_cache`) + client with lazy `CREATE TABLE IF NOT
  EXISTS` (so dev needs no `db:push`). `scripts/migrate_logs.ts` imports the legacy logs.
- `src/lib/engine/` — `types.ts` (wire types), `client.ts` (`/api/engine/*` + IndexedDB cache
  keyed by engine version + canonical request), `queue.ts` (4-wide priority queue; selected row
  and the drill's pair jump the line), `hooks.ts`, `cells.ts`.
- `src/lib/store/` — Zustand stores with `persist(..., { skipHydration: true })` and
  `useRehydrateStores()` in `Providers` (persisted state must NOT be in the first client render,
  or React throws hydration error #418); shared slices are mirrored to `settings` via
  `startSettingsSync` (last writer wins on `updatedAt`). `session.ts` (key/position from the
  practice-day query; tempo, meter, click, volumes, count-in, theme), `connections.ts` (setup +
  per-pickKey curation `{unkept, deleted}` — "no saved pick = everything kept"; kept = ALL loaded
  pairs − unkept, never the filtered view), `lines.ts` (its OWN `movement` key), `home.ts`,
  `score.ts`, `pentatonics.ts`, `triads.ts`.
- `src/lib/audio/` — the ONE `AudioContext` (`engine.ts` singleton): Worker-timed scheduler
  (25 ms tick, 100 ms lookahead), click (1000/800 Hz blips) and triangle play-along voices
  identical to `render_html`, count-in, patterns looping on whole click bars, switched at the
  next bar, cues; `pattern.ts` builds patterns from `placed[]`; unlocked on the first
  pointerdown/keydown (`useAudioUnlock` in `Providers`).
- `src/lib/drill/` — the resumable drill: `buildItems.ts` (kept pairs × kept fingerings sorted by
  cost; item id = `${pairKey}#${layout}` — split on the LAST `#`, cell names contain `#11`),
  `store.ts` (status idle/running/paused/finished; remaining time derived from an absolute
  deadline; `tick` auto-advances; a persisted running drill always comes back PAUSED; fingerings
  live in a non-persisted registry `registerFingerings`), `sync.ts` (PUT `/api/drill/connections`
  debounced 2 s / immediately on status change; adopts a NEWER remote state from another device,
  paused, and never writes back what it adopted), `wakeLock.ts`.
- `src/components/tab/` — `TabSvg` (pure; `src/lib/tab/geometry.ts` = render.py), `TabPlayer`
  (playhead follows the engine's `note` events for its `patternId`; `followTransport` for the
  drill), `NoteTable`, `FullReport` (the API's report text), `TabActions` (SVG download, copy
  encoding), `FingeringCard`. `src/lib/music/tabEncoding.ts` parses the legacy `5/3D 4/2D` form.
- Pages: `home/HomePage` (quiz, per-position tabs, pivot exercises), `connections/*`
  (SetupPanel, streamed ConnectionsTable + LoadProgress, FingeringList with Delete/Restore/
  Keep-only/Show-deleted and "load every layout" per box, `ConnectionsPage` orchestrates picks
  autosave + the drill), `drill/*` (DrillPanel = desktop right column / phone bottom sheet with a
  72 px mini bar, DrillStrip, DrillController), `lines/LinesPage`, `score/ScorePage` (pdf.js in
  the browser → `/score/read-vision`), `pentatonics/*` (+ `RankTable` shared with triads),
  `triads/*`.
- Keyboard: Space play/pause, ←/→ prev/next, R restart item, L loop session, M mute click,
  T show tab (ignored in inputs).

## Data & persistence
- `data/sampling/*.csv`, `data/pentatonics/bergonzi_patterns.json` — versioned sources of truth.
- `data/logs/` — git-ignored: only the local dev database (`bebop.db`) lives here now.
- `data/scores/` — the legacy score library files (versioned; imported into the `scores` table by
  `migrate_logs`; the app stores MusicXML in the DB from now on).
- `tests/golden/responses/*.json` — golden API fixtures (also usable as frontend fixtures).
- `archive/` — the retired JSON pipeline, reference only.
- Secrets: `.env.local` (git-ignored) — `APP_PASSWORD`, `AUTH_SECRET`, `ENGINE_API_KEY`
  (= `BEBOP_API_KEY`), `ENGINE_URL`, `TURSO_*`, `ANTHROPIC_API_KEY`. Never commit them.

## Deploy
Vercel Hobby (root dir = repo root; Python 3.12 function from `api/index.py`; env vars from
`.env.example`; leave `ENGINE_URL` unset so the app calls its own origin) + Turso
(`npm run db:push`, then `npm run migrate:logs`). The `nextjs-migration` branch is the
production target until merged. Fallback: the API in a container on Fly.io (`fly deploy`),
then `ENGINE_URL=https://<app>.fly.dev`. See README.md for the step list.

## Carry-over bugs fixed by design (do not reproduce)
Home pivot options from an unordered set; page-1 crash when page 2 left `movement = "A and N"`
(stores have their own keys); page-1 Save dropping kept rows hidden by the max cost; page-2 batch
selection overwriting the current fingering; "Major x Dominant" re-rolling every rerun (the API
returns the rolled structure); `Tab file` relative to CWD (tabs are JSON in the DB); Start/Last
note char slicing; score page re-parsing MusicXML every rerun; an unplayable row hiding the
library; the blocking `time.sleep` drill; the engine aliasing bug; KeyError on untranslatable
tokens; CSV re-reads per call.
