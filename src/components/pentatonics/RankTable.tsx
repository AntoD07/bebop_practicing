"use client";

import * as React from "react";
import { Badge, Info, Skeleton } from "@/components/ui/misc";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { FingeringCard } from "@/components/tab/FingeringCard";
import type { RankRow } from "@/lib/engine/types";
import { fmtCost } from "@/lib/utils";

/** The ranked-fingerings table shared by the Pentatonics and Triads pages. */
export function RankTable({ title, rows, done, total, enforced, maxCost, multi, slack, keyName, styleFilter, onStyleFilter, filename }: { title: string; rows: RankRow[]; done: number; total: number; enforced: string | null; maxCost: number; multi: boolean; slack: number; keyName: string; styleFilter: string[]; onStyleFilter: (s: string[]) => void; filename: string }) {
  const [selKey, setSelKey] = React.useState<string | null>(null);
  const underMax = rows.filter((r) => r.cost === null || r.cost <= maxCost);
  const styles = Array.from(new Set(underMax.map((r) => r.position)));
  const view = enforced ? underMax : underMax.filter((r) => !styleFilter.length || styleFilter.includes(r.position));
  const rowKey = (r: RankRow) => `${r.start ?? ""}|${r.position}|${r.layout ?? ""}|${r.where}`;
  const sel = view.find((r) => rowKey(r) === selKey) ?? view.find((r) => r.fingering) ?? null;
  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold">{title}</h2>
        <span className="text-xs text-fg-muted">
          {done}/{total} ranked{rows.length - underMax.length > 0 ? ` · ${rows.length - underMax.length} hidden by the max cost (${maxCost})` : ""}
        </span>
      </div>
      {enforced ? (
        <p className="text-xs text-fg-muted">
          <strong>{view.length} fingerings in {enforced}</strong> (±{slack} fret, box on {keyName}), cheapest per note first — click a row for its tab.
        </p>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {styles.map((st) => {
            const on = !styleFilter.length || styleFilter.includes(st);
            return (
              <button key={st} type="button" onClick={() => onStyleFilter(styleFilter.includes(st) ? styleFilter.filter((x) => x !== st) : [...styleFilter, st])} className={`rounded-full border px-2.5 py-1 text-xs ${on ? "border-accent bg-accent-soft text-accent" : "bg-bg-elev text-fg-muted"}`}>
                {st}
              </button>
            );
          })}
          {styleFilter.length > 0 && (
            <button className="text-xs text-fg-muted underline" onClick={() => onStyleFilter([])}>
              all styles
            </button>
          )}
        </div>
      )}
      {done < total && <Skeleton className="h-3 w-48" />}
      {view.length > 0 && (
        <Table>
          <thead>
            <tr>
              {multi && <Th>Start</Th>}
              {!enforced && <Th>Fingering</Th>}
              <Th className="text-right">Cost/note</Th>
              <Th className="text-right">Cost</Th>
              <Th>Played at</Th>
              {enforced && (
                <>
                  <Th>Frets</Th>
                  <Th className="text-right">↑</Th>
                  <Th>Layout</Th>
                </>
              )}
            </tr>
          </thead>
          <tbody>
            {view.map((r) => (
              <Tr key={rowKey(r)} selected={sel === r} onClick={() => setSelKey(rowKey(r))} className={r.fingering ? "" : "opacity-50"}>
                {multi && <Td>{r.start}</Td>}
                {!enforced && <Td className="max-w-[14rem] truncate">{r.position}</Td>}
                <Td className="text-right tabular-nums">{r.cpn === null ? "—" : r.cpn.toFixed(2)}</Td>
                <Td className="text-right tabular-nums">{fmtCost(r.cost)}</Td>
                <Td className="max-w-[16rem] truncate">{r.where}</Td>
                {enforced && (
                  <>
                    <Td>{r.fingering ? `${r.fingering.fret_lo}–${r.fingering.fret_hi}` : ""}</Td>
                    <Td className="text-right">{r.fingering?.n_up ?? ""}</Td>
                    <Td className="max-w-[16rem] truncate font-mono text-[11px]">{r.layout ?? ""}</Td>
                  </>
                )}
              </Tr>
            ))}
          </tbody>
        </Table>
      )}
      {done === total && !view.length && <Info tone="warn">Nothing to show — raise the max cost, or untick &quot;Enforce the position&quot;.</Info>}
      {sel?.fingering && (
        <>
          <p className="text-xs text-fg-muted">
            Showing: {multi && sel.start ? `start on ${sel.start} · ` : ""}
            <strong>{sel.position}</strong> · {sel.where} {sel.fingering.mode === "optimum" && <Badge tone="warn">single optimum</Badge>}
          </p>
          <FingeringCard fingering={sel.fingering} filename={filename} options={{ showChords: false }} />
        </>
      )}
    </section>
  );
}

export function WeightsEditor({ weights, onChange }: { weights: { max_stretch: number; u_cost: number; drop_cost: number; shift_cost: number; break_cost: number; sweep_bonus: number }; onChange: (w: typeof weights) => void }) {
  const row = (k: keyof typeof weights, label: string, min: number, max: number, step: number) => (
    <label key={k} className="grid grid-cols-[9rem_1fr_3rem] items-center gap-2 text-xs">
      <span>{label}</span>
      <input type="range" min={min} max={max} step={step} value={weights[k]} onChange={(e) => onChange({ ...weights, [k]: Number(e.target.value) })} className="accent-[var(--accent)]" />
      <span className="text-right tabular-nums">{weights[k]}</span>
    </label>
  );
  return (
    <div className="space-y-1.5">
      {row("max_stretch", "max_stretch", 3, 6, 1)}
      {row("u_cost", "u_cost (upstroke)", 0, 5, 0.25)}
      {row("drop_cost", "drop_cost", 0, 30, 1)}
      {row("shift_cost", "shift_cost /fret", 0, 3, 0.25)}
      {row("break_cost", "break_cost (2npS)", 0, 10, 0.5)}
      {row("sweep_bonus", "sweep_bonus", 0, 3, 0.25)}
    </div>
  );
}
