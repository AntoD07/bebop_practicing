"use client";

import type { TriadPairJSON } from "@/lib/engine/types";

type Box = { fret_lo: number; fret_hi: number; strings: number[] };
const STRING_NAME: Record<number, string> = { 1: "e", 2: "B", 3: "G", 4: "D", 5: "A", 6: "E" };
const INLAYS: Record<number, number> = { 3: 1, 5: 1, 7: 1, 9: 1, 12: 2, 15: 1 };
const BOX_COLOUR = "#3a7d3a";

function inBox(f: number, s: number, boxes: Box[], slack = 0) {
  if (f === 0) return false; // the open column never belongs to a hand box
  return boxes.some((b) => b.fret_lo - slack <= f && f <= b.fret_hi + slack && b.strings.includes(s));
}

/** Pure-SVG fretboard map of a triad pair (port of scripts/triad_pairs/neck_map.py):
 * high e on top, every tone coloured by triad, shared tones two-colour, roots
 * ringed, open strings hollow; with `boxes` the position's hand box is drawn
 * (solid) with the ±slack band (dashed) and out-of-box tones faded. */
export function NeckMap({ pair, boxes, labels = "name", maxFret = 15, slack = 0, title }: { pair: TriadPairJSON; boxes?: Box[] | null; labels?: "name" | "degree"; maxFret?: number; slack?: number; title?: string }) {
  const colW = 46;
  const rowH = 24;
  const left = 44;
  const top = boxes || title ? 46 : 26;
  const nCols = maxFret + 1;
  const right = left + nCols * colW;
  const bottom = top + 5 * rowH;
  const height = bottom + 62;
  const width = right + 16;
  const cx = (f: number) => left + f * colW + colW / 2;
  const cy = (s: number) => top + (s - 1) * rowH;
  const markers = pair.markers.filter((m) => m.fret <= maxFret);
  const colours = pair.colours;
  return (
    <div className="overflow-x-auto touch-pan-x">
      <svg xmlns="http://www.w3.org/2000/svg" width={width} height={height} viewBox={`0 0 ${width} ${height}`} fontFamily="Menlo,Consolas,monospace" className="block max-w-full" role="img" aria-label="fretboard map">
        <rect x={0} y={0} width={width} height={height} fill="#fbfaf7" />
        {title && (
          <text x={left} y={18} fontSize={13} fill="#333" fontWeight="bold">
            {title}
          </text>
        )}
        {(boxes ?? []).map((b, k) => {
          const loDraw = Math.max(b.fret_lo, 1);
          if (b.fret_hi < loDraw) return null;
          const sMin = Math.min(...b.strings);
          const sMax = Math.max(...b.strings);
          const layers: [number, string | null, number][] = slack ? [[slack, "6,4", 0.05], [0, null, 0.12]] : [[0, null, 0.12]];
          return (
            <g key={k}>
              {layers.map(([tol, dash, op], j) => {
                const loT = Math.max(1, loDraw - tol);
                const hiT = Math.min(maxFret, b.fret_hi + tol);
                const x0 = left + loT * colW;
                const x1 = left + (hiT + 1) * colW;
                const y0 = cy(sMin) - rowH / 2 - 2;
                const y1 = cy(sMax) + rowH / 2 + 2;
                return <rect key={j} x={x0} y={y0} width={x1 - x0} height={y1 - y0} rx={6} fill={BOX_COLOUR} fillOpacity={op} stroke={BOX_COLOUR} strokeWidth={1.5} strokeDasharray={dash ?? undefined} />;
              })}
              <text x={left + loDraw * colW + 4} y={cy(1) - rowH / 2 - 7} fontSize={11} fill={BOX_COLOUR} fontWeight="bold">
                frets {loDraw}–{Math.min(b.fret_hi, maxFret)}
              </text>
            </g>
          );
        })}
        {Object.entries(INLAYS).map(([f, n]) => {
          const fret = Number(f);
          if (fret > maxFret) return null;
          const ys = n === 1 ? [(cy(3) + cy(4)) / 2] : [(cy(2) + cy(3)) / 2, (cy(4) + cy(5)) / 2];
          return ys.map((yy, i) => <circle key={`${f}-${i}`} cx={cx(fret)} cy={yy} r={5} fill="#e4ded2" />);
        })}
        {Array.from({ length: nCols }, (_, i) => i + 1).map((f) => (
          <line key={`fw${f}`} x1={left + f * colW} y1={cy(1)} x2={left + f * colW} y2={cy(6)} stroke="#b9b2a4" strokeWidth={1} />
        ))}
        <line x1={left + colW} y1={cy(1) - 2} x2={left + colW} y2={cy(6) + 2} stroke="#444" strokeWidth={4} />
        {[1, 2, 3, 4, 5, 6].map((s) => (
          <g key={`s${s}`}>
            <line x1={left} y1={cy(s)} x2={right} y2={cy(s)} stroke="#8f887a" strokeWidth={0.8 + 0.25 * s} />
            <text x={left - 14} y={cy(s) + 4} fontSize={11} fill="#888" textAnchor="middle">
              {STRING_NAME[s]}
            </text>
          </g>
        ))}
        {Array.from({ length: nCols }, (_, f) => (
          <text key={`fn${f}`} x={cx(f)} y={bottom + 20} fontSize={10} fill="#777" textAnchor="middle">
            {f === 0 ? "open" : f}
          </text>
        ))}
        {markers.map((m, i) => {
          const x = cx(m.fret);
          const y = cy(m.string);
          const c1 = colours[m.triads[0]];
          const r = 10.5;
          const op = !boxes ? 1 : inBox(m.fret, m.string, boxes) ? 1 : slack && inBox(m.fret, m.string, boxes, slack) ? 0.55 : 0.18;
          const ring = m.roots.length ? "#222" : "#fff";
          const txt = labels === "name" ? m.name : (m.degree ?? "");
          return (
            <g key={i} opacity={op}>
              {m.fret === 0 ? (
                <circle cx={x} cy={y} r={r} fill="#fbfaf7" stroke={c1} strokeWidth={2} />
              ) : (
                <>
                  <circle cx={x} cy={y} r={r} fill={c1} />
                  {m.triads.length > 1 && <path d={`M${x},${y - r} A${r},${r} 0 0 1 ${x},${y + r} Z`} fill={colours[m.triads[1]]} />}
                  <circle cx={x} cy={y} r={r} fill="none" stroke={ring} strokeWidth={m.roots.length ? 2.4 : 1} />
                </>
              )}
              <text x={x} y={y + 3.5} fontSize={txt.length > 1 ? 9 : 10} fontWeight="bold" fill={m.fret === 0 ? c1 : "#fff"} textAnchor="middle">
                {txt}
              </text>
            </g>
          );
        })}
        {/* legend */}
        <g>
          {pair.triads.map((t, i) => (
            <g key={i} transform={`translate(${left + i * 170}, ${bottom + 44})`}>
              <circle cx={6} cy={-4} r={6} fill={colours[i]} />
              <text x={17} y={0} fontSize={11} fill="#444">
                {t.symbol} ({t.names.join(" ")})
              </text>
            </g>
          ))}
          <g transform={`translate(${left + 340}, ${bottom + 44})`}>
            <circle cx={6} cy={-4} r={6} fill="none" stroke="#222" strokeWidth={2} />
            <text x={17} y={0} fontSize={11} fill="#444">
              root
            </text>
          </g>
          <g transform={`translate(${left + 400}, ${bottom + 44})`}>
            <circle cx={6} cy={-4} r={6} fill="#fbfaf7" stroke="#888" strokeWidth={1.5} />
            <text x={17} y={0} fontSize={11} fill="#444">
              open string (never fingered)
            </text>
          </g>
        </g>
      </svg>
    </div>
  );
}
