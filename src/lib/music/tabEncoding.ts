// The compact "5/3D 4/2D 4/5U" fingering encoding (the legacy log's Tab
// column and the API's `encoding`) <-> placed notes, so migrated lines render.
import type { PlacedJSON } from "@/lib/engine/types";

export const TUNING_MIDI: Record<number, number> = { 1: 64, 2: 59, 3: 55, 4: 50, 5: 45, 6: 40 };
const PC_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];

export function midiToName(m: number) {
  return `${PC_NAMES[((m % 12) + 12) % 12]}${Math.floor(m / 12) - 1}`;
}

export type EncodedNote = { string: number; fret: number; stroke: "D" | "U" | "h" | "po" };

export function parseEncoding(enc: string): EncodedNote[] {
  const out: EncodedNote[] = [];
  for (const tok of enc.trim().split(/\s+/)) {
    if (!tok) continue;
    const m = /^(\d)\/(\d{1,2})(D|U|h|po)?$/.exec(tok);
    if (!m) throw new Error(`bad tab token ${tok}`);
    out.push({ string: Number(m[1]), fret: Number(m[2]), stroke: (m[3] ?? "D") as EncodedNote["stroke"] });
  }
  return out;
}

export function encode(placed: { string: number; fret: number; stroke: string }[]): string {
  return placed.map((p) => `${p.string}/${p.fret}${p.stroke}`).join(" ");
}

export function layoutOf(placed: { string: number; fret: number }[]): string {
  return placed.map((p) => `${p.string}/${p.fret}`).join(" ");
}

/** Placed notes from an encoding on the cell grid (eighth notes, 4/4),
 * optionally with degree/cell labels per note. */
export function placedFromEncoding(enc: string, opts: { beatsPerBar?: number; noteBeats?: number; degrees?: (string | null)[]; cells?: (string | null)[] } = {}): PlacedJSON[] {
  const bpb = opts.beatsPerBar ?? 4;
  const nb = opts.noteBeats ?? 0.5;
  return parseEncoding(enc).map((n, i) => {
    const onset = i * nb;
    const midi = TUNING_MIDI[n.string] + n.fret;
    return {
      i,
      midi,
      name: midiToName(midi),
      onset,
      beat: (onset % bpb) + 1,
      string: n.string,
      fret: n.fret,
      finger: 0,
      stretch: false,
      stroke: n.stroke,
      run_len: 1,
      rest: n.stroke === "D" && n.string > 1,
      role: null,
      degree: opts.degrees?.[i] ?? null,
      cell: opts.cells?.[i] ?? null,
      phrase_start: i === 0,
      grace: false,
    };
  });
}
