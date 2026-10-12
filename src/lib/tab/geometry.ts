// The tab's geometry = scripts/fingering/render.py (render_svg), shared by the
// SVG component and the audio playhead so they can never disagree.
import type { ChordJSON } from "@/lib/engine/types";

export const GEO = {
  left: 70,
  top: 96,
  rowH: 26,
  col: 62,
  graceCol: 36,
  rightPad: 40,
  laneChord: 22,
  laneCell: 40,
  laneDegree: 64,
  compactTop: 60,
} as const;

export const STRING_NAMES: Record<number, string> = { 1: "e", 2: "B", 3: "G", 4: "D", 5: "A", 6: "E" };
export const COLORS = {
  bg: "#fbfaf7",
  chord: "#1a3a8f",
  cell: "#b06a00",
  degree: "#3a7d3a",
  up: "#c0392b",
  upBox: "#fdeaea",
  down: "#222",
  legato: "#8a7f6a",
  staff: "#cfc9bd",
  bar: "#9a9384",
  finger: "#777",
  label: "#888",
  pivot: "#1a3a8f",
} as const;

export type ColumnLayout = { starts: number[]; centres: number[]; right: number };

/** Per-note column x positions (grace notes are narrower). Pure. */
export function layoutColumns(placed: { grace?: boolean }[], left = GEO.left, col = GEO.col, graceCol = GEO.graceCol): ColumnLayout {
  const starts: number[] = [];
  const centres: number[] = [];
  let acc = left;
  for (const p of placed) {
    const w = p.grace ? graceCol : col;
    starts.push(acc);
    centres.push(acc + Math.floor(w / 2));
    acc += w;
  }
  return { starts, centres, right: acc };
}

export function cellSpans(placed: { cell: string | null }[]): { a: number; b: number; name: string }[] {
  const out: { a: number; b: number; name: string }[] = [];
  let i = 0;
  while (i < placed.length) {
    const c = placed[i].cell;
    if (c === null || c === undefined) {
      i++;
      continue;
    }
    let j = i;
    while (j + 1 < placed.length && placed[j + 1].cell === c) j++;
    out.push({ a: i, b: j, name: c });
    i = j + 1;
  }
  return out;
}

export function barIndex(onset: number, beatsPerBar: number) {
  return Math.floor(onset / beatsPerBar);
}

export function barColumns(placed: { onset: number }[], beatsPerBar: number): number[] {
  const n = placed.length;
  const cols = [0];
  for (let i = 1; i < n; i++) if (barIndex(placed[i].onset, beatsPerBar) > barIndex(placed[i - 1].onset, beatsPerBar)) cols.push(i);
  cols.push(n);
  return cols;
}

export function chordAt(chords: ChordJSON[] | undefined, onset: number): string | null {
  let active: string | null = null;
  let start = -1;
  for (const c of chords ?? []) {
    if (c.start_beat <= onset + 1e-6 && c.start_beat >= start) {
      active = c.symbol;
      start = c.start_beat;
    }
  }
  return active;
}

export const GLYPH: Record<string, string> = { D: "⊓", U: "∨", po: "p", h: "h" };

export function fingerStr(p: { finger: number; stretch: boolean }) {
  if (p.finger === 0) return "0";
  return `${p.finger}${p.stretch ? "*" : ""}`;
}
