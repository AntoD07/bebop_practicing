"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { FingeringJSON } from "@/lib/engine/types";
import { uid } from "@/lib/utils";
import type { DrillItem } from "./buildItems";
import type { DrillConfig, DrillState } from "./types";

// Fingerings are NOT persisted (too heavy): the page registers them when it
// builds the items, and again after a reload (the engine responses are cached).
const fingerings = new Map<string, FingeringJSON>();
export function registerFingerings(entries: [string, FingeringJSON][]) {
  for (const [id, f] of entries) fingerings.set(id, f);
}
export function fingeringFor(itemId: string): FingeringJSON | undefined {
  return fingerings.get(itemId);
}

type Actions = {
  start: (items: DrillItem[], config: DrillConfig, from?: number) => void;
  pause: () => void;
  resume: () => void;
  next: () => void;
  prev: () => void;
  jumpTo: (i: number) => void;
  restartItem: () => void;
  tick: (now: number) => void;
  finish: () => void;
  reset: () => void;
  setItems: (items: DrillItem[]) => void;
  setConfig: (patch: Partial<DrillConfig>) => void;
  hydrate: (state: DrillState) => void;
};

export type DrillStore = DrillState & Actions;

const initial: DrillState = {
  status: "idle",
  config: null,
  items: [],
  currentIndex: 0,
  itemRemainingMs: 0,
  itemDeadlineAt: null,
  sessionStartedAt: null,
  updatedAt: 0,
  deviceId: "",
  lastEvent: null,
};

let seq = 0;
const ev = (type: NonNullable<DrillState["lastEvent"]>["type"], index: number) => ({ seq: ++seq, type, index });

export const useDrill = create<DrillStore>()(
  persist(
    (set, get) => ({
      ...initial,
      start: (items, config, from = 0) => {
        const now = Date.now();
        const i = Math.min(Math.max(0, from), Math.max(0, items.length - 1));
        set({
          status: items.length ? "running" : "idle",
          config,
          items,
          currentIndex: i,
          itemRemainingMs: config.secondsPerItem * 1000,
          itemDeadlineAt: now + config.secondsPerItem * 1000,
          sessionStartedAt: now,
          updatedAt: now,
          deviceId: get().deviceId || uid(),
          lastEvent: ev("start", i),
        });
      },
      pause: () => {
        const s = get();
        if (s.status !== "running") return;
        const now = Date.now();
        set({ status: "paused", itemRemainingMs: Math.max(0, (s.itemDeadlineAt ?? now) - now), itemDeadlineAt: null, updatedAt: now });
      },
      resume: () => {
        const s = get();
        if (s.status !== "paused" || !s.items.length) return;
        const now = Date.now();
        const remaining = s.itemRemainingMs > 0 ? s.itemRemainingMs : (s.config?.secondsPerItem ?? 30) * 1000;
        set({ status: "running", itemDeadlineAt: now + remaining, itemRemainingMs: remaining, updatedAt: now });
      },
      next: () => get().jumpTo(get().currentIndex + 1),
      prev: () => get().jumpTo(get().currentIndex - 1),
      jumpTo: (i) => {
        const s = get();
        if (!s.items.length || !s.config) return;
        const idx = Math.min(Math.max(0, i), s.items.length - 1);
        const now = Date.now();
        const per = s.config.secondsPerItem * 1000;
        const keep = s.config.switchMode === "keep";
        const remaining = keep ? (s.status === "running" ? Math.max(0, (s.itemDeadlineAt ?? now) - now) : s.itemRemainingMs) : per;
        if (s.status === "running") set({ currentIndex: idx, itemDeadlineAt: now + Math.max(1000, remaining), updatedAt: now, lastEvent: ev("jump", idx) });
        else if (s.status === "paused") set({ currentIndex: idx, itemRemainingMs: Math.max(1000, remaining), updatedAt: now, lastEvent: ev("jump", idx) });
        else set({ status: "running", currentIndex: idx, itemDeadlineAt: now + per, itemRemainingMs: per, sessionStartedAt: s.sessionStartedAt ?? now, updatedAt: now, lastEvent: ev("start", idx) });
      },
      restartItem: () => {
        const s = get();
        if (!s.config) return;
        const now = Date.now();
        const per = s.config.secondsPerItem * 1000;
        if (s.status === "running") set({ itemDeadlineAt: now + per, updatedAt: now });
        else set({ itemRemainingMs: per, updatedAt: now });
      },
      tick: (now) => {
        const s = get();
        if (s.status !== "running" || s.itemDeadlineAt === null || !s.config) return;
        if (now < s.itemDeadlineAt) return;
        const per = s.config.secondsPerItem * 1000;
        const last = s.items.length - 1;
        if (s.currentIndex < last) {
          set({ currentIndex: s.currentIndex + 1, itemDeadlineAt: now + per, updatedAt: now, lastEvent: ev("advance", s.currentIndex + 1) });
        } else if (s.config.loopSession) {
          set({ currentIndex: 0, itemDeadlineAt: now + per, updatedAt: now, lastEvent: ev("loop", 0) });
        } else {
          set({ status: "finished", itemDeadlineAt: null, itemRemainingMs: 0, updatedAt: now, lastEvent: ev("finish", s.currentIndex) });
        }
      },
      finish: () => set({ status: "finished", itemDeadlineAt: null, itemRemainingMs: 0, updatedAt: Date.now(), lastEvent: ev("finish", get().currentIndex) }),
      reset: () => set({ ...initial, deviceId: get().deviceId, updatedAt: Date.now() }),
      setItems: (items) => {
        const s = get();
        if (!items.length) return; // an empty rebuild never wipes a session
        const cur = s.items[s.currentIndex];
        const found = cur ? items.findIndex((it) => it.id === cur.id) : -1;
        const idx = found >= 0 ? found : Math.min(s.currentIndex, items.length - 1);
        set({ items, currentIndex: idx });
      },
      setConfig: (patch) => {
        const s = get();
        if (!s.config) return;
        set({ config: { ...s.config, ...patch }, updatedAt: Date.now() });
      },
      hydrate: (state) => set({ ...state, status: state.status === "running" ? "paused" : state.status, itemRemainingMs: state.status === "running" ? Math.max(0, (state.itemDeadlineAt ?? Date.now()) - Date.now()) : state.itemRemainingMs, itemDeadlineAt: null, deviceId: get().deviceId || state.deviceId || uid() }),
    }),
    {
      name: "bebop.drill",
      version: 1,
      skipHydration: true,
      // a reload never auto-starts audio: a running drill comes back paused
      merge: (persisted, current) => {
        const p = (persisted ?? {}) as Partial<DrillState>;
        const now = Date.now();
        const running = p.status === "running";
        return {
          ...current,
          ...p,
          status: running ? "paused" : (p.status ?? "idle"),
          itemRemainingMs: running ? Math.max(0, (p.itemDeadlineAt ?? now) - now) : (p.itemRemainingMs ?? 0),
          itemDeadlineAt: null,
          lastEvent: null,
          deviceId: p.deviceId || uid(),
        };
      },
    },
  ),
);

export const selectRemainingSeconds = (s: DrillState, now = Date.now()) => {
  if (s.status === "running" && s.itemDeadlineAt !== null) return Math.max(0, Math.ceil((s.itemDeadlineAt - now) / 1000));
  return Math.max(0, Math.ceil(s.itemRemainingMs / 1000));
};
