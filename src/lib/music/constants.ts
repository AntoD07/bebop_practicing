// Mirrors scripts/domain/notes.py and scripts/fingering/positions.py. The live
// values are also served by GET /api/engine/positions (constants) — these are
// the synchronous defaults the stores need before any fetch.
export const PRACTICE_KEYS = ["C", "G", "D", "A", "E", "B", "F#", "F", "Bb", "Eb", "Ab", "Db"] as const;
export type PracticeKey = (typeof PRACTICE_KEYS)[number];

export const POSITIONS = [
  "CAGED E string root",
  "CAGED A string root",
  "Diagonal E string root",
  "Diagonal A string root",
  "More Horizontal, D string root",
] as const;
export type PositionName = (typeof POSITIONS)[number];

export const POSITION_SHORT: Record<PositionName, string> = {
  "CAGED E string root": "CAGED E",
  "CAGED A string root": "CAGED A",
  "Diagonal E string root": "Diag E",
  "Diagonal A string root": "Diag A",
  "More Horizontal, D string root": "Horiz D",
};

export const FREE_POSITION = "Free (best on the neck)";

export const CHORD_MODES = ["Maj7", "Minor", "Dorian", "Myxolidian", "Locrian", "MajorResolutions", "MinorResolutions"] as const;
export type ChordMode = (typeof CHORD_MODES)[number];

export const DEGREE_ORDER = ["1", "b9", "9", "#9", "3", "maj3", "4", "11", "#11", "5", "#5", "b6", "6", "b7", "7", "#7", "maj7"];
export const CHORD_TONES = ["1", "3", "5", "7"];
export const NOTE_OPTIONS = ["1", "9", "3", "4", "11", "#11", "5", "6", "7", "b7", "b6", "b9", "#9", "#7"];

export const LINE_TYPES = [
  "Maj7", "Minor", "Dorian", "Myxolidian", "Locrian",
  "Short Maj 2-5-1", "Long Maj 2-5-1", "Short Minor 2-5-1", "Long Minor 2-5-1",
  "Long Minor with double resolution", "Double resolution",
  "Minor and Dominant 2-cells alternated", "Minor x Dominant", "Major x Dominant",
  "Dorian x Myxolidian",
] as const;
export const COMBO_LINE_TYPE = "Dorian x Myxolidian";
export const DEFAULT_LINE_TYPE = "Long Maj 2-5-1";

export const DEFAULT_TEMPO = 85;

export function positionName(index: number): PositionName {
  return POSITIONS[Math.min(POSITIONS.length, Math.max(1, index)) - 1];
}

export function degreeSortKey(t: string): [number, string] {
  const i = DEGREE_ORDER.indexOf(t);
  return [i === -1 ? 99 : i, t];
}

export function joinNotes(degrees: readonly string[]): string {
  return degrees.join("-");
}
