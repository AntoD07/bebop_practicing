import { describe, expect, it } from "vitest";
import { encode, layoutOf, parseEncoding, placedFromEncoding } from "./tabEncoding";

describe("tab encoding", () => {
  it("parses legacy strings", () => {
    expect(parseEncoding("5/3D 4/2D 4/5U")).toEqual([
      { string: 5, fret: 3, stroke: "D" },
      { string: 4, fret: 2, stroke: "D" },
      { string: 4, fret: 5, stroke: "U" },
    ]);
  });
  it("round-trips", () => {
    const enc = "3/14D 3/12U 4/14D";
    expect(encode(parseEncoding(enc))).toBe(enc);
    expect(layoutOf(parseEncoding(enc))).toBe("3/14 3/12 4/14");
  });
  it("rejects garbage", () => {
    expect(() => parseEncoding("x/y")).toThrow();
  });
  it("builds placed notes on the eighth grid", () => {
    const p = placedFromEncoding("5/3D 4/2D 4/5U 3/2D 3/5D");
    expect(p.map((x) => x.midi)).toEqual([48, 52, 55, 57, 60]);
    expect(p.map((x) => x.beat)).toEqual([1, 1.5, 2, 2.5, 3]);
    expect(p[2].stroke).toBe("U");
  });
});
