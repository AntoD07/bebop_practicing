import type { FingeringJSON, PlacedJSON } from "@/lib/engine/types";
import type { Pattern } from "./types";

/** A play-along pattern from a fingering: onset-based (grace notes steal time),
 * legato notes sound softer, the last note rings one beat. */
export function patternFromPlaced(placed: PlacedJSON[], id: string): Pattern {
  if (!placed.length) return { id, notes: [], beats: 0 };
  const base = placed[0].onset;
  const notes = placed.map((p, i) => {
    const start = p.onset - base;
    const next = i + 1 < placed.length ? placed[i + 1].onset - base : start + 1;
    return { midi: p.midi, start, dur: Math.max(0.08, next - start), legato: p.stroke === "h" || p.stroke === "po" };
  });
  const last = notes[notes.length - 1];
  return { id, notes, beats: last.start + last.dur };
}

export function patternFromFingering(f: FingeringJSON, id = f.layout): Pattern {
  return patternFromPlaced(f.placed, id);
}
