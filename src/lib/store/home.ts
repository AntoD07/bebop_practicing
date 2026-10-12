"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import { nowIso, type Synced } from "./sync";

export type HomeState = Synced & {
  mode: string;
  domToMinor: boolean;
  bonus: boolean;
  fingeringKey: string | null; // null = today's key
  set: (p: Partial<Omit<HomeState, "set">>) => void;
};

export const useHome = create<HomeState>()(
  persist(
    (set) => ({
      updatedAt: "",
      mode: "Minor",
      domToMinor: true,
      bonus: false,
      fingeringKey: null,
      set: (p) => set({ ...p, updatedAt: nowIso() }),
    }),
    { name: "bebop.home", version: 1 },
  ),
);
