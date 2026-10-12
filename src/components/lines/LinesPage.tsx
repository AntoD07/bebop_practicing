"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { Checkbox, Field, Input, NumberStepper, Select, Slider, Switch } from "@/components/ui/field";
import { Badge, Card, Info, Skeleton, Spinner, toast } from "@/components/ui/misc";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { FingeringCard } from "@/components/tab/FingeringCard";
import { TabPlayer } from "@/components/tab/TabPlayer";
import { usePageSettings } from "@/components/layout/PageSettings";
import { enginePost } from "@/lib/engine/client";
import type { FingeringJSON, SampleJSON, SampledLineJSON } from "@/lib/engine/types";
import { useBatchFingerings, useDeleteLine, useLineFingerings, useLineSetup, useSampleOne, useSaveLine, useSavedLines, type SavedLine } from "@/lib/lines/useLines";
import { CHORD_TONES, LINE_TYPES, NOTE_OPTIONS } from "@/lib/music/constants";
import { placedFromEncoding } from "@/lib/music/tabEncoding";
import { useLines, type LineMovement } from "@/lib/store/lines";
import { pickLinesSettings } from "@/lib/store/lines";
import { startSettingsSync } from "@/lib/store/sync";
import { fmtCost, todayLocal } from "@/lib/utils";

const NO_FIRST_LAST = new Set(["Long Minor 2-5-1 with Minor ending", "Long Maj 2-5-1 with Maj7 ending", "Minor and Dominant 2-cells alternated"]);
const ALL_NOTES_DEFAULT = new Set(["Long Minor 2-5-1", "Short Minor 2-5-1", "Double resolution"]);

function lineLabel(line: SampledLineJSON) {
  return line.cells.map((c) => c.name).join("  →  ");
}

function PageOptions() {
  const { s, position } = useLineSetup();
  return (
    <div className="space-y-3">
      <Switch checked={s.enforce} onCheckedChange={(v) => s.set({ enforce: v })} label={s.enforce ? `Enforce today's position (${position})` : "Free (cheapest anywhere)"} />
      <Checkbox label="Anchor positions on the V (Myxolidian) root" checked={s.posViewDom} onChange={(e) => s.set({ posViewDom: e.target.checked })} />
      <Field label={`Max fingering cost: ${s.maxCost.toFixed(1)}`}>
        <Slider min={0} max={40} step={0.5} value={s.maxCost} onChange={(e) => s.set({ maxCost: Number(e.target.value) })} />
      </Field>
      <Checkbox label="Include bonus cells" checked={s.bonus} onChange={(e) => s.set({ bonus: e.target.checked })} />
      <Checkbox label="Translate Dominant and Locrian cells to Minor/Major-I" checked={s.domToMinor} onChange={(e) => s.set({ domToMinor: e.target.checked })} />
      <Checkbox label="Translate the 7sus4 intervals for other modes" checked={s.sus4} onChange={(e) => s.set({ sus4: e.target.checked })} />
      <Field label="Line length (single-mode types)">
        <NumberStepper ariaLabel="Line length" value={s.length} onChange={(v) => s.set({ length: v })} min={2} max={8} />
      </Field>
    </div>
  );
}

