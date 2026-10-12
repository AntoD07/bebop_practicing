"use client";

import * as React from "react";
import { audioEngine } from "@/lib/audio/engine";
import { patternFromFingering } from "@/lib/audio/pattern";
import { fingeringFor, selectRemainingSeconds, useDrill } from "@/lib/drill/store";
import { useDrillSync } from "@/lib/drill/sync";
import { acquireWakeLock, releaseWakeLock } from "@/lib/drill/wakeLock";
import { useConnections } from "@/lib/store/connections";
import { useSession } from "@/lib/store/session";
import { toast } from "@/components/ui/misc";

function isTyping(e: KeyboardEvent) {
  const t = e.target as HTMLElement | null;
  if (!t) return false;
  const tag = t.tagName;
  return tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA" || t.isContentEditable;
}

/** Mounted ONCE in the app layout: the drill's clock, its audio side effects
 * (click / pattern / cues on the shared engine), the wake lock, keyboard
 * shortcuts and the server sync. The store holds the state; this drives it. */
export function DrillController() {
  // adopt a newer remote drill (paused): point the Connections page at its setup
  useDrillSync(() => {
    const cfg = useDrill.getState().config;
    if (!cfg) return;
    const r = cfg.request;
    useConnections.getState().set({
      chord1: r.pairs.chord1, chord2: r.pairs.chord2, bonus: r.flags.bonus, domToMinor1: r.flags.domToMinor1, domToMinor2: r.flags.domToMinor2,
      movement: (r.pairs.movement ?? "") as "" | "A" | "D", pivot: r.pairs.pivot ?? null, enforce: !!r.position, anchor: r.anchor,
      allFingerings: cfg.allFingerings, totalMinutes: cfg.totalMinutes, showTab: cfg.showTab,
    });
    toast("Resumed the drill from your other device (paused)");
  });

  // clock + pattern sync + countdown cues
  React.useEffect(() => {
    let lastRemaining = -1;
    let lastPatternKey: string | null = null;
    const sync = () => {
      const s = useDrill.getState();
      if (s.status !== "running") {
        lastPatternKey = null;
        return;
      }
      const item = s.items[s.currentIndex];
      if (!item) return;
      const f = fingeringFor(item.id);
      if (f && (lastPatternKey !== item.id || audioEngine.patternId !== item.id)) {
        audioEngine.setPattern(patternFromFingering(f, item.id), { loop: true, atNextBar: true });
        lastPatternKey = item.id;
      }
    };
    const tick = () => {
      const s = useDrill.getState();
      if (s.status !== "running") return;
      s.tick(Date.now());
      const after = useDrill.getState();
      const rem = selectRemainingSeconds(after);
      if (after.config?.cue && rem !== lastRemaining && rem >= 1 && rem <= 3 && after.status === "running") audioEngine.cue("tick");
      lastRemaining = rem;
      sync();
    };
    const id = setInterval(tick, 200);
    const onVis = () => tick();
    document.addEventListener("visibilitychange", onVis);
    const unsub = useDrill.subscribe((s, prev) => {
      if (s.status !== prev.status) {
        if (s.status === "running") {
          acquireWakeLock();
          const item = s.items[s.currentIndex];
          const f = item ? fingeringFor(item.id) : undefined;
          if (f) {
            audioEngine.setPattern(patternFromFingering(f, item.id), { loop: true, atNextBar: true });
            lastPatternKey = item.id;
          }
          if (!audioEngine.running) audioEngine.start({ countInBars: useSession.getState().countInBars });
        } else {
          releaseWakeLock();
          lastPatternKey = null;
          if (prev.status === "running") {
            audioEngine.setPattern(null);
            audioEngine.stop();
          }
          if (s.status === "finished" && s.config?.cue) audioEngine.cue("done");
        }
      } else if (s.status === "running" && s.currentIndex !== prev.currentIndex) {
        sync();
        if (s.config?.cue && s.lastEvent && s.lastEvent !== prev.lastEvent && (s.lastEvent.type === "advance" || s.lastEvent.type === "loop")) audioEngine.cue("next");
      }
    });
    return () => {
      clearInterval(id);
      document.removeEventListener("visibilitychange", onVis);
      unsub();
    };
  }, []);

  // keyboard shortcuts (ignored while typing)
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (isTyping(e) || e.metaKey || e.ctrlKey || e.altKey) return;
      const d = useDrill.getState();
      if (d.status === "idle" && e.key !== "m" && e.key !== "M") return;
      switch (e.key) {
        case " ":
          e.preventDefault();
          if (d.status === "running") d.pause();
          else if (d.status === "paused") d.resume();
          else if (d.status === "finished") d.jumpTo(0);
          break;
        case "ArrowRight":
          e.preventDefault();
          d.next();
          break;
        case "ArrowLeft":
          e.preventDefault();
          d.prev();
          break;
        case "r":
        case "R":
          d.restartItem();
          break;
        case "l":
        case "L":
          d.setConfig({ loopSession: !d.config?.loopSession });
          break;
        case "t":
        case "T":
          d.setConfig({ showTab: !d.config?.showTab });
          break;
        case "m":
        case "M": {
          const s = useSession.getState();
          s.setClickOn(!s.clickOn);
          break;
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return null;
}
