import type { PairsRequest } from "@/lib/engine/types";
import type { Anchor } from "@/lib/music/pickKey";
import type { DrillItem } from "./buildItems";

export type DrillStatus = "idle" | "running" | "paused" | "finished";

export type DrillRequest = {
  key: string;
  pairs: PairsRequest;
  position: string | null;
  anchor: Anchor;
  flags: { bonus: boolean; domToMinor1: boolean; domToMinor2: boolean };
};

export type DrillConfig = {
  pickKey: string | null;
  request: DrillRequest;
  totalMinutes: number;
  secondsPerItem: number;
  allFingerings: boolean;
  showTab: boolean;
  switchMode: "reset" | "keep";
  cue: boolean;
  loopSession: boolean;
};

export type DrillState = {
  status: DrillStatus;
  config: DrillConfig | null;
  items: DrillItem[];
  currentIndex: number;
  itemRemainingMs: number; // meaningful while paused
  itemDeadlineAt: number | null; // epoch ms while running
  sessionStartedAt: number | null;
  updatedAt: number;
  deviceId: string;
  /** monotonically increasing: the last auto-advance / finish event (for cues) */
  lastEvent: { seq: number; type: "advance" | "finish" | "jump" | "start" | "loop"; index: number } | null;
};
