"use client";

import * as React from "react";
import type { ChordJSON, PlacedJSON } from "@/lib/engine/types";
import { COLORS, GEO, STRING_NAMES, GLYPH, barColumns, cellSpans, chordAt, fingerStr, layoutColumns } from "@/lib/tab/geometry";
import { cn } from "@/lib/utils";

export type TabOptions = {
  showChords?: boolean;
  showCells?: boolean;
  showDegrees?: boolean;
  showFingers?: boolean;
  showLegend?: boolean;
  compact?: boolean;
};

export type TabSvgProps = {
  placed: PlacedJSON[];
  chords?: ChordJSON[];
  beatsPerBar?: number;
  totalCost?: number | null;
  pivotIndices?: number[];
  highlightIndex?: number | null;
  options?: TabOptions;
  playheadRef?: React.Ref<SVGLineElement>;
  svgRef?: React.Ref<SVGSVGElement>;
  className?: string;
  onNoteClick?: (i: number) => void;
};

const DEFAULTS: Required<TabOptions> = { showChords: true, showCells: true, showDegrees: true, showFingers: true, showLegend: true, compact: false };

/** The SoundSlice-style tab: string 1 (high e) on top, picking marks above,
 * chord / cell / degree lanes, fret numbers boxed (upstrokes tinted). Pure. */
