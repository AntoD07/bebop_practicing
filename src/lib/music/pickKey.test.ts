import { describe, expect, it } from "vitest";
import { pairKey, pickKey } from "./pickKey";

// Keys found in the real data/logs/connection_picks.json (2026-07) and the
// forms page 1 produced for the other anchor/combination cases.
describe("pickKey", () => {
  it("reproduces the saved single-chord key", () => {
    expect(pickKey({ chord1: "Myxolidian", chord2: "Myxolidian", rawPivot: "6", myxoToDorian: false, position: "CAGED A string root", anchor: "key", singleChord: true })).toBe(
      "Myxolidian|Myxolidian|6|CAGED A string root",
    );
  });
  it("namespaces the ii-spelled pivot and the key anchor", () => {
    expect(pickKey({ chord1: "Dorian", chord2: "Myxolidian", rawPivot: "3", myxoToDorian: true, position: null, anchor: "key", singleChord: false })).toBe(
      "Dorian|Myxolidian|ii:3|Free (best on the neck)|anchor:key",
    );
  });
  it("marks the 2nd-chord anchor and omits the 1st", () => {
    expect(pickKey({ chord1: "Myxolidian", chord2: "MajorResolutions", rawPivot: "b9", myxoToDorian: false, position: null, anchor: "chord2", singleChord: false })).toBe(
      "Myxolidian|MajorResolutions|b9|Free (best on the neck)|anchor:2nd",
    );
    expect(pickKey({ chord1: "Myxolidian", chord2: "MajorResolutions", rawPivot: "3", myxoToDorian: false, position: "CAGED E string root", anchor: "chord1", singleChord: false })).toBe(
      "Myxolidian|MajorResolutions|3|CAGED E string root",
    );
  });
  it("pair keys use the arrow", () => {
    expect(pairKey("Minor Honeysuckle Rose", "Hidden Ideal maj7 Arpeggio to 13th (Mccoy)")).toBe("Minor Honeysuckle Rose → Hidden Ideal maj7 Arpeggio to 13th (Mccoy)");
  });
});
