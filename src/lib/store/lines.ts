"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { SampledLineJSON } from "@/lib/engine/types";
import { DEFAULT_LINE_TYPE } from "@/lib/music/constants";
import { nowIso, type Synced } from "./sync";

export type LineMovement = "" | "A and N" | "D and N" | "A" | "D";

export type BatchRow = {
  line: SampledLineJSON;
  cost: number | null;
  where: string | null;
  nFingerings: number;
  nUp: number | null;
  status: "pending" | "done" | "error";
  error?: string | null;
};

export type LinesState = Synced & {
  lineType: string;
  length: number;
  nDorian: number;
  nMyxo: number;
  firstNote: string;
  endNote: string;
  movement: LineMovement; // its OWN key (never shared with page 1's)
  connectingNotes: string[] | null; // null = the type's default
  chordTones: boolean | null; // null = default (true for the combo type)
  bonus: boolean;
  domToMinor: boolean;
  sus4: boolean;
  enforce: boolean;
  posViewDom: boolean;
  maxCost: number;
  nSamples: number;
  currentLine: SampledLineJSON | null;
  currentSig: string | null; // layout of the chosen fingering of the current line
  grade: number;
  comment: string;
  set: (p: Partial<Omit<LinesState, "set">>) => void;
};

export const useLines = create<LinesState>()(
  persist(
    (set) => ({
      updatedAt: "",
      lineType: DEFAULT_LINE_TYPE,
      length: 4,
      nDorian: 2,
      nMyxo: 2,
      firstNote: "",
      endNote: "",
      movement: "",
      connectingNotes: null,
      chordTones: null,
      bonus: false,
      domToMinor: false,
      sus4: false,
      enforce: true,
      posViewDom: false,
      maxCost: 15,
      nSamples: 10,
      currentLine: null,
      currentSig: null,
      grade: 5,
      comment: "",
      set: (p) => set({ ...p, updatedAt: nowIso() }),
    }),
    { name: "bebop.lines", version: 1 },
  ),
);

export const pickLinesSettings = (s: LinesState) => ({
  lineType: s.lineType, length: s.length, nDorian: s.nDorian, nMyxo: s.nMyxo, firstNote: s.firstNote, endNote: s.endNote,
  movement: s.movement, connectingNotes: s.connectingNotes, chordTones: s.chordTones, bonus: s.bonus, domToMinor: s.domToMinor,
  sus4: s.sus4, enforce: s.enforce, posViewDom: s.posViewDom, maxCost: s.maxCost, nSamples: s.nSamples,
});
