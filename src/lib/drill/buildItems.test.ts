import { describe, expect, it } from "vitest";
import type { FingeringJSON } from "@/lib/engine/types";
import { buildItems, secondsPerItem } from "./buildItems";

const f = (layout: string, cost: number) => ({ layout, cost }) as unknown as FingeringJSON;
const cell = (id: string) => ({ id, name: id, degrees: ["1"], movement: "A" });

describe("buildItems", () => {
  const rows = [
    { pairKey: "a → b", end: cell("a"), start: cell("b"), candidates: [f("L1", 5), f("L2", 9), f("L3", 12)] },
    { pairKey: "c → d", end: cell("c"), start: cell("d"), candidates: [f("L4", 3), f("L5", 20)] },
    { pairKey: "e → f", end: cell("e"), start: cell("f"), candidates: [] },
  ];
  it("one cheapest kept fingering per kept pair, sorted by cost", () => {
    const items = buildItems(rows, { kept: () => true, deleted: () => new Set(), allFingerings: false });
    expect(items.map((i) => i.id)).toEqual(["c → d#L4", "a → b#L1"]);
    expect(items[0]).toMatchObject({ k: 1, m: 1, cost: 3 });
  });
  it("skips deleted fingerings and unkept pairs", () => {
    const items = buildItems(rows, { kept: (k) => k !== "c → d", deleted: (k) => (k === "a → b" ? new Set(["L1"]) : new Set()), allFingerings: true });
    expect(items.map((i) => i.id)).toEqual(["a → b#L2", "a → b#L3"]);
    expect(items[1]).toMatchObject({ k: 2, m: 2 });
  });
  it("splits the session time", () => {
    expect(secondsPerItem(10, 24)).toBe(25);
    expect(secondsPerItem(10, 0)).toBe(0);
    expect(secondsPerItem(1, 1000)).toBe(1);
  });
});
