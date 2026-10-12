"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Anchor } from "@/lib/music/pickKey";
import { nowIso, type Synced } from "./sync";

export type Curation = {
  unkept: string[]; // pairKeys
  deleted: Record<string, string[]>; // pairKey -> layout sigs
  showDeleted: boolean;
  savedAt: string | null; // server save time we last synced with
  dirty: boolean;
};

export const emptyCuration = (): Curation => ({ unkept: [], deleted: {}, showDeleted: false, savedAt: null, dirty: false });

export type ConnectionsState = Synced & {
  chord1: string;
  chord2: string;
  domToMinor1: boolean;
  domToMinor2: boolean;
  bonus: boolean;
  movement: "" | "A" | "D";
  pivot: string | null; // null = the default ("3" when offered)
  enforce: boolean;
  anchor: Anchor;
  maxCost: number;
  showTab: boolean;
  allFingerings: boolean;
  totalMinutes: number;
  selectedPair: string | null;
  curations: Record<string, Curation>;
  set: (p: Partial<Omit<ConnectionsState, "set" | "curations" | "updateCuration">>) => void;
  updateCuration: (pickKey: string, fn: (c: Curation) => Curation) => void;
};

export const useConnections = create<ConnectionsState>()(
  persist(
    (set) => ({
      updatedAt: "",
      chord1: "Minor",
      chord2: "Myxolidian",
      domToMinor1: false,
      domToMinor2: false,
      bonus: false,
      movement: "",
      pivot: null,
      enforce: true,
      anchor: "key",
      maxCost: 15,
      showTab: true,
      allFingerings: false,
      totalMinutes: 10,
      selectedPair: null,
      curations: {},
      set: (p) => set({ ...p, updatedAt: nowIso() }),
      updateCuration: (pickKey, fn) => set((s) => ({ curations: { ...s.curations, [pickKey]: fn(s.curations[pickKey] ?? emptyCuration()) } })),
    }),
    { name: "bebop.connections", version: 1, partialize: (s) => ({ ...s, selectedPair: null }) as ConnectionsState, skipHydration: true },
  ),
);

export const pickConnectionsSettings = (s: ConnectionsState) => ({
  chord1: s.chord1,
  chord2: s.chord2,
  domToMinor1: s.domToMinor1,
  domToMinor2: s.domToMinor2,
  bonus: s.bonus,
  movement: s.movement,
  pivot: s.pivot,
  enforce: s.enforce,
  anchor: s.anchor,
  maxCost: s.maxCost,
  showTab: s.showTab,
  allFingerings: s.allFingerings,
  totalMinutes: s.totalMinutes,
});