export function LinesPage() {
  const { s, key, positionName, posKey, isCombo, chordTones, sampleBase } = useLineSetup();
  React.useEffect(() => startSettingsSync(useLines, "lines", pickLinesSettings), []);
  usePageSettings(<PageOptions />, []);
  const sample = useSampleOne();
  const [batchLines, setBatchLines] = React.useState<SampledLineJSON[]>([]);
  const [batchTitle, setBatchTitle] = React.useState<string>("");
  const [batchBusy, setBatchBusy] = React.useState(false);
  const [preview, setPreview] = React.useState<SampledLineJSON | null>(null);
  const [lastSample, setLastSample] = React.useState<SampleJSON | null>(null);
  const showFirstLast = !NO_FIRST_LAST.has(s.lineType);
  const defaultCn = ALL_NOTES_DEFAULT.has(s.lineType) ? NOTE_OPTIONS : CHORD_TONES;
  const cn = s.connectingNotes ?? defaultCn;

  async function generate() {
    try {
      const out = await sample.mutateAsync(sampleBase);
      setLastSample(out);
      if (!out.lines.length) {
        toast(out.message ?? "No line found — relax the constraints", "danger");
        return;
      }
      s.set({ currentLine: out.lines[0], currentSig: null });
      setPreview(null);
    } catch (e) {
      toast((e as Error).message, "danger");
    }
  }

  async function sampleMany() {
    setBatchBusy(true);
    try {
      const out = await enginePost<SampleJSON>("lines/sample", { ...sampleBase, n: s.nSamples, seed: Math.floor(Math.random() * 1e9) }, { cache: false });
      setLastSample(out);
      setBatchLines(out.lines);
      setBatchTitle(`${out.lines.length} sampled lines`);
      if (!out.lines.length) toast(out.message ?? "No lines found", "danger");
    } catch (e) {
      toast((e as Error).message, "danger");
    } finally {
      setBatchBusy(false);
    }
  }

  async function enumeratePairs() {
    setBatchBusy(true);
    try {
      const out = await enginePost<{ lines: SampledLineJSON[]; structure: string[] }>("lines/pairs", { line_type: s.lineType, bonus: s.bonus, movement: s.movement || null, starting_note: s.firstNote || null, ending_note: s.endNote || null, connecting_notes: s.connectingNotes, chord_tones: chordTones, n_dorian: s.nDorian, n_myxo: s.nMyxo, key });
      setBatchLines(out.lines);
      setBatchTitle(`${out.lines.length} pivot-valid pairs (exhaustive)`);
    } catch (e) {
      toast((e as Error).message, "danger");
    } finally {
      setBatchBusy(false);
    }
  }

  const structure = lastSample?.structure_preview ?? s.currentLine?.structure ?? [];
  const twoCell = (lastSample?.structure_preview?.length ?? (isCombo ? s.nDorian + s.nMyxo : s.lineType === "Short Maj 2-5-1" || s.lineType === "Short Minor 2-5-1" ? 2 : 0)) === 2;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Melodic lines</h1>
      <Card className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Type of line">
            <Select value={s.lineType} onChange={(e) => s.set({ lineType: e.target.value, connectingNotes: null, chordTones: null })}>
              {LINE_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </Select>
          </Field>
          {isCombo && (
            <>
              <Field label="Dorian cells">
                <NumberStepper ariaLabel="Dorian cells" value={s.nDorian} onChange={(v) => s.set({ nDorian: v })} min={1} max={6} />
              </Field>
              <Field label="Myxolidian cells">
                <NumberStepper ariaLabel="Myxolidian cells" value={s.nMyxo} onChange={(v) => s.set({ nMyxo: v })} min={1} max={6} />
              </Field>
            </>
          )}
          {showFirstLast && (
            <>
              <Field label="First note (optional)">
                <Select value={s.firstNote} onChange={(e) => s.set({ firstNote: e.target.value })}>
                  <option value="">None</option>
                  {NOTE_OPTIONS.map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="End note (optional)">
                <Select value={s.endNote} onChange={(e) => s.set({ endNote: e.target.value })}>
                  <option value="">None</option>
                  {NOTE_OPTIONS.map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </Select>
              </Field>
            </>
          )}
          <Field label="Line movement (optional)">
            <Select value={s.movement} onChange={(e) => s.set({ movement: e.target.value as LineMovement })}>
              {["", "A and N", "D and N", "A", "D"].map((m) => (
                <option key={m} value={m}>
                  {m || "Any"}
                </option>
              ))}
            </Select>
          </Field>
        </div>
        <Field label="Connecting notes (the pivots a cell may enter on)">
          <div className="flex flex-wrap gap-1.5">
            {NOTE_OPTIONS.map((n) => {
              const on = cn.includes(n);
              return (
                <button
                  key={n}
                  type="button"
                  onClick={() => s.set({ connectingNotes: on ? cn.filter((x) => x !== n) : [...cn, n] })}
                  className={`rounded-full border px-2.5 py-1 text-xs ${on ? "border-accent bg-accent-soft text-accent" : "bg-bg-elev text-fg-muted"}`}
                >
                  {n}
                </button>
              );
            })}
            <Button size="sm" variant="ghost" onClick={() => s.set({ connectingNotes: null })}>
              reset
            </Button>
          </div>
        </Field>
        <Checkbox label="Connecting notes are chord tones" checked={chordTones} onChange={(e) => s.set({ chordTones: e.target.checked })} />
        {structure.length > 0 && (
          <p className="text-xs text-fg-muted">
            Structure: <span className="font-mono">{structure.join(" · ")}</span>
          </p>
        )}
        {lastSample?.harmony_caption && <p className="text-xs text-fg-muted">{lastSample.harmony_caption.replace(/\*\*/g, "")}</p>}
        {lastSample?.mapping_info && <Info>{lastSample.mapping_info.replace(/\*\*/g, "")}</Info>}
        {lastSample?.chord_tones_info && <Info>{lastSample.chord_tones_info.replace(/\*\*/g, "")}</Info>}
        {chordTones && !s.firstNote && <p className="text-xs text-fg-muted">First note: a chord tone (1 / 3 / 5 / 7) of the first cell&apos;s chord.</p>}
        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={generate} disabled={sample.isPending}>
            {sample.isPending ? <Spinner /> : null} Generate melodic line
          </Button>
          <NumberStepper ariaLabel="Lines to sample" value={s.nSamples} onChange={(v) => s.set({ nSamples: v })} min={3} max={100} />
          <Button variant="outline" onClick={sampleMany} disabled={batchBusy}>
            Sample &amp; rank lines
          </Button>
          {twoCell && (
            <Button variant="outline" onClick={enumeratePairs} disabled={batchBusy}>
              Enumerate ALL pairs &amp; rank
            </Button>
          )}
        </div>
      </Card>

      {s.currentLine && <CurrentLine line={s.currentLine} keyName={key} positionName={positionName} posKey={posKey} maxCost={s.maxCost} />}

      {batchLines.length > 0 && (
        <BatchPanel title={batchTitle} lines={batchLines} keyName={key} positionName={positionName} posKey={posKey} maxCost={s.maxCost} preview={preview} onPreview={setPreview} onPractice={(l) => { s.set({ currentLine: l, currentSig: null }); setPreview(null); window.scrollTo({ top: 0, behavior: "smooth" }); }} />
      )}

      <SavedLines lineType={s.lineType} movement={s.movement} />
    </div>
  );
}

function CurrentLine({ line, keyName, positionName, posKey, maxCost }: { line: SampledLineJSON; keyName: string; positionName: string | null; posKey: string; maxCost: number }) {
  const s = useLines();
  const q = useLineFingerings(line, keyName, positionName, posKey);
  const save = useSaveLine();
  const all = q.data?.fingerings ?? [];
  const under = all.filter((f) => f.cost <= maxCost);
  const chosen: FingeringJSON | undefined = under.find((f) => f.layout === s.currentSig) ?? under[0];
  const cellsLabel = line.cells.map((c) => c.name);

  async function saveLine() {
    try {
      await save.mutateAsync({
        date: todayLocal(),
        line_type: line.line_type,
        cells: cellsLabel,
        note_seq: line.cells.map((c) => c.degrees),
        grade: s.grade,
        comment: s.comment,
        movement: s.movement || null,
        tab_encoding: chosen?.encoding ?? null,
        tab_json: chosen ?? null,
      });
      toast(chosen ? `Line saved with its tab (${chosen.where})` : "Line saved (sequence only — no tab displayed)", "ok");
    } catch (e) {
      toast((e as Error).message, "danger");
    }
  }

  return (
    <Card className="space-y-3">
      <h2 className="text-base font-semibold">Current line</h2>
      <div className="grid gap-1 sm:grid-cols-[8rem_1fr_auto]">
        {line.cells.map((c, i) => (
          <React.Fragment key={c.id + i}>
            <div className="text-xs font-semibold text-accent">{line.structure[i]}</div>
            <div className="text-sm">{c.name}</div>
            <div className="font-mono text-sm text-fg-muted">{c.degrees.join("-")}</div>
          </React.Fragment>
        ))}
      </div>
      {line.harmony_caption && <p className="text-xs text-fg-muted">{line.harmony_caption.replace(/\*\*/g, "")}</p>}
      <h3 className="text-sm font-semibold">Fingering {positionName ? `in ${positionName}` : "(Free)"} — cheapest first</h3>
      {q.isLoading && <Skeleton className="h-32" />}
      {q.error && <Info tone="danger">{(q.error as Error).message}</Info>}
      {q.data && !all.length && <Info tone="warn">{q.data.error ?? "No playable fingering for this line."}</Info>}
      {all.length > 0 && !under.length && <Info>All {all.length} fingerings of this line cost more than the max ({maxCost}) — raise it.</Info>}
      {under.length > 1 && (
        <Table>
          <thead>
            <tr>
              <Th>#</Th>
              <Th className="text-right">Cost</Th>
              <Th>Frets</Th>
              <Th className="text-right">↑</Th>
              <Th className="text-right">Flags</Th>
              <Th>Position(s)</Th>
              <Th>Layout</Th>
            </tr>
          </thead>
          <tbody>
            {under.map((f, i) => (
              <Tr key={f.layout} selected={chosen?.layout === f.layout} onClick={() => s.set({ currentSig: f.layout })}>
                <Td>{i + 1}</Td>
                <Td className="text-right tabular-nums">{fmtCost(f.cost)}</Td>
                <Td>
                  {f.fret_lo}–{f.fret_hi}
                </Td>
                <Td className="text-right">{f.n_up}</Td>
                <Td className="text-right">{f.n_flags}</Td>
                <Td className="max-w-[12rem] truncate">{f.positions.join(", ") || "none"}</Td>
                <Td className="font-mono text-[11px]">{f.layout}</Td>
              </Tr>
            ))}
          </tbody>
        </Table>
      )}
      {chosen && (
        <>
          <p className="text-xs text-fg-muted">
            <strong>{under.length} fingering(s)</strong> · showing cost {chosen.cost.toFixed(2)} · {chosen.where}
            {q.data?.truncated && (
              <Badge tone="warn" className="ml-2">
                budget hit — partial list
              </Badge>
            )}
          </p>
          <FingeringCard fingering={chosen} pivotIndices={q.data?.pivot_indices} filename="melodic-line.svg" />
        </>
      )}
      <div className="flex flex-wrap items-end gap-2 border-t pt-3">
        <Field label="How good was it?">
          <NumberStepper ariaLabel="Grade" value={s.grade} onChange={(v) => s.set({ grade: v })} min={1} max={5} />
        </Field>
        <Field label="Comment" className="min-w-48 flex-1">
          <Input value={s.comment} onChange={(e) => s.set({ comment: e.target.value })} placeholder="e.g. position 2, without the last cell" />
        </Field>
        <Button onClick={saveLine} disabled={save.isPending}>
          Save line{chosen ? " + tab" : ""}
        </Button>
      </div>
    </Card>
  );
}

function BatchPanel({ title, lines, keyName, positionName, posKey, maxCost, preview, onPreview, onPractice }: { title: string; lines: SampledLineJSON[]; keyName: string; positionName: string | null; posKey: string; maxCost: number; preview: SampledLineJSON | null; onPreview: (l: SampledLineJSON) => void; onPractice: (l: SampledLineJSON) => void }) {
  const { rows, playable, done, total } = useBatchFingerings(lines, keyName, positionName, posKey, maxCost);
  const sel = playable.find((r) => r.line === preview) ?? playable[0];
  return (
    <Card className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold">{title} — ranked by playability</h2>
        <span className="text-xs text-fg-muted">
          {done}/{total} fingered · {playable.length} playable under the max cost
        </span>
      </div>
      <p className="text-xs text-fg-muted">Each line is ranked by its cheapest fingering {positionName ? `inside ${positionName}` : "anywhere on the neck"}; lines with none are dropped. Click a row to preview; &quot;Practice this line&quot; makes it the current line above.</p>
      <Table>
        <thead>
          <tr>
            <Th className="text-right">Cost</Th>
            <Th>Line</Th>
            <Th className="text-right">Fing.</Th>
            <Th>Played at</Th>
            <Th className="text-right">↑</Th>
          </tr>
        </thead>
        <tbody>
          {playable.map((r) => (
            <Tr key={r.line.signature.join("|")} selected={sel === r} onClick={() => onPreview(r.line)}>
              <Td className="text-right tabular-nums">{fmtCost(r.best!.cost)}</Td>
              <Td className="max-w-[28rem] truncate">{lineLabel(r.line)}</Td>
              <Td className="text-right">{r.nFingerings}</Td>
              <Td className="max-w-[12rem] truncate">{r.best!.where}</Td>
              <Td className="text-right">{r.best!.n_up}</Td>
            </Tr>
          ))}
          {rows.filter((r) => r.status === "pending").slice(0, 3).map((r) => (
            <tr key={"p" + r.line.signature.join("|")}>
              <Td colSpan={5}>
                <Skeleton className="h-3 w-56" />
              </Td>
            </tr>
          ))}
        </tbody>
      </Table>
      {sel && (
        <>
          <p className="text-sm">
            <strong>{lineLabel(sel.line)}</strong> · cost {sel.best!.cost.toFixed(2)} · {sel.best!.where}
          </p>
          <FingeringCard fingering={sel.best!} pivotIndices={sel.data?.pivot_indices} filename="batch-line.svg">
            <Button size="sm" onClick={() => onPractice(sel.line)}>
              Practice this line
            </Button>
          </FingeringCard>
        </>
      )}
    </Card>
  );
}

function SavedLines({ lineType, movement }: { lineType: string; movement: string }) {
  const q = useSavedLines(lineType);
  const del = useDeleteLine();
  const [open, setOpen] = React.useState<string | null>(null);
  const lines = React.useMemo(() => {
    const xs = [...(q.data?.lines ?? [])];
    xs.sort((a, b) => Number((b.movement ?? "") === movement) - Number((a.movement ?? "") === movement) || (b.grade ?? 0) - (a.grade ?? 0) || b.createdAt.localeCompare(a.createdAt));
    return xs;
  }, [q.data, movement]);
  const sel = lines.find((l) => l.id === open) ?? null;
  return (
    <section className="space-y-3">
      <h2 className="text-base font-semibold">Saved melodic lines · {lineType}</h2>
      {q.isLoading && <Skeleton className="h-20" />}
      {q.data && !lines.length && <p className="text-sm text-fg-muted">Nothing saved for this line type yet.</p>}
      {lines.length > 0 && (
        <Table>
          <thead>
            <tr>
              <Th>Date</Th>
              <Th>Line</Th>
              <Th>Start</Th>
              <Th>Last</Th>
              <Th className="text-right">Grade</Th>
              <Th>Comment</Th>
              <Th>Mvt</Th>
              <Th />
            </tr>
          </thead>
          <tbody>
            {lines.map((l) => (
              <Tr key={l.id} selected={sel?.id === l.id} onClick={() => setOpen(sel?.id === l.id ? null : l.id)}>
                <Td className="whitespace-nowrap">{l.date}</Td>
                <Td className="max-w-[26rem] truncate">{l.cells.join("  →  ")}</Td>
                <Td className="font-mono">{l.noteSeq[0]?.[0] ?? ""}</Td>
                <Td className="font-mono">{l.noteSeq.at(-1)?.at(-1) ?? ""}</Td>
                <Td className="text-right">{l.grade ?? ""}</Td>
                <Td className="max-w-[14rem] truncate text-fg-muted">{l.comment ?? ""}</Td>
                <Td>{l.movement ?? ""}</Td>
                <Td onClick={(e) => e.stopPropagation()}>
                  <Button size="sm" variant="ghost" onClick={() => { if (confirm("Delete this saved line?")) del.mutate(l.id); }}>
                    delete
                  </Button>
                </Td>
              </Tr>
            ))}
          </tbody>
        </Table>
      )}
      {sel && <SavedLineDetail line={sel} />}
    </section>
  );
}

function SavedLineDetail({ line }: { line: SavedLine }) {
  const tab = line.tabJson;
  const placed = tab ? tab.placed : line.tabEncoding ? placedFromEncoding(line.tabEncoding, { degrees: line.noteSeq.flat(), cells: line.noteSeq.flatMap((d, i) => d.map(() => line.cells[i] ?? null)) }) : null;
  return (
    <Card className="space-y-2">
      <div className="grid gap-1 sm:grid-cols-[1fr_auto]">
        {line.cells.map((name, i) => (
          <React.Fragment key={i}>
            <div className="text-sm">{name}</div>
            <div className="font-mono text-sm text-fg-muted">{(line.noteSeq[i] ?? []).join("-")}</div>
          </React.Fragment>
        ))}
      </div>
      {placed ? (
        <TabPlayer placed={placed} chords={tab?.chords} beatsPerBar={tab?.beats_per_bar ?? 4} totalCost={tab?.cost} patternId={`saved:${line.id}`} />
      ) : (
        <p className="text-xs text-fg-muted">No tab was saved with this line.</p>
      )}
    </Card>
  );
}
