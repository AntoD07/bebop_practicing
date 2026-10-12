# Bebop Practicing

A single-user guitar practice app for bebop improvisation: memorising melodic **cells**,
drilling how they **connect** at pivot notes, generating **melodic lines**, pentatonic and
triad-pair exercises, and reading scores — every line rendered as a Gypsy-jazz
**fingering tab** (string/fret/finger/picking) with a native metronome and play-along.

It is a **Next.js 16** app (phone + laptop, installable as a PWA) in front of a **Python
compute API** (FastAPI) that wraps the fingering engine. Both deploy as ONE Vercel project;
state (today's key, curated connections, saved lines, drill progress) lives in **Turso**
(libSQL) so every device sees the same thing.

```
src/                 Next.js app (App Router, TypeScript, Tailwind v4)
api/                 FastAPI compute API  (api/index.py = the Vercel Python function)
scripts/fingering/   the fingering engine (Viterbi/DP), unchanged domain logic
scripts/domain/      pure-stdlib cell catalog, translations, pairing, sampling, lines
scripts/pentatonics/ scripts/triad_pairs/   exercise generators + rankers
data/sampling/*.csv  the cell library — the hand-edited source of truth
tests/               pytest (API) + golden fixtures; e2e/ Playwright specs
```

## Run it locally

```bash
# once
uv sync                       # Python 3.12 venv with the API deps (+ pytest, uvicorn)
npm install                   # Node 24; also copies pdf.js's worker into public/
cp .env.example .env.local    # set APP_PASSWORD, AUTH_SECRET, ENGINE_API_KEY (= BEBOP_API_KEY)

# every time: two processes
BEBOP_API_KEY=<same as ENGINE_API_KEY> uv run uvicorn api.index:app --port 8000 --reload
npm run dev                   # http://localhost:3000 — sign in with APP_PASSWORD
```

Without `TURSO_DATABASE_URL` the app uses a local libSQL file (`data/logs/bebop.db`, created
on first use). `./scripts/dev_preview.sh` starts both servers plus a public cloudflared
tunnel for a quick phone check.

## Tests

```bash
python -m scripts.fingering.tests          # engine T1–T9 (run after touching costs/optimizer/picking)
BEBOP_DEV=1 uv run pytest tests/api -q     # API: auth, catalog, connections, lines, golden…
uv run python -m scripts.golden.dump --update   # refresh tests/golden/responses after an intended engine change
uv run python -m scripts.golden.bench      # 2400 random connection requests, every one < 3.5 s
npm run typecheck && npm run lint && npm test   # TS, ESLint, Vitest (stores, geometry, pick keys…)
npm run build && npm run e2e               # Playwright: login + drill resume (needs the API running)
```

## Deploy (Vercel Hobby + Turso, $0/month)

1. **Turso**: `turso db create bebop` → `turso db show bebop --url` and
   `turso db tokens create bebop` give `TURSO_DATABASE_URL` / `TURSO_AUTH_TOKEN`.
2. **Vercel**: import the repo (root directory = repo root; the Python function is detected
   from `api/index.py` + `vercel.json`). Set the environment variables from `.env.example`:
   `APP_PASSWORD`, `AUTH_SECRET` (long random), `ENGINE_API_KEY` and `BEBOP_API_KEY` (the same
   value), `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`, optionally `ANTHROPIC_API_KEY` (score
   reader) and `BEBOP_ALLOWED_ORIGINS=https://<your-app>.vercel.app`. Leave `ENGINE_URL` unset
   on Vercel (the app calls its own origin). Point production at the `nextjs-migration` branch
   until it is merged.
3. **Schema + data**: `npm run db:push` (drizzle-kit) with the Turso variables exported, then
   `LEGACY_ROOT=/path/to/old/checkout npm run migrate:logs` to import `data/logs/*` and
   `data/scores/*` (the tables are also created lazily on first use).
4. Install on the phone from the browser's "Add to Home Screen" — it opens on `/connections`.

Fallback for the API (if Hobby's CPU hours ever bite): `fly launch` with the included
`Dockerfile` / `fly.toml`, then set `ENGINE_URL=https://<app>.fly.dev` on Vercel.

## The cell library is the CSVs

`data/sampling/<Mode>_sampling.csv` (`Maj7`, `Minor`, `Dorian`, `Myxolidian`, `Locrian`,
`MajorResolutions`, `MinorResolutions`, `7sus4`) are the hand-edited source of truth. Columns:
`Cell Name`, `Start Note`, `End Note`, `Notes` (degree list), `Movement` (A/D/N), `Type`
(Essential/Bonus). Cells are **scale-degree strings** (chord tones `1/3/5/7`, extensions
`9/11/6`, alterations `b7/#11/b9/#9/b6`); two cells connect when one's `End Note` equals the
next's `Start Note` (the *pivot*). Edit the CSVs and restart the API: cell ids are content
hashes, data oddities (Start/End ≠ Notes, duplicate names) are listed by `GET /api/py/health`.
