"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Checkbox, Field, NumberStepper, Select, Slider, Switch } from "@/components/ui/field";
import { Card, Info, Spinner, toast } from "@/components/ui/misc";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { usePageSettings } from "@/components/layout/PageSettings";
import { engineGet, enginePost } from "@/lib/engine/client";
import type { GenerateJSON, PatternsJSON, RankJSON } from "@/lib/engine/types";
import { POSITIONS, PRACTICE_KEYS } from "@/lib/music/constants";
import { useRankAcrossStarts } from "@/lib/pentatonics/useRank";
import { pickPentaSettings, usePenta, DEFAULT_WEIGHTS } from "@/lib/store/pentatonics";
import { useSession } from "@/lib/store/session";
import { startSettingsSync } from "@/lib/store/sync";
import { RankTable, WeightsEditor } from "./RankTable";

function PageOptions({ pats }: { pats: PatternsJSON | undefined }) {
  const s = usePenta();
  const todayKey = useSession((x) => x.key);
  const position = useSession((x) => x.position);
  const degrees = pats?.pentatonics[s.penta]?.degrees ?? [];
  return (
    <div className="space-y-3">
      <Field label="Key">
        <Select value={s.keyOverride ?? ""} onChange={(e) => s.set({ keyOverride: e.target.value || null })}>
          <option value="">Today&apos;s key ({todayKey})</option>
          {PRACTICE_KEYS.map((k) => (
            <option key={k} value={k}>
              {k}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Pentatonic">
        <Select value={s.penta} onChange={(e) => s.set({ penta: e.target.value, startDegs: [] })}>
          {(pats?.names ?? ["minor", "major", "minor6", "dominant"]).map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Starting note(s) — none = explore all">
        <div className="flex flex-wrap gap-1.5">
          {degrees.map((d, i) => {
            const on = s.startDegs.includes(i);
            return (
              <button key={i} type="button" onClick={() => s.set({ startDegs: on ? s.startDegs.filter((x) => x !== i) : [...s.startDegs, i].sort() })} className={`rounded-full border px-2.5 py-1 text-xs ${on ? "border-accent bg-accent-soft text-accent" : "bg-bg-elev text-fg-muted"}`}>
                {d}
              </button>
            );
          })}
        </div>
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Octaves">
          <NumberStepper ariaLabel="Octaves" value={s.nOctaves} onChange={(v) => s.set({ nOctaves: v })} min={1} max={3} />
        </Field>
        <Field label="Lowest octave">
          <NumberStepper ariaLabel="Lowest octave" value={s.lowOctave} onChange={(v) => s.set({ lowOctave: v })} min={1} max={4} />
        </Field>
      </div>
      <Switch checked={s.enforce} onCheckedChange={(v) => s.set({ enforce: v })} label={s.enforce ? `Enforce today's position (${POSITIONS[position - 1]}, ±${pats?.position_slack ?? 1} fret)` : "Compare every fingering system"} />
      <Field label={`Max fingering cost: ${s.maxCost}`}>
        <Slider min={0} max={200} step={1} value={s.maxCost} onChange={(e) => s.set({ maxCost: Number(e.target.value) })} />
      </Field>
      <details>
        <summary className="cursor-pointer text-sm">Fingering cost weights</summary>
        <div className="mt-2">
          <WeightsEditor weights={s.weights} onChange={(w) => s.set({ weights: w })} />
          <Button size="sm" variant="ghost" className="mt-1" onClick={() => s.set({ weights: DEFAULT_WEIGHTS })}>
            reset
          </Button>
        </div>
      </details>
    </div>
  );
}

export function PentatonicsPage() {
  const s = usePenta();
  const todayKey = useSession((x) => x.key);
  const position = useSession((x) => x.position);
  const key = s.keyOverride ?? todayKey;
  const enforced = s.enforce ? POSITIONS[position - 1] : null;
  const pats = useQuery({ queryKey: ["engine", "pentatonics/patterns"], queryFn: () => engineGet<PatternsJSON>("pentatonics/patterns"), staleTime: Infinity });
  React.useEffect(() => startSettingsSync(usePenta, "pentatonics", pickPentaSettings), []);
  usePageSettings(<PageOptions pats={pats.data} />, [pats.data]);
  const [result, setResult] = React.useState<GenerateJSON | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [ranked, setRanked] = React.useState<{ name: string; cpn: number | null; where: string; gen: GenerateJSON }[] | null>(null);

  const genBody = React.useCallback(
    (formula?: string) => ({
      key, penta: s.penta, exercise: s.exercise, direction: s.direction, n_octaves: s.nOctaves, low_octave: s.lowOctave, start_degs: s.startDegs.length ? s.startDegs : null, x: s.x, add_b6: s.addB6,
      formula: formula ?? s.formula ?? pats.data?.patterns[0]?.name ?? null, shift_choice: s.shiftChoice === "none" ? null : s.shiftChoice, groups_per_shift: s.groupsPerShift, n_shifts: s.nShifts, interval_name: s.intervalName ?? pats.data?.shift_choices[2] ?? null,
    }),
    [key, s, pats.data],
  );

  async function generate() {
    setBusy(true);
    try {
      setResult(await enginePost<GenerateJSON>("pentatonics/generate", genBody()));
    } catch (e) {
      toast((e as Error).message, "danger");
    } finally {
      setBusy(false);
    }
  }

  async function rankAll() {
    if (!pats.data) return;
    setBusy(true);
    try {
      const out: { name: string; cpn: number | null; where: string; gen: GenerateJSON }[] = [];
      for (const p of pats.data.patterns) {
        const gen = await enginePost<GenerateJSON>("pentatonics/generate", { ...genBody(p.name), exercise: "bergonzi" });
        const line = Object.values(gen.lines_by_start)[0] ?? [];
        const rk = await enginePost<RankJSON>("pentatonics/rank", { key, line, position: enforced, penta: s.penta, root: key, group: gen.group, config: s.weights });
        const feas = rk.rows.filter((r) => r.fingering);
        // fullest coverage first, then cheapest per note — a cheap fragment must not win
        const best = feas.sort((a, b) => b.covered - a.covered || (a.cpn ?? 0) - (b.cpn ?? 0))[0];
        out.push({ name: p.name, cpn: best ? best.cpn : null, where: best?.where ?? "—", gen });
      }
      out.sort((a, b) => Number(a.cpn === null) - Number(b.cpn === null) || (a.cpn ?? 0) - (b.cpn ?? 0));
      setRanked(out);
    } catch (e) {
      toast((e as Error).message, "danger");
    } finally {
      setBusy(false);
    }
  }

  const rank = useRankAcrossStarts(result ? { key, lines_by_start: result.lines_by_start, position: enforced, penta: s.penta, root: key, group: result.group, weights: s.weights } : null);
  const directions = pats.data?.directions ?? ["ascending", "descending", "both"];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Pentatonic practice</h1>
        <p className="text-xs text-fg-muted">Scale runs, chromaticism, Bergonzi shapes and shifting — each fingered by the Gypsy-jazz optimizer and ranked by cost across neck positions and run styles. Key, pentatonic and starting notes live in the settings sheet (gear).</p>
      </div>
      {pats.error && <Info tone="danger">{(pats.error as Error).message}</Info>}
      <Card className="space-y-3">
        <div className="flex flex-wrap gap-1.5">
          {(pats.data?.exercises ?? []).map((ex) => (
            <button key={ex.id} type="button" onClick={() => s.set({ exercise: ex.id as typeof s.exercise })} className={`rounded-full border px-3 py-1.5 text-sm ${s.exercise === ex.id ? "border-accent bg-accent-soft text-accent" : "bg-bg-elev"}`}>
              {ex.label}
            </button>
          ))}
        </div>
        <p className="text-xs text-fg-muted">
          {key} {s.penta} · {s.nOctaves} oct from octave {s.lowOctave} · {s.startDegs.length ? `start on ${s.startDegs.map((i) => pats.data?.pentatonics[s.penta]?.degrees[i]).join(", ")}` : "all starting notes"} · {enforced ?? "every system"}
        </p>
        <div className="grid gap-3 sm:grid-cols-3">
          {s.exercise !== "bergonzi" && (
            <Field label="Direction">
              <Select value={s.direction} onChange={(e) => s.set({ direction: e.target.value })}>
                {directions.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </Select>
            </Field>
          )}
          {s.exercise === "pattern" && (
            <Field label="Notes per group (x)" hint="Groups of x consecutive pentatonic notes, each starting one scale note after the previous (1-2-3-4, 2-3-4-5, …).">
              <NumberStepper ariaLabel="Notes per group" value={s.x} onChange={(v) => s.set({ x: v })} min={2} max={8} />
            </Field>
          )}
          {s.exercise === "chromatic" && (
            <Field label="Passing tones" hint="Fills each whole-step gap with a passing tone (minor: 1-b3-3-4-#4-5-b7-7).">
              <Checkbox label="Add b6 (also fill the 5→b7 gap)" checked={s.addB6} onChange={(e) => s.set({ addB6: e.target.checked })} />
            </Field>
          )}
          {s.exercise === "bergonzi" && (
            <>
              <Field label="Formula" hint="Formulas 1-4 descend, 5-8 ascend; they define their own start.">
                <Select value={s.formula ?? pats.data?.patterns[0]?.name ?? ""} onChange={(e) => s.set({ formula: e.target.value })}>
                  {(pats.data?.patterns ?? []).map((p) => (
                    <option key={p.name} value={p.name}>
                      {p.name}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Shift the formula (side-slip)">
                <Select value={s.shiftChoice} onChange={(e) => s.set({ shiftChoice: e.target.value })}>
                  <option value="none">No shift — sweep the scale</option>
                  {(pats.data?.shift_choices ?? []).map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </Select>
              </Field>
              {s.shiftChoice !== "none" && (
                <div className="grid grid-cols-2 gap-2">
                  <Field label="Groupings before each shift">
                    <NumberStepper ariaLabel="Groupings per shift" value={s.groupsPerShift} onChange={(v) => s.set({ groupsPerShift: v })} min={1} max={6} />
                  </Field>
                  <Field label="Key shifts">
                    <NumberStepper ariaLabel="Key shifts" value={s.nShifts} onChange={(v) => s.set({ nShifts: v })} min={1} max={8} />
                  </Field>
                </div>
              )}
            </>
          )}
          {s.exercise === "shifting" && (
            <>
              <Field label="Shift interval / cycle">
                <Select value={s.intervalName ?? pats.data?.shift_choices[2] ?? ""} onChange={(e) => s.set({ intervalName: e.target.value })}>
                  {(pats.data?.shift_choices ?? []).map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Number of key shifts">
                <NumberStepper ariaLabel="Key shifts" value={s.nShifts} onChange={(v) => s.set({ nShifts: v })} min={1} max={8} />
              </Field>
            </>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button onClick={generate} disabled={busy || !pats.data}>
            {busy ? <Spinner /> : null} Generate
          </Button>
          {s.exercise === "bergonzi" && (
            <Button variant="outline" onClick={rankAll} disabled={busy || !pats.data}>
              Rank ALL formulas easiest → hardest
            </Button>
          )}
        </div>
      </Card>

      {ranked && (
        <Card className="space-y-2">
          <h2 className="text-base font-semibold">Formulas ranked by playability</h2>
          <Table>
            <thead>
              <tr>
                <Th>Formula</Th>
                <Th className="text-right">Cost/note</Th>
                <Th>Played at</Th>
              </tr>
            </thead>
            <tbody>
              {ranked.map((r) => (
                <Tr key={r.name} selected={result?.title === r.gen.title} onClick={() => setResult(r.gen)}>
                  <Td>{r.name}</Td>
                  <Td className="text-right tabular-nums">{r.cpn === null ? "—" : r.cpn.toFixed(2)}</Td>
                  <Td className="max-w-[18rem] truncate">{r.where}</Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}

      {result && <RankTable title={result.title} rows={rank.rows} done={rank.done} total={rank.total} enforced={enforced} maxCost={s.maxCost} multi={rank.multi} slack={pats.data?.position_slack ?? 1} keyName={key} styleFilter={s.styleFilter} onStyleFilter={(f) => s.set({ styleFilter: f })} filename="pentatonic_tab.svg" />}
      {rank.errors.length > 0 && <Info tone="danger">{rank.errors[0]}</Info>}
    </div>
  );
}
