"use client";

import * as React from "react";
import { Play, Square, Repeat } from "lucide-react";
import { Button } from "@/components/ui/button";
import { audioEngine } from "@/lib/audio/engine";
import { patternFromPlaced } from "@/lib/audio/pattern";
import { useEngineState } from "@/lib/audio/useAudio";
import type { ChordJSON, PlacedJSON } from "@/lib/engine/types";
import { layoutColumns } from "@/lib/tab/geometry";
import { useSession } from "@/lib/store/session";
import { cn } from "@/lib/utils";
import { TabSvg, type TabOptions } from "./TabSvg";

export type TabPlayerProps = {
  placed: PlacedJSON[];
  chords?: ChordJSON[];
  beatsPerBar?: number;
  totalCost?: number | null;
  pivotIndices?: number[];
  options?: TabOptions;
  /** Stable id of the pattern (the layout string); same id = same pattern. */
  patternId: string;
  /** Loop the pattern on the transport (drill); off = play once. */
  loop?: boolean;
  onLoopChange?: (loop: boolean) => void;
  controls?: boolean;
  className?: string;
  svgRef?: React.Ref<SVGSVGElement>;
  /** When true the tab follows the transport's current pattern even if it was
   * set elsewhere (the drill sets patterns itself). */
  followTransport?: boolean;
};

/** TabSvg + Web-Audio play-along on the shared engine, with a playhead that
 * follows the engine's note events and scrolls into view. Mounted once per
 * place; switching the pattern only swaps the engine's pattern. */
export function TabPlayer({ placed, chords, beatsPerBar = 4, totalCost, pivotIndices, options, patternId, loop = false, onLoopChange, controls = true, className, svgRef, followTransport = false }: TabPlayerProps) {
  const playhead = React.useRef<SVGLineElement | null>(null);
  const wrap = React.useRef<HTMLDivElement | null>(null);
  const state = useEngineState();
  const countIn = useSession((s) => s.countInBars);
  const [active, setActive] = React.useState(false);
  const centres = React.useMemo(() => layoutColumns(placed).centres, [placed]);
  const pattern = React.useMemo(() => patternFromPlaced(placed, patternId), [placed, patternId]);
  const playing = state.running && state.pattern === patternId;

  // playhead follows the engine's note events for THIS pattern
  React.useEffect(() => {
    const offNote = audioEngine.subscribe("note", (e) => {
      if (e.patternId !== patternId) return;
      const ph = playhead.current;
      if (!ph) return;
      const xx = centres[e.index];
      if (xx === undefined) return;
      ph.setAttribute("x1", String(xx));
      ph.setAttribute("x2", String(xx));
      ph.setAttribute("opacity", "1");
      setActive(true);
      const el = wrap.current?.querySelector("div");
      if (el) {
        const left = xx - el.clientWidth / 2;
        if (Math.abs(el.scrollLeft - left) > el.clientWidth / 3) el.scrollTo({ left, behavior: "smooth" });
      }
    });
    const offEnd = audioEngine.subscribe("patternEnd", (e) => {
      if (e.patternId !== patternId) return;
      if (!audioEngine.running || audioEngine.patternId !== patternId || !loop) {
        playhead.current?.setAttribute("opacity", "0");
        setActive(false);
      }
    });
    const offState = audioEngine.subscribe("state", (s) => {
      if (!s.running || s.pattern !== patternId) {
        playhead.current?.setAttribute("opacity", "0");
        setActive(false);
      }
    });
    return () => {
      offNote();
      offEnd();
      offState();
    };
  }, [patternId, centres, loop]);

  // the drill keeps the engine's pattern itself; a standalone player sets it
  React.useEffect(() => {
    if (followTransport) return;
    if (audioEngine.running && audioEngine.patternId === patternId) {
      audioEngine.setPattern(pattern, { loop, atNextBar: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pattern, loop]);

  async function play() {
    if (playing) {
      if (loop) audioEngine.setPattern(null);
      else audioEngine.stop();
      return;
    }
    if (audioEngine.running) {
      audioEngine.setPattern(pattern, { loop, atNextBar: true });
      return;
    }
    if (loop) {
      audioEngine.setPattern(pattern, { loop: true });
      await audioEngine.start({ countInBars: countIn });
    } else {
      await audioEngine.playOnce(pattern);
    }
  }

  return (
    <div ref={wrap} className={cn("space-y-2", className)}>
      <TabSvg placed={placed} chords={chords} beatsPerBar={beatsPerBar} totalCost={totalCost} pivotIndices={pivotIndices} options={options} playheadRef={playhead} svgRef={svgRef} />
      {controls && (
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" variant={playing || active ? "default" : "outline"} onClick={play} aria-label={playing ? "Stop" : "Play"}>
            {playing || active ? <Square size={14} /> : <Play size={14} />}
            {playing || active ? "Stop" : loop ? "Play (loop)" : "Play"}
          </Button>
          {onLoopChange && (
            <Button size="sm" variant={loop ? "soft" : "ghost"} onClick={() => onLoopChange(!loop)} aria-pressed={loop}>
              <Repeat size={14} /> Loop
            </Button>
          )}
          <span className="text-xs text-fg-muted">{state.tempo} bpm · {beatsPerBar}/4 bars{loop ? " · loops on the click" : ""}</span>
        </div>
      )}
    </div>
  );
}
