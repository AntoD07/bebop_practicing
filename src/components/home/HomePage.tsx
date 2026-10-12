"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Checkbox, Field, Input, Select } from "@/components/ui/field";
import { Badge, Card, Info, Skeleton } from "@/components/ui/misc";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { FingeringCard } from "@/components/tab/FingeringCard";
import { usePageSettings } from "@/components/layout/PageSettings";
import { translationFor, useCells } from "@/lib/engine/cells";
import { enginePost } from "@/lib/engine/client";
import type { CellJSON, PositionsFingeringJSON } from "@/lib/engine/types";
import { CHORD_MODES, POSITIONS, POSITION_SHORT, PRACTICE_KEYS, degreeSortKey, joinNotes } from "@/lib/music/constants";
import { useHome } from "@/lib/store/home";
import { useSession } from "@/lib/store/session";
import { cn, fmtCost } from "@/lib/utils";

function normalizeAnswer(s: string): string {
  return s
    .trim()
    .split(/[\s,-]+/)
    .filter(Boolean)
    .join("-");
}

export function HomePage() {
  const home = useHome();
  const todayKey = useSession((s) => s.key);
  const todayPosition = useSession((s) => s.position);
  const key = home.fingeringKey ?? todayKey;
  const translate = translationFor(home.mode, home.domToMinor);
  const cellsQ = useCells(home.mode, home.bonus, translate);
  const cells = React.useMemo(() => (cellsQ.data?.cells ?? []).filter((c) => !c.error), [cellsQ.data]);

  // The chosen cell: an explicit pick, else a random draw (the seed changes on
  // "Randomize"; a new mode falls back to the draw since the old id is gone).
  const [cellId, setCellId] = React.useState<string | null>(null);
  const [seed, setSeed] = React.useState(() => Math.random());
  const cell = React.useMemo(() => cells.find((c) => c.id === cellId) ?? (cells.length ? cells[Math.floor(seed * cells.length) % cells.length] : null), [cells, cellId, seed]);

  usePageSettings(
    <div className="space-y-3">
      <Checkbox label="Include bonus cells" checked={home.bonus} onChange={(e) => home.set({ bonus: e.target.checked })} />
      <Field label="Key for the fingering tabs (defaults to today's key)">
        <Select value={home.fingeringKey ?? ""} onChange={(e) => home.set({ fingeringKey: e.target.value || null })}>
          <option value="">Today&apos;s key ({todayKey})</option>
          {PRACTICE_KEYS.map((k) => (
            <option key={k} value={k}>
              {k}
            </option>
          ))}
        </Select>
      </Field>
    </div>,
    [home.bonus, home.fingeringKey, todayKey],
  );

  function randomize() {
    setCellId(null);
    setSeed(Math.random());
  }

  return (
    <div className="space-y-6">
      <section className="space-y-3">
        <h1 className="text-xl font-semibold">Cell quiz</h1>
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Chord to practice">
            <Select value={home.mode} onChange={(e) => home.set({ mode: e.target.value })} className="w-52">
              {CHORD_MODES.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </Select>
          </Field>
          {(home.mode === "MinorResolutions" || home.mode === "Locrian") && (
            <Checkbox label="Translate Dominant to Minor-I" checked={home.domToMinor} onChange={(e) => home.set({ domToMinor: e.target.checked })} />
          )}
          <Button variant="outline" onClick={randomize} disabled={!cells.length}>
            Randomize again
          </Button>
        </div>
        {cellsQ.isLoading && <Skeleton className="h-24" />}
        {cellsQ.error && <Info tone="danger">Could not load the cells: {(cellsQ.error as Error).message}</Info>}
        {cell && <QuizCard key={cell.id} cell={cell} cells={cells} onPick={setCellId} />}
      </section>

      {cell && <PositionTabs cell={cell} mode={home.mode} fingeringKey={key} domToMinor={home.domToMinor} todayPosition={todayPosition} />}

      {cells.length > 0 && <PivotExercises cells={cells} />}
    </div>
  );
}

function QuizCard({ cell, cells, onPick }: { cell: CellJSON; cells: CellJSON[]; onPick: (id: string) => void }) {
  const [answer, setAnswer] = React.useState("");
  const [verdict, setVerdict] = React.useState<"ok" | "ko" | null>(null);
  const [showSolution, setShowSolution] = React.useState(false);
  function submit(e: React.FormEvent) {
    e.preventDefault();
    setVerdict(normalizeAnswer(answer) === joinNotes(cell.degrees) ? "ok" : "ko");
  }
  return (
    <Card className="space-y-3">
      <Field label="Refresh memory on any cell">
        <Select value={cell.id} onChange={(e) => onPick(e.target.value)}>
          {cells.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </Select>
      </Field>
      <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
        <Field label="Cell notes (degrees, w.r.t. the chord)" className="min-w-48 flex-1">
          <Input value={answer} onChange={(e) => setAnswer(e.target.value)} placeholder="e.g. 1 3 5 7 6" autoCapitalize="none" autoCorrect="off" />
        </Field>
        <Button type="submit">Submit</Button>
        <Button type="button" variant="ghost" onClick={() => setShowSolution((v) => !v)}>
          {showSolution ? "Hide solution" : "See solution"}
        </Button>
      </form>
      {verdict === "ok" && <Info tone="ok">Good answer!</Info>}
      {verdict === "ko" && <Info tone="danger">Incorrect!</Info>}
      {showSolution && (
        <p className="font-mono text-sm">
          {joinNotes(cell.degrees)} <Badge className="ml-2">{cell.movement ?? "?"}</Badge>
          {cell.nominal_mismatch && (
            <Badge tone="warn" className="ml-2">
              Start/End ≠ Notes
            </Badge>
          )}
        </p>
      )}
    </Card>
  );
}

function PositionTabs({ cell, mode, fingeringKey, domToMinor, todayPosition }: { cell: CellJSON; mode: string; fingeringKey: string; domToMinor: boolean; todayPosition: number }) {
  const q = useQuery({
    queryKey: ["engine", "fingering/positions", fingeringKey, mode, cell.id, domToMinor],
    queryFn: () => enginePost<PositionsFingeringJSON>("fingering/positions", { key: fingeringKey, mode, cell: { id: cell.id }, dom_to_minor: domToMinor }),
    staleTime: Infinity,
  });
  const [octave, setOctave] = React.useState<Record<string, number>>({});
  const todayName = POSITIONS[todayPosition - 1];
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold">
        Fingering for <span className="text-accent">{cell.name}</span> <span className="text-fg-muted">({fingeringKey} {mode})</span>
      </h2>
      <p className="text-xs text-fg-muted">Pitches fixed by the cell; the solver finds each position&apos;s layout and derives Gypsy picking (⊓ rest-stroke down, ∨ parity upstroke). ⭐ today&apos;s focus position; tabs ranked by cost, hardest first.</p>
      {q.isLoading && <Skeleton className="h-40" />}
      {q.error && <Info tone="danger">{(q.error as Error).message}</Info>}
      {q.data && (
        <Tabs defaultValue={q.data.positions[0]?.name}>
          <TabsList className="h-auto w-full flex-wrap justify-start">
            {q.data.positions.map((p) => (
              <TabsTrigger key={p.name} value={p.name} className="flex-none text-xs">
                {p.name === todayName ? "⭐ " : ""}
                <span className="sm:hidden">{POSITION_SHORT[p.name as keyof typeof POSITION_SHORT]}</span>
                <span className="hidden sm:inline">{p.name}</span>
                <span className="ml-1 text-fg-muted">· {fmtCost(p.best_cost, 1)}</span>
              </TabsTrigger>
            ))}
          </TabsList>
          {q.data.positions.map((p) => {
            const idx = Math.min(octave[p.name] ?? 0, Math.max(0, p.octaves.length - 1));
            const o = p.octaves[idx];
            return (
              <TabsContent key={p.name} value={p.name} className="mt-3 space-y-2">
                {!o ? (
                  <Info tone="warn">This cell&apos;s range does not fit this position.</Info>
                ) : (
                  <>
                    <div className="flex flex-wrap items-center gap-2 text-sm">
                      <span className="text-fg-muted">Octave:</span>
                      <Select value={idx} onChange={(e) => setOctave((s) => ({ ...s, [p.name]: Number(e.target.value) }))} className="w-auto max-w-full">
                        {p.octaves.map((oo, i) => (
                          <option key={i} value={i}>
                            {oo.register} · cost {oo.cost.toFixed(2)}
                          </option>
                        ))}
                      </Select>
                    </div>
                    {o.note && <Info>{o.note}</Info>}
                    <FingeringCard fingering={o.fingering} caption={o.fingering.where} filename={`${cell.name}-${p.name}.svg`} />
                  </>
                )}
              </TabsContent>
            );
          })}
        </Tabs>
      )}
    </section>
  );
}

function PivotExercises({ cells }: { cells: CellJSON[] }) {
  const pivots = React.useMemo(() => {
    const set = new Set<string>();
    for (const c of cells) {
      set.add(c.start);
      set.add(c.end);
    }
    return Array.from(set).sort((a, b) => {
      const [ia, ta] = degreeSortKey(a);
      const [ib, tb] = degreeSortKey(b);
      return ia - ib || ta.localeCompare(tb);
    });
  }, [cells]);
  const [pivotState, setPivot] = React.useState<string | null>(null);
  const pivot = pivotState && pivots.includes(pivotState) ? pivotState : (pivots[0] ?? "1");
  const starting = cells.filter((c) => c.start === pivot);
  const ending = cells.filter((c) => c.end === pivot);
  const [showCells, setShowCells] = React.useState(false);
  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <Field label="Pivot note to practice">
          <Select value={pivot} onChange={(e) => setPivot(e.target.value)} className="w-28">
            {pivots.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </Select>
        </Field>
        <Button variant="ghost" onClick={() => setShowCells((v) => !v)}>
          {showCells ? "Hide cells" : "Show cells"}
        </Button>
      </div>
      {showCells && (
        <div className="grid gap-3 sm:grid-cols-2">
          <Card>
            <h3 className="mb-2 text-sm font-semibold">Ending on {pivot}</h3>
            <CellList cells={ending} />
          </Card>
          <Card>
            <h3 className="mb-2 text-sm font-semibold">Starting on {pivot}</h3>
            <CellList cells={starting} />
          </Card>
        </div>
      )}
      <Exercise key={`s${pivot}`} title={`Exercise 1 · cells starting on ${pivot}`} all={cells} correct={starting} />
      <Exercise key={`e${pivot}`} title={`Exercise 2 · cells ending on ${pivot}`} all={cells} correct={ending} />
    </section>
  );
}

function CellList({ cells }: { cells: CellJSON[] }) {
  if (!cells.length) return <p className="text-xs text-fg-muted">none</p>;
  return (
    <ul className="space-y-1 text-sm">
      {cells.map((c) => (
        <li key={c.id}>
          <span className="font-medium">{c.name}</span> <span className="font-mono text-fg-muted">{joinNotes(c.degrees)}</span> <Badge className="ml-1">{c.movement ?? "?"}</Badge>
        </li>
      ))}
    </ul>
  );
}

function Exercise({ title, all, correct }: { title: string; all: CellJSON[]; correct: CellJSON[] }) {
  const [picked, setPicked] = React.useState<Set<string>>(new Set());
  const [result, setResult] = React.useState<{ extras: string[]; missing: number } | null>(null);
  function verify() {
    const correctIds = new Set(correct.map((c) => c.id));
    const extras = Array.from(picked).filter((id) => !correctIds.has(id)).map((id) => all.find((c) => c.id === id)?.name ?? id);
    const missing = correct.filter((c) => !picked.has(c.id)).length;
    setResult({ extras, missing });
  }
  const ok = result && !result.extras.length && !result.missing;
  return (
    <Card className="space-y-2">
      <h3 className="text-sm font-semibold">{title}</h3>
      <div className="grid gap-1 sm:grid-cols-2">
        {all.map((c) => (
          <label key={c.id} className={cn("flex cursor-pointer items-center gap-2 rounded px-1 py-0.5 text-sm hover:bg-bg-muted", picked.has(c.id) && "bg-accent-soft")}>
            <input
              type="checkbox"
              className="accent-[var(--accent)]"
              checked={picked.has(c.id)}
              onChange={(e) =>
                setPicked((s) => {
                  const n = new Set(s);
                  if (e.target.checked) n.add(c.id);
                  else n.delete(c.id);
                  return n;
                })
              }
            />
            <span className="truncate">{c.name}</span>
          </label>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" onClick={verify}>
          Verify answer
        </Button>
        {ok && <Info tone="ok">Correct!</Info>}
        {result && !ok && (
          <Info tone="danger">
            {result.extras.length > 0 && <div>{result.extras.join(", ")} are not part of the correct answer.</div>}
            {result.missing > 0 && <div>{result.missing} missing.</div>}
          </Info>
        )}
      </div>
      {result && (
        <details className="text-sm">
          <summary className="cursor-pointer text-fg-muted">See solution</summary>
          <CellList cells={correct} />
        </details>
      )}
    </Card>
  );
}
