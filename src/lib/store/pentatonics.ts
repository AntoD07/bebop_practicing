"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import { nowIso, type Synced } from "./sync";

export type Weights = { max_stretch: number; u_cost: number; drop_cost: number; shift_cost: number; break_cost: number; sweep_bonus: number };
export const DEFAULT_WEIGHTS: Weights = { max_stretch: 4, u_cost: 1.0, drop_cost: 10, shift_cost: 0.5, break_cost: 3, sweep_bonus: 0.5 };

export type PentaState = Synced & {
  keyOverride: string | null;
  penta: string;
  startDegs: number[]; // [] = every degree
  nOctaves: number;
  lowOctave: number;
  enforce: boolean;
  maxCost: number;
  weights: Weights;
  exercise: "scale" | "pattern" | "chromatic" | "bergonzi" | "shifting";
  direction: string;
  x: number;
  addB6: boolean;
  formula: string | null;
  shiftChoice: string; // "none" = sweep
  groupsPerShift: number;
  nShifts: number;
  intervalName: string | null;
  styleFilter: string[];
  set: (p: Partial<Omit<PentaState, "set">>) => void;
};

export const usePenta = create<PentaState>()(
  persist(
    (set) => ({
      updatedAt: "",
      keyOverride: null,
      penta: "minor",
      startDegs: [],
      nOctaves: 3,
      lowOctave: 1,
      enforce: true,
      maxCost: 30,
      weights: DEFAULT_WEIGHTS,
      exercise: "scale",
      direction: "ascending",
      x: 4,
      addB6: false,
      formula: null,
      shiftChoice: "none",
      groupsPerShift: 2,
      nShifts: 3,
      intervalName: null,
      styleFilter: [],
      set: (p) => set({ ...p, updatedAt: nowIso() }),
    }),
    { name: "bebop.pentatonics", version: 1 },
  ),
);

export const pickPentaSettings = (s: PentaState) => ({
  keyOverride: s.keyOverride, penta: s.penta, startDegs: s.startDegs, nOctaves: s.nOctaves, lowOctave: s.lowOctave, enforce: s.enforce, maxCost: s.maxCost,
  weights: s.weights, exercise: s.exercise, direction: s.direction, x: s.x, addB6: s.addB6, formula: s.formula, shiftChoice: s.shiftChoice,
  groupsPerShift: s.groupsPerShift, nShifts: s.nShifts, intervalName: s.intervalName,
});