export function TabSvg({ placed, chords, beatsPerBar = 4, totalCost, pivotIndices = [], highlightIndex = null, options, playheadRef, svgRef, className, onNoteClick }: TabSvgProps) {
  const o = { ...DEFAULTS, ...(options ?? {}) };
  const n = placed.length;
  const { starts, centres, right } = layoutColumns(placed);
  const top = o.compact ? GEO.compactTop : GEO.top;
  const rowH = GEO.rowH;
  const staffH = rowH * 5;
  const width = right + GEO.rightPad;
  const height = top + staffH + (o.compact ? 30 : o.showLegend ? 90 : 56);
  const spans = o.showCells ? cellSpans(placed) : [];
  const bars = barColumns(placed, beatsPerBar);
  const pivots = new Set(pivotIndices);
  const x = (i: number) => centres[i];
  const sy = (s: number) => top + (s - 1) * rowH;

  let lastChord: string | null = null;
  const chordLabels: { i: number; sym: string }[] = [];
  if (o.showChords && chords?.length) {
    for (let i = 0; i < n; i++) {
      const sym = chordAt(chords, placed[i].onset);
      if (sym && sym !== lastChord) {
        chordLabels.push({ i, sym });
        lastChord = sym;
      }
    }
  }

  return (
    <div className={cn("overflow-x-auto touch-pan-x rounded-lg", className)}>
      <svg ref={svgRef} xmlns="http://www.w3.org/2000/svg" width={width} height={height} viewBox={`0 0 ${width} ${height}`} fontFamily="Menlo,Consolas,monospace" className="block select-none" role="img" aria-label="guitar tab">
        <rect x={0} y={0} width={width} height={height} fill={COLORS.bg} />
        {/* pivot columns */}
        {Array.from(pivots).map((i) =>
          i >= 0 && i < n ? <rect key={`pv${i}`} x={starts[i]} y={top - 20} width={(i + 1 < n ? starts[i + 1] : right) - starts[i]} height={staffH + 40} fill={COLORS.pivot} fillOpacity={0.07} /> : null,
        )}
        {/* highlighted (current) column */}
        {highlightIndex !== null && highlightIndex >= 0 && highlightIndex < n && (
          <rect x={starts[highlightIndex]} y={top - 20} width={(highlightIndex + 1 < n ? starts[highlightIndex + 1] : right) - starts[highlightIndex]} height={staffH + 40} fill={COLORS.up} fillOpacity={0.6} />
        )}
        {/* chord lane */}
        {!o.compact &&
          chordLabels.map(({ i, sym }) => (
            <text key={`ch${i}`} x={x(i)} y={GEO.laneChord} fill={COLORS.chord} fontSize={15} fontWeight="bold" textAnchor="middle">
              {sym}
            </text>
          ))}
        {/* cell brackets */}
        {!o.compact &&
          spans.map(({ a, b, name }) => {
            const x0 = starts[a] + 6;
            const x1 = (b + 1 < n ? starts[b + 1] : right) - 6;
            const y = GEO.laneCell;
            return (
              <g key={`cs${a}`}>
                <path d={`M${x0},${y + 6} L${x0},${y} L${x1},${y} L${x1},${y + 6}`} stroke={COLORS.cell} fill="none" strokeWidth={1.4} />
                <text x={(x0 + x1) / 2} y={y - 3} fill={COLORS.cell} fontSize={11} textAnchor="middle">
                  {name}
                </text>
              </g>
            );
          })}
        {/* degrees + picking */}
        {placed.map((p, i) => {
          const lab = p.degree || p.role || "";
          const gcol = p.stroke === "U" ? COLORS.up : p.stroke === "h" || p.stroke === "po" ? COLORS.legato : COLORS.down;
          return (
            <g key={`lab${i}`}>
              {o.showDegrees && lab && (
                <text x={x(i)} y={o.compact ? top - 26 : GEO.laneDegree} fill={p.grace ? "#999" : COLORS.degree} fontSize={p.grace ? 10 : 12} textAnchor="middle">
                  {lab}
                </text>
              )}
              <text x={x(i)} y={top - 6} fontSize={p.grace ? 12 : 15} textAnchor="middle" fill={gcol}>
                {GLYPH[p.stroke] ?? p.stroke}
              </text>
            </g>
          );
        })}
        {/* staff */}
        {[1, 2, 3, 4, 5, 6].map((s) => (
          <g key={`st${s}`}>
            <line x1={GEO.left - 10} y1={sy(s)} x2={right} y2={sy(s)} stroke={COLORS.staff} strokeWidth={1} />
            <text x={GEO.left - 24} y={sy(s) + 4} fontSize={12} fill={COLORS.label}>
              {STRING_NAMES[s]}
            </text>
          </g>
        ))}
        {/* bar lines */}
        {bars.map((i, k) => {
          const bx = i < n ? starts[i] : right;
          return <line key={`bar${k}`} x1={bx} y1={top} x2={bx} y2={top + staffH} stroke={COLORS.bar} strokeWidth={1.5} />;
        })}
        {/* slur arcs for legato notes */}
        {placed.map((p, i) => {
          if (i === 0 || (p.stroke !== "h" && p.stroke !== "po")) return null;
          const y0 = sy(placed[i - 1].string);
          const y1 = sy(p.string);
          const ytop = Math.min(y0, y1) - 15;
          return (
            <g key={`sl${i}`}>
              <path d={`M${x(i - 1)},${Math.min(y0, y1) - 12} Q${(x(i - 1) + x(i)) / 2},${ytop - 8} ${x(i)},${Math.min(y0, y1) - 12}`} stroke={COLORS.legato} fill="none" strokeWidth={1.8} />
              <text x={(x(i - 1) + x(i)) / 2} y={ytop - 11} fill={COLORS.legato} fontSize={11} fontWeight="bold" textAnchor="middle">
                {p.stroke === "h" ? "H" : "P"}
              </text>
            </g>
          );
        })}
        {/* fret boxes */}
        {placed.map((p, i) => {
          const yy = sy(p.string);
          const w = p.grace ? 18 : 24;
          const h = p.grace ? 17 : 22;
          const fs = p.grace ? 11 : 13;
          const fill = p.grace ? "#f6f2ff" : p.stroke === "U" ? COLORS.upBox : "#ffffff";
          return (
            <g key={`fr${i}`} onClick={onNoteClick ? () => onNoteClick(i) : undefined} style={onNoteClick ? { cursor: "pointer" } : undefined}>
              <rect x={x(i) - w / 2} y={yy - h / 2} width={w} height={h} rx={4} fill={fill} stroke={p.grace ? "#777" : "#333"} strokeWidth={1} />
              <text x={x(i)} y={yy + (p.grace ? 4 : 5)} fontSize={fs} textAnchor="middle" fill="#111">
                {p.fret}
              </text>
              {o.showFingers && !o.compact && (
                <text x={x(i)} y={top + staffH + 16} fontSize={10} textAnchor="middle" fill={COLORS.finger}>
                  {fingerStr(p)}
                </text>
              )}
            </g>
          );
        })}
        {/* playhead (moved imperatively by the player) */}
        <line ref={playheadRef} x1={GEO.left} y1={top - 2} x2={GEO.left} y2={top + staffH + 2} stroke={COLORS.up} strokeWidth={2} opacity={0} />
        {/* legend */}
        {!o.compact && o.showLegend && (
          <g>
            <text x={GEO.left - 24} y={top + staffH + 44} fontSize={11} fill="#666">
              ⊓ down/rest-stroke   ∨ up (parity)   H hammer-on   P pull-off   fingers: 0=open 1-4 *=stretch
            </text>
            {totalCost !== null && totalCost !== undefined && (
              <text x={GEO.left - 24} y={top + staffH + 60} fontSize={11} fill="#666">
                total cost {totalCost}
              </text>
            )}
          </g>
        )}
      </svg>
    </div>
  );
}
