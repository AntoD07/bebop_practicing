import { describe, expect, it } from "vitest";
import { barColumns, cellSpans, chordAt, layoutColumns } from "./geometry";

describe("tab geometry", () => {
  it("lays out columns like render.py", () => {
    const l = layoutColumns([{ grace: false }, { grace: true }, { grace: false }]);
    expect(l.starts).toEqual([70, 132, 168]);
    expect(l.centres).toEqual([101, 150, 199]);
    expect(l.right).toBe(230);
  });
  it("groups cell spans and bar columns", () => {
    expect(cellSpans([{ cell: "a" }, { cell: "a" }, { cell: "b" }, { cell: null }, { cell: "b" }])).toEqual([
      { a: 0, b: 1, name: "a" },
      { a: 2, b: 2, name: "b" },
      { a: 4, b: 4, name: "b" },
    ]);
    expect(barColumns([{ onset: 0 }, { onset: 0.5 }, { onset: 4 }, { onset: 4.5 }, { onset: 8 }], 4)).toEqual([0, 2, 4, 5]);
  });
  it("finds the active chord", () => {
    const ch = [
      { start_beat: 0, symbol: "Fm7" },
      { start_beat: 2, symbol: "Bb7" },
    ];
    expect(chordAt(ch, 1.5)).toBe("Fm7");
    expect(chordAt(ch, 2)).toBe("Bb7");
    expect(chordAt([], 0)).toBeNull();
  });
});
