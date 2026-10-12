import type { CellJSON, FingeringJSON } from "@/lib/engine/types";

export type DrillCell = { id: string; name: string; degrees: string[]; movement: string | null };

export type DrillItem = {
  id: string; // `${pairKey}#${layoutSig}`
  pairKey: string;
  end: DrillCell;
  start: DrillCell;
  layoutSig: string;
  k: number; // 1-based index of this fingering among the pair's kept ones
  m: number; // how many kept fingerings the pair has
  cost: number;
};

export type DrillSourceRow = {
  pairKey: string;
  end: CellJSON | DrillCell;
  start: CellJSON | DrillCell;
  /** candidates: in-box, under the max cost, cheapest first */
  candidates: FingeringJSON[];
};

const toCell = (c: CellJSON | DrillCell): DrillCell => ({ id: c.id, name: c.name, degrees: [...c.degrees], movement: c.movement });

/** The drill's item list (today's semantics): kept pairs × their kept
 * fingerings (candidates minus deleted; the cheapest one only unless
 * `allFingerings`), flattened and sorted by cost ascending. Pure. */
export function buildItems(rows: DrillSourceRow[], opts: { kept: (pairKey: string) => boolean; deleted: (pairKey: string) => ReadonlySet<string>; allFingerings: boolean }): DrillItem[] {
  const out: DrillItem[] = [];
  for (const r of rows) {
    if (!opts.kept(r.pairKey)) continue;
    const gone = opts.deleted(r.pairKey);
    let kept = r.candidates.filter((f) => !gone.has(f.layout));
    if (!opts.allFingerings) kept = kept.slice(0, 1);
    kept.forEach((f, i) => {
      out.push({ id: `${r.pairKey}#${f.layout}`, pairKey: r.pairKey, end: toCell(r.end), start: toCell(r.start), layoutSig: f.layout, k: i + 1, m: kept.length, cost: f.cost });
    });
  }
  out.sort((a, b) => a.cost - b.cost || a.pairKey.localeCompare(b.pairKey) || a.k - b.k);
  return out;
}

export function secondsPerItem(totalMinutes: number, nItems: number): number {
  if (nItems <= 0) return 0;
  return Math.max(1, Math.floor((totalMinutes * 60) / nItems));
}
