"use client";

import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { enginePost } from "@/lib/engine/client";
import { queued } from "@/lib/engine/queue";
import type { FingeringJSON, LineFingeringJSON, LineFingeringRequest, SampleJSON, SampleRequest, SampledLineJSON } from "@/lib/engine/types";
import { COMBO_LINE_TYPE, POSITIONS } from "@/lib/music/constants";
import { useLines } from "@/lib/store/lines";
import { useSession } from "@/lib/store/session";

export const KEY_PCS: Record<string, number> = { C: 0, G: 7, D: 2, A: 9, E: 4, B: 11, "F#": 6, F: 5, Bb: 10, Eb: 3, Ab: 8, Db: 1 };
const PC_FLAT = ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"];

export function dominantOf(key: string): string {
  const pc = KEY_PCS[key] ?? 0;
  return PC_FLAT[(pc + 7) % 12];
}

export function useLineSetup() {
  const s = useLines();
  const key = useSession((x) => x.key);
  const position = useSession((x) => x.position);
  const isCombo = s.lineType === COMBO_LINE_TYPE;
  const chordTones = s.chordTones ?? isCombo;
  const positionName = s.enforce ? POSITIONS[position - 1] : null;
  const posKey = s.posViewDom ? dominantOf(key) : key;
  const sampleBase: SampleRequest = {
    line_type: s.lineType, length: s.length, n_dorian: s.nDorian, n_myxo: s.nMyxo, bonus: s.bonus, dom_to_minor: s.domToMinor, sus4: s.sus4,
    movement: s.movement || null, starting_note: s.firstNote || null, ending_note: s.endNote || null,
    connecting_notes: s.connectingNotes, chord_tones: chordTones, key,
  };
  return { s, key, position, positionName, posKey, isCombo, chordTones, sampleBase };
}

export function lineFingeringRequest(line: SampledLineJSON, key: string, position: string | null, posKey: string): LineFingeringRequest {
  return {
    key,
    cells: line.cells.map((c) => ({ id: c.id, degrees: c.degrees, movement: c.movement })),
    reading_modes: line.reading_modes,
    movement_modes: line.movement_modes,
    position,
    pos_key: posKey,
  };
}

export function useLineFingerings(line: SampledLineJSON | null, key: string, position: string | null, posKey: string) {
  const req = line ? lineFingeringRequest(line, key, position, posKey) : null;
  return useQuery({
    queryKey: ["engine", "fingering/line", req],
    enabled: !!req,
    staleTime: Infinity,
    queryFn: () => enginePost<LineFingeringJSON>("fingering/line", req),
  });
}

export function useSampleOne() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: SampleRequest) => enginePost<SampleJSON>("lines/sample", { ...req, n: 1 }, { cache: false }),
    onSuccess: (data) => qc.setQueryData(["lines", "last-sample"], data),
  });
}

/** Batch rows: every line's fingerings through the queue; rows land as they finish. */
export function useBatchFingerings(lines: SampledLineJSON[], key: string, position: string | null, posKey: string, maxCost: number) {
  const queries = useQueries({
    queries: lines.map((line, i) => {
      const req = lineFingeringRequest(line, key, position, posKey);
      return {
        queryKey: ["engine", "fingering/line", req],
        staleTime: Infinity,
        retry: 1,
        queryFn: ({ signal }: { signal: AbortSignal }) => queued(line.signature.join("|"), 10 + i, (sig) => enginePost<LineFingeringJSON>("fingering/line", req, { signal: sig }), signal),
      };
    }),
  });
  const rows = lines.map((line, i) => {
    const q = queries[i];
    const data = q?.data as LineFingeringJSON | undefined;
    const under = data ? data.fingerings.filter((f) => f.cost <= maxCost) : [];
    const best: FingeringJSON | null = under[0] ?? null;
    return { line, data: data ?? null, best, nFingerings: under.length, status: q?.isError ? ("error" as const) : data ? ("done" as const) : ("pending" as const), error: q?.error ? (q.error as Error).message : null };
  });
  const done = rows.filter((r) => r.status !== "pending").length;
  const playable = rows.filter((r) => r.best).sort((a, b) => a.best!.cost - b.best!.cost);
  return { rows, playable, done, total: rows.length };
}

export type SavedLine = { id: string; date: string; lineType: string; cells: string[]; noteSeq: string[][]; grade: number | null; comment: string | null; movement: string | null; tabEncoding: string | null; tabJson: FingeringJSON | null; createdAt: string };

export function useSavedLines(lineType: string) {
  return useQuery({
    queryKey: ["lines", "saved", lineType],
    queryFn: async () => {
      const r = await fetch(`/api/lines?line_type=${encodeURIComponent(lineType)}`);
      if (!r.ok) throw new Error(`lines ${r.status}`);
      return (await r.json()) as { lines: SavedLine[] };
    },
    staleTime: 30_000,
  });
}

export function useSaveLine() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: Record<string, unknown>) => {
      const r = await fetch("/api/lines", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
      if (!r.ok) throw new Error(`save ${r.status}`);
      return r.json();
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["lines", "saved"] }),
  });
}

export function useDeleteLine() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const r = await fetch(`/api/lines/${encodeURIComponent(id)}`, { method: "DELETE" });
      if (!r.ok) throw new Error(`delete ${r.status}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["lines", "saved"] }),
  });
}
