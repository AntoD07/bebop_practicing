"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Field, NumberStepper, Select, Slider, Switch } from "@/components/ui/field";
import { Card, Info, Spinner, toast } from "@/components/ui/misc";
import { Table, Td, Th } from "@/components/ui/table";
import { usePageSettings } from "@/components/layout/PageSettings";
import { engineGet, enginePost } from "@/lib/engine/client";
import type { GenerateJSON, TriadPairJSON } from "@/lib/engine/types";
import { POSITIONS, PRACTICE_KEYS } from "@/lib/music/constants";
import { useRankAcrossStarts } from "@/lib/pentatonics/useRank";
import { DEFAULT_WEIGHTS } from "@/lib/store/pentatonics";
import { useSession } from "@/lib/store/session";
import { startSettingsSync } from "@/lib/store/sync";
import { pickTriadsSettings, useTriads } from "@/lib/store/triads";
import { RankTable, WeightsEditor } from "@/components/pentatonics/RankTable";
import { NeckMap } from "./NeckMap";

const ROOTS = ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"];
const KEY_PC: Record<string, number> = { C: 0, Db: 1, D: 2, Eb: 3, E: 4, F: 5, "F#": 6, G: 7, Ab: 8, A: 9, Bb: 10, B: 11 };

function PageOptions({ pair }: { pair: TriadPairJSON | undefined }) {
  const s = useTriads();
  const todayKey = useSession((x) => x.key);
  const position = useSession((x) => x.position);
  const hexa = pair?.hexatonic ?? [];
  return (
    <div className="space-y-3">
      <Field label="Key (anchors the positions, seeds the pair)">
        <Select value={s.keyOverride ?? ""} onChange={(e) => s.set({ keyOverride: e.target.value || null })}>
          <option value="">Today&apos;s key ({todayKey})</option>
          {PRACTICE_KEYS.map((k) => (
            <option key={k} value={k}>
              {k}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Starting note(s) — none = explore all">
        <div className="flex flex-wrap gap-1.5">
          {hexa.map((t, i) => {
            const on = s.startDegs.includes(i);
            return (
              <button key={i} type="button" onClick={() => s.set({ startDegs: on ? s.startDegs.filter((x) => x !== i) : [...s.startDegs, i].sort() })} className={`rounded-full border px-2.5 py-1 text-xs ${on ? "border-accent bg-accent-soft text-accent" : "bg-bg-elev text-fg-muted"}`}>
                {t.name} ({t.label})
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
      <Switch checked={s.enforce} onCheckedChange={(v) => s.set({ enforce: v })} label={s.enforce ? `Enforce today's position (${POSITIONS[position - 1]}, ±${pair?.slack ?? 1} fret)` : "Rank Free and the five positions"} />
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

export function TriadsPage() {
  const s = useTriads();
  const todayKey = useSession((x) => x.key);
  const position = useSession((x) => x.position);
  const key = s.keyOverride ?? todayKey;
  const root1 = s.root1 ?? key;
  const root2 = s.root2 ?? ROOTS[(KEY_PC[key] + 2) % 12];
  const enforced = s.enforce ? POSITIONS[position - 1] : null;
  const mapName = POSITIONS[(s.mapPosition ?? position) - 1];
  const pairQ = useQuery({ queryKey: ["engine", "triads/pair", root1, s.quality1, root2, s.quality2, key], queryFn: () => engineGet<TriadPairJSON>("triads/pair", { root1, quality1: s.quality1, root2, quality2: s.quality2, key, max_fret: 15 }), staleTime: Infinity });
  const pair = pairQ.data;
  React.useEffect(() => startSettingsSync(useTriads, "triads", pickTriadsSettings), []);
  usePageSettings(<PageOptions pair={pair} />, [pair]);
  const [result, setResult] = React.useState<GenerateJSON | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [showAll, setShowAll] = React.useState(false);

  async function generate() {
    setBusy(true);
    try {
      const out = await enginePost<GenerateJSON>("triads/generate", { root1, quality1: s.quality1, root2, quality2: s.quality2, exercise: s.exercise, direction: s.exercise === "alternating" ? s.altDirection : s.scaleDirection, n_octaves: s.nOctaves, low_octave: s.lowOctave, x: s.exercise === "alternating" ? s.xAlt : s.x, start_degs: s.startDegs.length ? s.startDegs : null });
      if (out.message) toast(out.message, "danger");
      setResult(out);
    } catch (e) {
      toast((e as Error).message, "danger");
    } finally {
      setBusy(false);
    }
  }

  const rank = useRankAcrossStarts(result ? { key, lines_by_start: result.lines_by_start, position: enforced, group: result.group, weights: s.weights, generic: true } : null);
  const qualities = pair?.constants.qualities ?? ["major", "minor", "diminished", "augmented", "sus4", "sus2"];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Triad pairs &amp; hexatonics</h1>
        <p className="text-xs text-fg-muted">Two triads, one hexatonic scale: see the pair on the whole neck and in position, then practise the scale, its x-notes groupings and the alternating-triad groupings — each fingered by the Gypsy-jazz optimizer and ranked by cost.</p>
      </div>
      <Card className="space-y-3">
        <div className="grid gap-3 sm:grid-cols-4">
          <Field label="Triad 1 root">
            <Select value={root1} onChange={(e) => s.set({ root1: e.target.value, startDegs: [] })}>
              {ROOTS.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Triad 1 quality">
            <Select value={s.quality1} onChange={(e) => s.set({ quality1: e.target.value, startDegs: [] })}>
              {qualities.map((q) => (
                <option key={q} value={q}>
                  {q}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Triad 2 root">
            <Select value={root2} onChange={(e) => s.set({ root2: e.target.value, startDegs: [] })}>
              {ROOTS.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Triad 2 quality">
            <Select value={s.quality2} onChange={(e) => s.set({ quality2: e.target.value, startDegs: [] })}>
              {qualities.map((q) => (
                <option key={q} value={q}>
                  {q}
                </option>
              ))}
            </Select>
          </Field>
        </div>
        {pairQ.isLoading && <Spinner />}
        {pairQ.error && <Info tone="danger">{(pairQ.error as Error).message}</Info>}
        {pair && (
          <>
            <h2 className="text-base font-semibold">{pair.title}</h2>
            {pair.identical && <Info tone="warn">Both triads are identical — pick a different second triad.</Info>}
            <p className="text-sm">
              <strong>Hexatonic:</strong> {pair.hexatonic_names.join(" ")} · roots {pair.interval_name} · {pair.common.length ? `shared tone(s): ${pair.common.join(", ")} (${pair.hexatonic.length} distinct notes)` : "no common tone — a true six-note hexatonic"}
            </p>
            <details>
              <summary className="cursor-pointer text-sm text-fg-muted">Tones of the pair</summary>
              <Table className="mt-2">
                <thead>
                  <tr>
                    <Th>Note</Th>
                    <Th>Triad(s)</Th>
                    <Th>Degree(s)</Th>
                  </tr>
                </thead>
                <tbody>
                  {pair.hexatonic.map((t) => (
                    <tr key={t.pc}>
                      <Td>{t.name}</Td>
                      <Td>{t.triads.map((i) => pair.triads[i].symbol).join(" / ")}</Td>
                      <Td>{t.labels.map((l) => l.split(":")[1]).join(" / ")}</Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </details>
          </>
        )}
      </Card>

      {pair && (
        <Card className="space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-base font-semibold">On the whole neck</h2>
            <Select value={s.labels} onChange={(e) => s.set({ labels: e.target.value as "name" | "degree" })} className="w-36">
              <option value="name">Note names</option>
              <option value="degree">Triad degrees</option>
            </Select>
          </div>
          <NeckMap pair={pair} labels={s.labels} />
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-base font-semibold">In position</h2>
            <Select value={s.mapPosition ?? position} onChange={(e) => s.set({ mapPosition: Number(e.target.value) })} className="w-64">
              {POSITIONS.map((p, i) => (
                <option key={p} value={i + 1}>
                  {i + 1} · {p}
                </option>
              ))}
            </Select>
            <Button size="sm" variant="ghost" onClick={() => setShowAll((v) => !v)}>
              {showAll ? "Hide the other positions" : "All five positions"}
            </Button>
          </div>
          <NeckMap pair={pair} boxes={pair.boxes[mapName]} labels={s.labels} slack={pair.slack} title={`${mapName} · box on ${key}`} />
          <p className="text-xs text-fg-muted">Solid box = the hand position anchored on {key} (both octaves of the shape when the upper one is on the neck); dashed = the ±{pair.slack}-fret tolerance the position exercises accept; faded tones lie outside. Open strings are shown but never fingered.</p>
          {showAll && POSITIONS.filter((p) => p !== mapName).map((p) => <NeckMap key={p} pair={pair} boxes={pair.boxes[p]} labels={s.labels} slack={pair.slack} title={`${p} · box on ${key}`} />)}
        </Card>
      )}

      {pair && (
        <Card className="space-y-3">
          <h2 className="text-base font-semibold">Exercises</h2>
          <div className="flex flex-wrap gap-1.5">
            {[
              ["scale", "Hexatonic scale run"],
              ["pattern", "x-notes grouping (hexatonic)"],
              ["alternating", "Alternating triads (x-notes grouping)"],
            ].map(([id, label]) => (
              <button key={id} type="button" onClick={() => s.set({ exercise: id as typeof s.exercise })} className={`rounded-full border px-3 py-1.5 text-sm ${s.exercise === id ? "border-accent bg-accent-soft text-accent" : "bg-bg-elev"}`}>
                {label}
              </button>
            ))}
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            {s.exercise !== "alternating" ? (
              <Field label="Direction">
                <Select value={s.scaleDirection} onChange={(e) => s.set({ scaleDirection: e.target.value })}>
                  {pair.constants.scale_directions.map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </Select>
              </Field>
            ) : (
              <Field label="Direction">
                <Select value={s.altDirection} onChange={(e) => s.set({ altDirection: e.target.value })}>
                  {pair.constants.alternating_directions.map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </Select>
              </Field>
            )}
            {s.exercise === "pattern" && (
              <Field label="Notes per group (x)">
                <NumberStepper ariaLabel="Notes per group" value={s.x} onChange={(v) => s.set({ x: v })} min={2} max={8} />
              </Field>
            )}
            {s.exercise === "alternating" && (
              <Field label="Notes per group (x)">
                <NumberStepper ariaLabel="Notes per group" value={s.xAlt} onChange={(v) => s.set({ xAlt: v })} min={2} max={8} />
              </Field>
            )}
          </div>
          <p className="text-xs text-fg-muted">
            {s.exercise === "scale" && "The six notes played as a scale, straight through."}
            {s.exercise === "pattern" && `Groups of ${s.x} consecutive hexatonic notes, each starting one scale note after the previous (1-2-3-4, 2-3-4-5, …); descending runs the same from the top.`}
            {s.exercise === "alternating" && `Groups of ${s.xAlt} arpeggio tones alternating ${pair.triads[0].symbol} / ${pair.triads[1].symbol}, each group starting on the next tone of its own triad — the inversions walk through the range. Ascending: every group up; descending: from the top; alternating ↑↓: one triad up, the other down from the next tone above, the pairs climbing; alternating ↓↑: the mirror, falling.`}
          </p>
          <Button onClick={generate} disabled={busy}>
            {busy ? <Spinner /> : null} Generate
          </Button>
        </Card>
      )}

      {result && <RankTable title={result.title} rows={rank.rows} done={rank.done} total={rank.total} enforced={enforced} maxCost={s.maxCost} multi={rank.multi} slack={pair?.slack ?? 1} keyName={key} styleFilter={s.styleFilter} onStyleFilter={(f) => s.set({ styleFilter: f })} filename="triad_pair_tab.svg" />}
      {rank.errors.length > 0 && <Info tone="danger">{rank.errors[0]}</Info>}
    </div>
  );
}
