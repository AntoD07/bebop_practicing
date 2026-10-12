"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/field";
import { Badge, Info } from "@/components/ui/misc";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { FingeringCard } from "@/components/tab/FingeringCard";
import type { PairRow } from "@/lib/connections/useConnections";
import type { FingeringJSON } from "@/lib/engine/types";
import { fmtCost } from "@/lib/utils";

export function FingeringList({
  row,
  deleted,
  showDeleted,
  onShowDeleted,
  onDelete,
  onRestore,
  onKeepOnly,
  onRestoreAll,
  onLoadAll,
  loadingAll,
  maxCost,
  positionLabel,
  selectedSig,
  onSelectSig,
}: {
  row: PairRow;
  deleted: ReadonlySet<string>;
  showDeleted: boolean;
  onShowDeleted: (b: boolean) => void;
  onDelete: (sig: string) => void;
  onRestore: (sig: string) => void;
  onKeepOnly: (sig: string, all: string[]) => void;
  onRestoreAll: () => void;
  onLoadAll?: () => void;
  loadingAll?: boolean;
  maxCost: number;
  positionLabel: string;
  selectedSig: string | null;
  onSelectSig: (sig: string | null) => void;
}) {
  const cands = row.candidates;
  const keptF = row.kept;
  const shown = showDeleted ? cands : keptF;
  const chosen: FingeringJSON | undefined = shown.find((f) => f.layout === selectedSig) ?? shown[0];
  const data = row.data;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-sm">
          <span className="font-semibold">{row.end.name}</span> <span className="text-fg-muted">→</span> <span className="font-semibold">{row.start.name}</span>{" "}
          <Badge tone={row.isKept ? "ok" : "default"} className="ml-1">
            {row.isKept ? "kept" : "not kept"}
          </Badge>
          {data && (
            <span className="ml-2 text-xs text-fg-muted">
              {data.sym1} → {data.sym2} · pivot {data.pivot.name} ({data.pivot.label})
            </span>
          )}
        </div>
        <Switch checked={showDeleted} onCheckedChange={onShowDeleted} label="Show deleted" />
      </div>
      {data?.error && !row.inBox.length && <Info tone="warn">No playable fingering: {data.error}</Info>}
      {data?.truncated && (
        <Info tone="warn">
          The layout budget was hit: some registers show only their single best layout.{" "}
          {onLoadAll && (
            <Button size="sm" variant="outline" className="ml-2" onClick={onLoadAll} disabled={loadingAll}>
              {loadingAll ? "Loading…" : "Load every layout"}
            </Button>
          )}
        </Info>
      )}
      {row.inBox.length > 0 && !cands.length && <Info>All {row.inBox.length} fingerings of this connection cost more than the max ({maxCost}) — raise it to see them.</Info>}
      {cands.length > 0 && !shown.length && <Info>All {cands.length} fingerings of this connection are deleted — show deleted to restore some.</Info>}
      {shown.length > 0 && (
        <>
          <p className="text-xs text-fg-muted">
            <strong>
              {keptF.length} of {cands.length} fingerings
            </strong>{" "}
            kept for practice in {positionLabel} (cheapest first). Click a row to preview its tab; delete it from — or restore it to — the practice set. Changes save automatically.
          </p>
          <Table>
            <thead>
              <tr>
                <Th>Practice</Th>
                <Th>#</Th>
                <Th className="text-right">Cost</Th>
                <Th>Frets</Th>
                <Th className="text-right">↑</Th>
                <Th className="text-right">Flags</Th>
                <Th>Position(s)</Th>
                <Th>Layout (string/fret)</Th>
              </tr>
            </thead>
            <tbody>
              {shown.map((f, i) => (
                <Tr key={f.layout} selected={chosen?.layout === f.layout} onClick={() => onSelectSig(f.layout)}>
                  <Td>{deleted.has(f.layout) ? <Badge tone="danger">deleted</Badge> : <Badge tone="ok">✓</Badge>}</Td>
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
          {chosen && (
            <div className="flex flex-wrap gap-2">
              {deleted.has(chosen.layout) ? (
                <Button size="sm" variant="outline" onClick={() => onRestore(chosen.layout)}>
                  Restore this fingering
                </Button>
              ) : (
                <>
                  <Button size="sm" variant="outline" onClick={() => onDelete(chosen.layout)}>
                    Delete from practice
                  </Button>
                  {keptF.length > 1 && (
                    <Button size="sm" variant="outline" onClick={() => onKeepOnly(chosen.layout, cands.map((c) => c.layout))}>
                      Keep only this one
                    </Button>
                  )}
                </>
              )}
              {deleted.size > 0 && (
                <Button size="sm" variant="ghost" onClick={onRestoreAll}>
                  Restore all fingerings
                </Button>
              )}
            </div>
          )}
          {chosen && <FingeringCard fingering={chosen} pivotIndices={data?.pivot_indices} caption={`${chosen.where} · ${chosen.mode === "optimum" ? "single optimum (budget)" : chosen.mode}`} filename={`${row.end.name} - ${row.start.name}.svg`} />}
        </>
      )}
    </div>
  );
}
