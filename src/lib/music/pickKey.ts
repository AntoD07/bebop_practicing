import { FREE_POSITION } from "./constants";

export type Anchor = "key" | "chord1" | "chord2";

/** The connection_picks key, byte-for-byte as the Streamlit page built it
 * (scripts/domain/connections.py `pick_key` mirrors this):
 * `chord1|chord2|[ii:]rawPivot|position[|anchor:key|anchor:2nd]`. */
export function pickKey(args: { chord1: string; chord2: string; rawPivot: string; myxoToDorian: boolean; position: string | null; anchor: Anchor; singleChord: boolean }): string {
  const { chord1, chord2, rawPivot, myxoToDorian, position, anchor, singleChord } = args;
  const parts = [chord1, chord2, (myxoToDorian ? "ii:" : "") + String(rawPivot), position ?? FREE_POSITION];
  if (anchor === "key" && !singleChord) parts.push("anchor:key");
  else if (anchor === "chord2") parts.push("anchor:2nd");
  return parts.join("|");
}

export function pairKey(end: string, start: string): string {
  return `${end} → ${start}`;
}
