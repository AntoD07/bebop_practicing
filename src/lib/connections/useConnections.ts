"use client";

import * as React from "react";
import { useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { enginePost } from "@/lib/engine/client";
import { queued, engineQueue } from "@/lib/engine/queue";
import type { CellJSON, ConnectionJSON, ConnectionRequest, FingeringJSON, PairsJSON, PairsRequest } from "@/lib/engine/types";
import { FREE_POSITION, POSITIONS } from "@/lib/music/constants";
import { pickKey as makePickKey } from "@/lib/music/pickKey";
import { useConnections, type Curation, emptyCuration } from "@/lib/store/connections";
import { useSession } from "@/lib/store/session";
import { debounce } from "@/lib/utils";

export type PairRow = {
  pairKey: string;
  end: CellJSON;
  start: CellJSON;
  index: number;
  status: "pending" | "loading" | "done" | "error";
  data: ConnectionJSON | null;
  error: string | null;
  /** fingerings in the position, cheapest first (all costs) */
  inBox: FingeringJSON[];
  /** inBox under the max cost */
  candidates: FingeringJSON[];
  /** candidates minus the deleted ones */
  kept: FingeringJSON[];
  /** the pair's cheapest in-box fingering (null = does not fit / error) */
  best: FingeringJSON | null;
  fits: boolean;
  underMax: boolean;
  isKept: boolean;
};

export function usePairsRequest(): PairsRequest {
  const s = useConnections();
  const key = useSession((x) => x.key);
  return React.useMemo(
    () => ({ chord1: s.chord1, chord2: s.chord2, bonus: s.bonus, dom_to_minor1: s.domToMinor1, dom_to_minor2: s.domToMinor2, movement: s.movement || null, pivot: s.pivot, key }),
    [s.chord1, s.chord2, s.bonus, s.domToMinor1, s.domToMinor2, s.movement, s.pivot, key],
  );
}

export function usePairs(req: PairsRequest) {
  return useQuery({ queryKey: ["engine", "connections/pairs", req], queryFn: () => enginePost<PairsJSON>("connections/pairs", req), staleTime: Infinity });
}

export function connectionRequest(pairs: PairsJSON, pair: { end_id: string; start_id: string }, key: string, position: string | null, anchor: ConnectionRequest["anchor"], flags: { bonus: boolean; domToMinor1: boolean; domToMinor2: boolean }): ConnectionRequest {
  return {
    key,
    chord1: pairs.chord1,
    chord2: pairs.chord2,
    cell1: { id: pair.end_id },
    cell2: { id: pair.start_id },
    bonus: flags.bonus,
    dom_to_minor1: flags.domToMinor1,
    dom_to_minor2: flags.domToMinor2,
    position,
    anchor: pairs.single_chord ? "key" : anchor,
  };
}

/** Every pair's fingerings, streamed through the priority queue; the selected
 * row (and the drill's current pair) jump the line. */
export function useConnectionRows(pairs: PairsJSON | undefined, position: string | null, priorityPairs: string[]) {
  const s = useConnections();
  const key = useSession((x) => x.key);
  const flags = React.useMemo(() => ({ bonus: s.bonus, domToMinor1: s.domToMinor1, domToMinor2: s.domToMinor2 }), [s.bonus, s.domToMinor1, s.domToMinor2]);
  const anchor = pairs?.single_chord ? "key" : s.anchor;
  const list = React.useMemo(() => pairs?.pairs ?? [], [pairs]);
  const prio = React.useMemo(() => new Set(priorityPairs), [priorityPairs]);

  React.useEffect(() => {
    for (const p of list) if (prio.has(p.pair_key)) engineQueue.setPriority(p.pair_key, 0);
  }, [prio, list]);

  const queries = useQueries({
    queries: list.map((p, i) => {
      const req = pairs ? connectionRequest(pairs, p, key, position, anchor, flags) : null;
      return {
        queryKey: ["engine", "fingering/connection", req],
        enabled: !!req,
        staleTime: Infinity,
        gcTime: 30 * 60_000,
        retry: 1,
        queryFn: ({ signal }: { signal: AbortSignal }) => queued(p.pair_key, prio.has(p.pair_key) ? 0 : 10 + i, (sig) => enginePost<ConnectionJSON>("fingering/connection", req, { signal: sig }), signal),
      };
    }),
  });
  return { list, queries };
}

export function usePickKey(pairs: PairsJSON | undefined, position: string | null): string | null {
  const anchor = useConnections((x) => x.anchor);
  if (!pairs || pairs.raw_pivot == null) return null;
  return makePickKey({ chord1: pairs.chord1, chord2: pairs.chord2, rawPivot: pairs.raw_pivot, myxoToDorian: pairs.myxo_to_dorian, position, anchor: pairs.single_chord ? "key" : anchor, singleChord: pairs.single_chord });
}

type ServerPick = { exists: boolean; pickKey: string; kept?: string[][]; deleted_fingerings?: Record<string, string[]>; saved?: string };

/** Load the saved curation (server wins when newer), expose kept/deleted
 * helpers and autosave every mutation (debounced). */
export function useCuration(pickKey: string | null, pairs: PairsJSON | undefined) {
  const qc = useQueryClient();
  const curation = useConnections((x) => (pickKey ? x.curations[pickKey] : undefined)) ?? emptyCuration();
  const updateCuration = useConnections((x) => x.updateCuration);
  const [saving, setSaving] = React.useState<"idle" | "saving" | "saved" | "error">("idle");
  const serverQ = useQuery({
    queryKey: ["picks", pickKey],
    enabled: !!pickKey,
    queryFn: async () => {
      const r = await fetch(`/api/picks/${encodeURIComponent(pickKey!)}`);
      if (!r.ok) throw new Error(`picks ${r.status}`);
      return (await r.json()) as ServerPick;
    },
    staleTime: 60_000,
  });

  // hydrate from the server when it is newer than what we hold locally
  React.useEffect(() => {
    const sp = serverQ.data;
    if (!pickKey || !sp || !pairs) return;
    if (!sp.exists) return;
    const local = useConnections.getState().curations[pickKey];
    if (local && local.savedAt && sp.saved && local.savedAt >= sp.saved) return;
    const keptSet = new Set((sp.kept ?? []).map(([e, st]) => `${e} → ${st}`));
    const unkept = pairs.pairs.map((p) => p.pair_key).filter((k) => !keptSet.has(k));
    updateCuration(pickKey, (c) => ({ ...c, unkept, deleted: sp.deleted_fingerings ?? {}, savedAt: sp.saved ?? null, dirty: false }));
  }, [serverQ.data, pickKey, pairs, updateCuration]);

  const save = React.useMemo(
    () =>
      debounce((pk: string, c: Curation, allPairs: { pair_key: string; end: string; start: string }[]) => {
        const unkept = new Set(c.unkept);
        const kept = allPairs.filter((p) => !unkept.has(p.pair_key)).map((p) => [p.end, p.start]);
        const keptKeys = new Set(allPairs.filter((p) => !unkept.has(p.pair_key)).map((p) => p.pair_key));
        const deleted: Record<string, string[]> = {};
        for (const [k, v] of Object.entries(c.deleted)) if (keptKeys.has(k) && v.length) deleted[k] = v;
        const saved = new Date().toISOString();
        setSaving("saving");
        fetch(`/api/picks/${encodeURIComponent(pk)}`, { method: "PUT", headers: { "content-type": "application/json" }, body: JSON.stringify({ kept, deleted_fingerings: deleted, saved }) })
          .then((r) => {
            if (!r.ok) throw new Error(String(r.status));
            setSaving("saved");
            updateCuration(pk, (cc) => ({ ...cc, savedAt: saved, dirty: false }));
            qc.setQueryData(["picks", pk], { exists: true, pickKey: pk, kept, deleted_fingerings: deleted, saved });
          })
          .catch(() => setSaving("error"));
      }, 800),
    [qc, updateCuration],
  );

  const pairList = React.useMemo(() => {
    if (!pairs) return [];
    const byId = new Map(pairs.ending.concat(pairs.starting).map((c) => [c.id, c]));
    return pairs.pairs.map((p) => ({ pair_key: p.pair_key, end: byId.get(p.end_id)?.name ?? "", start: byId.get(p.start_id)?.name ?? "" }));
  }, [pairs]);

  const mutate = React.useCallback(
    (fn: (c: Curation) => Curation) => {
      if (!pickKey) return;
      updateCuration(pickKey, (c) => ({ ...fn(c), dirty: true }));
      const next = useConnections.getState().curations[pickKey];
      save(pickKey, next, pairList);
    },
    [pickKey, updateCuration, save, pairList],
  );

  const unkeptSet = React.useMemo(() => new Set(curation.unkept), [curation.unkept]);
  const deletedSets = React.useMemo(() => {
    const m = new Map<string, Set<string>>();
    for (const [k, v] of Object.entries(curation.deleted)) m.set(k, new Set(v));
    return m;
  }, [curation.deleted]);

  return {
    curation,
    saving,
    serverSaved: serverQ.data?.exists ? serverQ.data.saved ?? null : null,
    isKept: (pk: string) => !unkeptSet.has(pk),
    deleted: (pk: string) => deletedSets.get(pk) ?? new Set<string>(),
    setKept: (pk: string, kept: boolean) => mutate((c) => ({ ...c, unkept: kept ? c.unkept.filter((k) => k !== pk) : Array.from(new Set([...c.unkept, pk])) })),
    keepAll: () => mutate((c) => ({ ...c, unkept: [] })),
    keepNone: () => mutate((c) => ({ ...c, unkept: pairList.map((p) => p.pair_key) })),
    deleteFingering: (pk: string, sig: string) => mutate((c) => ({ ...c, deleted: { ...c.deleted, [pk]: Array.from(new Set([...(c.deleted[pk] ?? []), sig])) } })),
    restoreFingering: (pk: string, sig: string) => mutate((c) => ({ ...c, deleted: { ...c.deleted, [pk]: (c.deleted[pk] ?? []).filter((x) => x !== sig) } })),
    keepOnly: (pk: string, sig: string, all: string[]) => mutate((c) => ({ ...c, deleted: { ...c.deleted, [pk]: all.filter((x) => x !== sig) } })),
    restoreAll: (pk: string) => mutate((c) => ({ ...c, deleted: { ...c.deleted, [pk]: [] } })),
    setShowDeleted: (b: boolean) => pickKey && updateCuration(pickKey, (c) => ({ ...c, showDeleted: b })),
    deleteSaved: async () => {
      if (!pickKey) return;
      save.cancel();
      await fetch(`/api/picks/${encodeURIComponent(pickKey)}`, { method: "DELETE" });
      updateCuration(pickKey, () => emptyCuration());
      qc.setQueryData(["picks", pickKey], { exists: false, pickKey });
      setSaving("idle");
    },
  };
}

export function positionLabel(enforce: boolean, position: number): string | null {
  return enforce ? POSITIONS[position - 1] : null;
}

export const FREE = FREE_POSITION;
