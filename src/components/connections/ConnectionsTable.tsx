"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { Badge, Skeleton } from "@/components/ui/misc";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import type { PairRow } from "@/lib/connections/useConnections";
import { fmtCost } from "@/lib/utils";

export function LoadProgress({ done, total, errors }: { done: number; total: number; errors: number }) {
  if (!total) return null;
  const pct = Math.round((100 * done) / total);
  return (
    <div className="flex items-center gap-2 text-xs text-fg-muted">
      <div className="h-1.5 w-32 overflow-hidden rounded bg-bg-muted">
        <div className="h-full bg-accent transition-[width]" style={{ width: `${pct}%` }} />
      </div>
      <span>
        {done}/{total} fingered{errors ? ` · ${errors} failed` : ""}
      </span>
    </div>
  );
}

export function ConnectionsTable({ rows, pending, selected, onSelect, onKept, onPractice }: { rows: PairRow[]; pending: PairRow[]; selected: string | null; onSelect: (pk: string) => void; onKept: (pk: string, kept: boolean) => void; onPractice?: (pk: string) => void }) {
  return (
    <Table>
      <thead>
        <tr>
          <Th className="w-8">Keep</Th>
          <Th>Ending cell</Th>
          <Th>Starting cell</Th>
          <Th className="text-right">Cost</Th>
          <Th className="text-right">Fing.</Th>
          <Th>Pivot</Th>
          <Th>Position</Th>
          <Th className="text-right">↑</Th>
          <Th className="text-right">Flags</Th>
          {onPractice && <Th />}
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <Tr key={r.pairKey} selected={r.pairKey === selected} onClick={() => onSelect(r.pairKey)}>
            <Td onClick={(e) => e.stopPropagation()}>
              <input type="checkbox" className="accent-[var(--accent)]" checked={r.isKept} onChange={(e) => onKept(r.pairKey, e.target.checked)} aria-label="keep" />
            </Td>
            <Td className="max-w-[14rem]">
              <div className="truncate font-medium">{r.end.name}</div>
              <div className="font-mono text-[11px] text-fg-muted">{r.end.degrees.join("-")}</div>
            </Td>
            <Td className="max-w-[14rem]">
              <div className="truncate font-medium">{r.start.name}</div>
              <div className="font-mono text-[11px] text-fg-muted">{r.start.degrees.join("-")}</div>
            </Td>
            <Td className="text-right tabular-nums">{fmtCost(r.best?.cost)}</Td>
            <Td className="text-right tabular-nums">
              {r.kept.length}
              {r.data?.truncated && (
                <Badge tone="warn" className="ml-1">
                  partial
                </Badge>
              )}
            </Td>
            <Td className="whitespace-nowrap">
              {r.data?.pivot.name} <span className="text-fg-muted">({r.data?.pivot.label})</span>
            </Td>
            <Td className="max-w-[12rem] truncate">{r.best?.where ?? "—"}</Td>
            <Td className="text-right tabular-nums">{r.best?.n_up ?? "—"}</Td>
            <Td className="text-right tabular-nums">{r.best?.n_flags ?? "—"}</Td>
            {onPractice && (
              <Td onClick={(e) => e.stopPropagation()}>
                <Button size="sm" variant="ghost" onClick={() => onPractice(r.pairKey)} disabled={!r.isKept || !r.kept.length}>
                  Practice from here
                </Button>
              </Td>
            )}
          </Tr>
        ))}
        {pending.map((r) => (
          <tr key={r.pairKey} className="opacity-70">
            <Td />
            <Td colSpan={onPractice ? 9 : 8}>
              <div className="flex items-center gap-2 text-xs text-fg-muted">
                <Skeleton className="h-3 w-40" />
                {r.end.name} → {r.start.name} {r.status === "error" ? <Badge tone="danger">{r.error}</Badge> : "…"}
              </div>
            </Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}
