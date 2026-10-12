"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import { nowIso, type Synced } from "./sync";

export type ScoreState = Synced & {
  posKey: string | null; // null = today's key
  set: (p: Partial<Omit<ScoreState, "set">>) => void;
};

export const useScore = create<ScoreState>()(
  persist((set) => ({ updatedAt: "", posKey: null, set: (p) => set({ ...p, updatedAt: nowIso() }) }), { name: "bebop.score", version: 1 }),
);
