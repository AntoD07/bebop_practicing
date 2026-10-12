"use client";

import { useEffect, useState } from "react";
import { audioEngine } from "./engine";
import type { EngineEvents } from "./types";

export function useEngineState() {
  const [state, setState] = useState<EngineEvents["state"]>({
    running: audioEngine.running,
    tempo: audioEngine.tempo,
    meter: audioEngine.meter,
    clickOn: audioEngine.clickOn,
    pattern: audioEngine.patternId,
  });
  useEffect(() => audioEngine.subscribe("state", setState), []);
  return state;
}

export function useBeat() {
  const [beat, setBeat] = useState<EngineEvents["beat"] | null>(null);
  useEffect(() => audioEngine.subscribe("beat", setBeat), []);
  return beat;
}

/** Installs the one-time gesture unlock (iOS needs a user gesture before any
 * sound) — mounted in the root layout. */
export function useAudioUnlock() {
  useEffect(() => {
    const unlock = () => {
      audioEngine.unlock();
    };
    window.addEventListener("pointerdown", unlock, { passive: true });
    window.addEventListener("keydown", unlock);
    return () => {
      window.removeEventListener("pointerdown", unlock);
      window.removeEventListener("keydown", unlock);
    };
  }, []);
}
