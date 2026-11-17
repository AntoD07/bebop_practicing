"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import { DEFAULT_WEIGHTS, type Weights } from "./pentatonics";

// Runs are played IN a position: a hand shift costs the engine's full default
// (1.0/fret — the Pentatonics page halves it), so a 2-fret move mid-run loses
// to a 1-fret adjustment at the end (user-validated on Eb+F / CAGED A).
export const TRIAD_WEIGHTS: Weights = { ...DEFAULT_WEIGHTS, shift_cost: 1.0 };
import { nowIso, type Synced } from "./sync";

export type TriadsState = Synced & {
  keyOverride: string | null;
  root1: string | null; // null = the key
  quality1: string;
  root2: string | null; // null = a whole tone above the key
  quality2: string;
  startDegs: number[];
  nOctaves: number;
  lowOctave: number;
  enforce: boolean;
  maxCost: number;
  weights: Weights;
  exercise: "scale" | "pattern" | "alternating";
  scaleDirection: string;
  altDirection: string;
  x: number;
  xAlt: number;
  labels: "name" | "degree";
  mapPosition: number | null; // null = today's
  styleFilter: string[];
  set: (p: Partial<Omit<TriadsState, "set">>) => void;
};

export const useTriads = create<TriadsState>()(
  persist(
    (set) => ({
      updatedAt: "",
      keyOverride: null,
      root1: null,
      quality1: "major",
      root2: null,
      quality2: "major",
      startDegs: [],
      nOctaves: 2,
      lowOctave: 2,
      enforce: true,
      maxCost: 30,
      weights: TRIAD_WEIGHTS,
      exercise: "scale",
      scaleDirection: "ascending",
      altDirection: "ascending",
      x: 4,
      xAlt: 3,
      labels: "name",
      mapPosition: null,
      styleFilter: [],
      set: (p) => set({ ...p, updatedAt: nowIso() }),
    }),
    {
      name: "bebop.triads",
      version: 2,
      skipHydration: true,
      // v1 -> v2: the old default shift cost (0.5) becomes the run-oriented 1.0
      migrate: (persisted, version) => {
        const p = persisted as Partial<TriadsState>;
        if (version < 2 && p.weights && p.weights.shift_cost === DEFAULT_WEIGHTS.shift_cost) return { ...p, weights: { ...p.weights, shift_cost: TRIAD_WEIGHTS.shift_cost }, updatedAt: nowIso() };
        return p;
      },
    },
  ),
);

export const pickTriadsSettings = (s: TriadsState) => ({
  keyOverride: s.keyOverride, root1: s.root1, quality1: s.quality1, root2: s.root2, quality2: s.quality2, startDegs: s.startDegs, nOctaves: s.nOctaves, lowOctave: s.lowOctave,
  enforce: s.enforce, maxCost: s.maxCost, weights: s.weights, exercise: s.exercise, scaleDirection: s.scaleDirection, altDirection: s.altDirection, x: s.x, xAlt: s.xAlt, labels: s.labels, mapPosition: s.mapPosition,
});
