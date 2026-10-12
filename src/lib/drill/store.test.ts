import { beforeEach, describe, expect, it, vi } from "vitest";
import type { DrillItem } from "./buildItems";
import { selectRemainingSeconds, useDrill } from "./store";
import type { DrillConfig } from "./types";

const items: DrillItem[] = ["a", "b", "c"].map((id, i) => ({ id, pairKey: id, end: { id, name: id, degrees: [], movement: null }, start: { id, name: id, degrees: [], movement: null }, layoutSig: id, k: 1, m: 1, cost: i }));
const cfg: DrillConfig = { pickKey: null, request: { key: "C", pairs: { chord1: "Maj7", chord2: "Maj7" }, position: null, anchor: "key", flags: { bonus: false, domToMinor1: false, domToMinor2: false } }, totalMinutes: 1, secondsPerItem: 10, allFingerings: false, showTab: true, switchMode: "reset", cue: true, loopSession: false };

describe("drill store", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(1_000_000);
    useDrill.getState().reset();
  });
  it("starts, counts down and auto-advances with cues", () => {
    const d = useDrill.getState();
    d.start(items, cfg);
    expect(useDrill.getState().status).toBe("running");
    expect(selectRemainingSeconds(useDrill.getState())).toBe(10);
    vi.setSystemTime(1_000_000 + 10_000);
    useDrill.getState().tick(Date.now());
    expect(useDrill.getState().currentIndex).toBe(1);
    expect(useDrill.getState().lastEvent?.type).toBe("advance");
  });
  it("pause freezes and resume restores the remaining time", () => {
    useDrill.getState().start(items, cfg);
    vi.setSystemTime(1_000_000 + 4_000);
    useDrill.getState().pause();
    expect(useDrill.getState().status).toBe("paused");
    expect(selectRemainingSeconds(useDrill.getState())).toBe(6);
    vi.setSystemTime(1_000_000 + 60_000);
    useDrill.getState().resume();
    expect(selectRemainingSeconds(useDrill.getState())).toBe(6);
  });
  it("next/prev/jumpTo work running and paused, reset the clock by default", () => {
    useDrill.getState().start(items, cfg);
    vi.setSystemTime(1_000_000 + 7_000);
    useDrill.getState().next();
    expect(useDrill.getState().currentIndex).toBe(1);
    expect(selectRemainingSeconds(useDrill.getState())).toBe(10);
    useDrill.getState().pause();
    useDrill.getState().jumpTo(2);
    expect(useDrill.getState().currentIndex).toBe(2);
    expect(useDrill.getState().status).toBe("paused");
    useDrill.getState().prev();
    useDrill.getState().prev();
    useDrill.getState().prev();
    expect(useDrill.getState().currentIndex).toBe(0);
  });
  it("keep mode keeps the remaining time across a switch", () => {
    useDrill.getState().start(items, { ...cfg, switchMode: "keep" });
    vi.setSystemTime(1_000_000 + 7_000);
    useDrill.getState().next();
    expect(selectRemainingSeconds(useDrill.getState())).toBe(3);
  });
  it("finishes on the last item unless looping", () => {
    useDrill.getState().start(items, cfg, 2);
    vi.setSystemTime(1_000_000 + 10_000);
    useDrill.getState().tick(Date.now());
    expect(useDrill.getState().status).toBe("finished");
    useDrill.getState().start(items, { ...cfg, loopSession: true }, 2);
    vi.setSystemTime(1_000_000 + 20_000);
    useDrill.getState().tick(Date.now());
    expect(useDrill.getState().currentIndex).toBe(0);
    expect(useDrill.getState().status).toBe("running");
  });
  it("jumpTo from idle starts the drill", () => {
    useDrill.getState().start(items, cfg);
    useDrill.getState().finish();
    useDrill.getState().jumpTo(1);
    expect(useDrill.getState().status).toBe("running");
    expect(useDrill.getState().currentIndex).toBe(1);
  });
  it("hydrating a running state lands paused with the remaining time", () => {
    const now = Date.now();
    useDrill.getState().hydrate({ status: "running", config: cfg, items, currentIndex: 1, itemRemainingMs: 0, itemDeadlineAt: now + 4000, sessionStartedAt: now, updatedAt: now, deviceId: "x", lastEvent: null });
    expect(useDrill.getState().status).toBe("paused");
    expect(selectRemainingSeconds(useDrill.getState())).toBe(4);
  });
});
