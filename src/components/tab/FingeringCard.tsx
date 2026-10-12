"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import type { FingeringJSON } from "@/lib/engine/types";
import { TabPlayer } from "./TabPlayer";
import { NoteTable } from "./NoteTable";
import { FullReport } from "./FullReport";
import { TabActions } from "./TabActions";
import type { TabOptions } from "./TabSvg";

/** The standard "a fingering" block: tab + play-along, details toggles. */
export function FingeringCard({ fingering, pivotIndices, title, caption, options, filename, loopDefault = false, children }: { fingering: FingeringJSON; pivotIndices?: number[]; title?: React.ReactNode; caption?: React.ReactNode; options?: TabOptions; filename?: string; loopDefault?: boolean; children?: React.ReactNode }) {
  const svgRef = React.useRef<SVGSVGElement | null>(null);
  const [loop, setLoop] = React.useState(loopDefault);
  const [showNotes, setShowNotes] = React.useState(false);
  const [showReport, setShowReport] = React.useState(false);
  return (
    <div className="space-y-2 rounded-xl border bg-bg-elev p-3">
      {(title || caption) && (
        <div>
          {title && <div className="text-sm font-semibold">{title}</div>}
          {caption && <div className="text-xs text-fg-muted">{caption}</div>}
        </div>
      )}
      <TabPlayer placed={fingering.placed} chords={fingering.chords} beatsPerBar={fingering.beats_per_bar} totalCost={fingering.cost} pivotIndices={pivotIndices} options={options} patternId={fingering.layout} loop={loop} onLoopChange={setLoop} svgRef={svgRef} />
      {fingering.warnings.map((w, i) => (
        <p key={i} className="text-xs text-warn">
          {w}
        </p>
      ))}
      <div className="flex flex-wrap items-center gap-2">
        <TabActions svgRef={svgRef} encoding={fingering.encoding} filename={filename} />
        <Button size="sm" variant="ghost" onClick={() => setShowNotes((v) => !v)}>
          {showNotes ? "Hide notes" : "Per-note detail"}
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setShowReport((v) => !v)}>
          {showReport ? "Hide report" : "Full report"}
        </Button>
        {children}
      </div>
      {showNotes && <NoteTable placed={fingering.placed} />}
      {showReport && <FullReport fingering={fingering} />}
    </div>
  );
}
