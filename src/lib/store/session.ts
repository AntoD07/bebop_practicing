"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import { DEFAULT_TEMPO, POSITIONS, PRACTICE_KEYS } from "@/lib/music/constants";
import { clamp } from "@/lib/utils";
import { nowIso, type Synced } from "./sync";

export type MetronomeMode = "native" | "iframe";

export type SessionState = Synced & {
  // today's draw (server-authoritative; cached here)
  date: string | null;
  key: string;
  position: number; // 1..5
  // shared practice settings (mirrored to the settings table)
  tempo: number;
  meter: 2 | 4;
  metronome: MetronomeMode;
  clickOn: boolean;
  volumes: { click: number; tab: number };
  countInBars: number;
  showIframe: boolean;
  theme: "system" | "light" | "dark";
  setDay: (date: string, key: string, position: number) => void;
  setKey: (key: string) => void;
  setPosition: (position: number) => void;
  setTempo: (tempo: number) => void;
  setMeter: (meter: 2 | 4) => void;
  setMetronome: (m: MetronomeMode) => void;
  setClickOn: (on: boolean) => void;
  setVolumes: (v: Partial<{ click: number; tab: number }>) => void;
  setCountInBars: (n: number) => void;
  setShowIframe: (b: boolean) => void;
  setTheme: (t: "system" | "light" | "dark") => void;
};

export const useSession = create<SessionState>()(
  persist(
    (set) => ({
      updatedAt: "",
      date: null,
      key: PRACTICE_KEYS[0],
      position: 1,
      tempo: DEFAULT_TEMPO,
      meter: 2,
      metronome: "native",
      clickOn: true,
      volumes: { click: 0.8, tab: 0.9 },
      countInBars: 1,
      showIframe: false,
      theme: "system",
      setDay: (date, key, position) => set({ date, key, position }),
      setKey: (key) => set({ key }),
      setPosition: (position) => set({ position: clamp(position, 1, POSITIONS.length) }),
      setTempo: (tempo) => set({ tempo: clamp(Math.round(tempo), 30, 300), updatedAt: nowIso() }),
      setMeter: (meter) => set({ meter, updatedAt: nowIso() }),
      setMetronome: (metronome) => set({ metronome, updatedAt: nowIso() }),
      setClickOn: (clickOn) => set({ clickOn, updatedAt: nowIso() }),
      setVolumes: (v) => set((s) => ({ volumes: { ...s.volumes, ...v }, updatedAt: nowIso() })),
      setCountInBars: (countInBars) => set({ countInBars: clamp(countInBars, 0, 4), updatedAt: nowIso() }),
      setShowIframe: (showIframe) => set({ showIframe, updatedAt: nowIso() }),
      setTheme: (theme) => set({ theme, updatedAt: nowIso() }),
    }),
    { name: "bebop.session", version: 1 },
  ),
);

export const pickSessionSettings = (s: SessionState) => ({
  tempo: s.tempo,
  meter: s.meter,
  metronome: s.metronome,
  clickOn: s.clickOn,
  volumes: s.volumes,
  countInBars: s.countInBars,
  showIframe: s.showIframe,
  theme: s.theme,
});
