"use client";

import { useQueries } from "@tanstack/react-query";
import { enginePost } from "@/lib/engine/client";
import { queued } from "@/lib/engine/queue";
import type { LineNote, RankJSON, RankRow } from "@/lib/engine/types";
import type { Weights } from "@/lib/store/pentatonics";

export type RankInput = { key: string; lines_by_start: Record<string, LineNote[]>; position: string | null; penta?: string; root?: string; group: number | null; weights: Weights; generic?: boolean };

/** One /pentatonics/rank per starting note, through the queue; rows combined
 * cheapest-per-note first (coverage breaking ties) like rank_across_starts. */
export function useRankAcrossStarts(input: RankInput | null) {
  const entries = input ? Object.entries(input.lines_by_start) : [];
  const queries = useQueries({
    queries: entries.map(([label, line], i) => {
      const body = { key: input!.key, line, position: input!.position, penta: input!.penta ?? "minor", root: input!.root ?? input!.key, group: input!.group, config: input!.weights, generic: !!input!.generic, start_label: label };
      return {
        queryKey: ["engine", "pentatonics/rank", body],
        staleTime: Infinity,
        retry: 1,
        queryFn: ({ signal }: { signal: AbortSignal }) => queued(`rank:${label}`, 10 + i, (sig) => enginePost<RankJSON>("pentatonics/rank", body, { signal: sig }), signal),
      };
    }),
  });
  const rows: RankRow[] = [];
  let done = 0;
  const errors: string[] = [];
  queries.forEach((q) => {
    if (q.data) {
      done++;
      rows.push(...(q.data as RankJSON).rows);
    } else if (q.isError) {
      done++;
      errors.push((q.error as Error).message);
    }
  });
  rows.sort((a, b) => Number(a.cpn === null) - Number(b.cpn === null) || (a.cpn ?? 0) - (b.cpn ?? 0) || b.covered - a.covered);
  return { rows, done, total: entries.length, errors, multi: entries.length > 1 };
}
