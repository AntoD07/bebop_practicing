"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import { DEFAULT_WEIGHTS, type Weights } from "./pentatonics";
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
      weights: DEFAULT_WEIGHTS,
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
    { name: "bebop.triads", version: 1, skipHydration: true },
  ),
);

export const pickTriadsSettings = (s: TriadsState) => ({
  keyOverride: s.keyOverride, root1: s.root1, quality1: s.quality1, root2: s.root2, quality2: s.quality2, startDegs: s.startDegs, nOctaves: s.nOctaves, lowOctave: s.lowOctave,
  enforce: s.enforce, maxCost: s.maxCost, weights: s.weights, exercise: s.exercise, scaleDirection: s.scaleDirection, altDirection: s.altDirection, x: s.x, xAlt: s.xAlt, labels: s.labels, mapPosition: s.mapPosition,
});
