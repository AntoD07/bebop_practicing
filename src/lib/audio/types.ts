export type PatternNote = { midi: number; start: number; dur: number; legato?: boolean };
/** A play-along pattern: onsets in beats from the pattern's start (its first
 * note is beat 0 of a bar), `beats` = total length in beats (loop length is
 * rounded up to whole click bars). */
export type Pattern = { id: string; notes: PatternNote[]; beats: number };

export type BeatEvent = { bar: number; beat: number; time: number; countIn: boolean; absBeat: number };
export type NoteEvent = { patternId: string; index: number; time: number; midi: number; loopIndex: number };
export type EngineEvents = {
  beat: BeatEvent;
  note: NoteEvent;
  patternStart: { patternId: string; time: number; loopIndex: number };
  patternEnd: { patternId: string; time: number; loopIndex: number };
  state: { running: boolean; tempo: number; meter: number; clickOn: boolean; pattern: string | null };
};
export type CueKind = "three" | "two" | "one" | "next" | "done" | "tick";
