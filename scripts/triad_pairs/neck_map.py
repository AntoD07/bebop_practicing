"""Fretboard map of a triad pair — the whole neck, or a named position's box.

A pure-SVG diagram: 6 strings (high e on top, like the tab), frets 0..``max_fret``
left to right, every tone of the pair marked with its triad's colour. A shared
tone is a two-colour disc, a triad root wears a dark ring, and an open-string
tone is hollow (it is on the neck, but the fretted engine never plays it).

With ``boxes`` (from :func:`position_map_boxes`) the position's hand box(es)
are drawn — the hard box solid, the ±slack tolerance dashed — and tones outside
them fade, so the player sees exactly what the "Enforce the position" exercises
may use.
"""

from __future__ import annotations

import html
from typing import List, Optional, Tuple

from scripts.fingering.config import FingeringConfig, STANDARD_TUNING_MIDI
from scripts.fingering.positions import position_boxes
from scripts.triad_pairs.triads import TriadPair

# first / second triad
TRIAD_COLOURS = ("#2962b3", "#d9822b")
_BOX_COLOUR = "#3a7d3a"
_STRING_NAME = {1: "e", 2: "B", 3: "G", 4: "D", 5: "A", 6: "E"}
_INLAYS = {3: 1, 5: 1, 7: 1, 9: 1, 12: 2, 15: 1}

Box = Tuple[int, int, Tuple[int, ...]]  # (lo fret, hi fret, strings)


def neck_markers(pair: TriadPair, max_fret: int = 15) -> List[dict]:
    """Every (string, fret) up to ``max_fret`` sounding a tone of the pair."""
    root_pcs = tuple(t.root_pc for t in pair.triads)
    out = []
    for s in range(1, 7):
        for f in range(0, max_fret + 1):
            midi = STANDARD_TUNING_MIDI[s] + f
            pc = midi % 12
            members = tuple(i for i, t in enumerate(pair.triads) if pc in t.pcs)
            if not members:
                continue
            owner = members[0]
            out.append({
                "string": s, "fret": f, "midi": midi, "pc": pc, "triads": members,
                "name": pair.name_for(pc),
                "degree": pair.triads[owner].degree_of(pc),
                "roots": tuple(i for i in members if pc == root_pcs[i]),
            })
    return out


def position_map_boxes(position: str, key: str,
                       base_cfg: Optional[FingeringConfig] = None) -> List[Box]:
    """The hand box(es) of a named position for a KEY: ``(lo, hi, strings)`` per
    octave of the shape (root fret, and 12 frets up when on the neck)."""
    out: List[Box] = []
    for cfg, _root_midi in position_boxes(position, key, base_cfg):
        lo, hi = cfg.fret_window
        out.append((lo, hi, tuple(cfg.string_range)))
    return out


def _in_box(f: int, s: int, boxes: List[Box], slack: int = 0) -> bool:
    # Boxes are fretted hand positions: the open column never belongs to one.
    if f == 0:
        return False
    return any(lo - slack <= f <= hi + slack and s in strings for lo, hi, strings in boxes)


def render_neck_svg(pair: TriadPair, boxes: Optional[List[Box]] = None,
                    labels: str = "name", max_fret: int = 15, slack: int = 0,
                    title: str = "") -> str:
    """The SVG neck map; ``labels`` = ``"name"`` (note names) or ``"degree"``
    (chord degree within the owning triad). Responsive: scales to its container."""
    markers = neck_markers(pair, max_fret)
    col_w, row_h = 46, 24
    left, top = 44, 46 if (boxes or title) else 26
    n_cols = max_fret + 1
    right = left + n_cols * col_w
    bottom = top + 5 * row_h
    height = bottom + 62
    width = right + 16

    def cx(f):
        return left + f * col_w + col_w / 2

    def cy(s):
        return top + (s - 1) * row_h

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="Menlo,Consolas,monospace" '
        f'style="max-width:100%;height:auto;display:block">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#fbfaf7"/>',
    ]
    if title:
        parts.append(f'<text x="{left}" y="18" font-size="13" fill="#333" '
                     f'font-weight="bold">{html.escape(title)}</text>')

    # ---- position boxes (under everything) ------------------------------
    for lo, hi, strings in boxes or []:
        lo_draw = max(lo, 1)
        if hi < lo_draw:
            continue
        s_min, s_max = min(strings), max(strings)
        # The ±slack tolerance band (dashed, faint) under the hard box (solid).
        layers = ([(slack, "6,4", 0.05)] if slack else []) + [(0, None, 0.12)]
        for tol, dash, op in layers:
            lo_t, hi_t = max(1, lo_draw - tol), min(max_fret, hi + tol)
            x0, x1 = left + lo_t * col_w, left + (hi_t + 1) * col_w
            y0, y1 = cy(s_min) - row_h / 2 - 2, cy(s_max) + row_h / 2 + 2
            parts.append(
                f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" rx="6" '
                f'fill="{_BOX_COLOUR}" fill-opacity="{op}" stroke="{_BOX_COLOUR}" '
                f'stroke-width="1.5"' + (f' stroke-dasharray="{dash}"' if dash else "") + '/>')
        # Label above the top string (the box may not reach string 1), clamped
        # to the drawn neck (a horizontal shape's window can run past it).
        parts.append(
            f'<text x="{left + lo_draw * col_w + 4}" y="{cy(1) - row_h / 2 - 7}" '
            f'font-size="11" fill="{_BOX_COLOUR}" font-weight="bold">'
            f'frets {lo_draw}–{min(hi, max_fret)}</text>')

    # ---- inlays, frets, nut, strings ------------------------------------
    for f, n_dots in _INLAYS.items():
        if f > max_fret:
            continue
        ys = ((cy(3) + cy(4)) / 2,) if n_dots == 1 else ((cy(2) + cy(3)) / 2, (cy(4) + cy(5)) / 2)
        for yy in ys:
            parts.append(f'<circle cx="{cx(f)}" cy="{yy}" r="5" fill="#e4ded2"/>')
    for f in range(1, n_cols + 1):  # fret wires at the right edge of each column
        xx = left + f * col_w
        parts.append(f'<line x1="{xx}" y1="{cy(1)}" x2="{xx}" y2="{cy(6)}" '
                     f'stroke="#b9b2a4" stroke-width="1"/>')
    nut = left + col_w
    parts.append(f'<line x1="{nut}" y1="{cy(1) - 2}" x2="{nut}" y2="{cy(6) + 2}" '
                 f'stroke="#444" stroke-width="4"/>')
    for s in range(1, 7):
        parts.append(f'<line x1="{left}" y1="{cy(s)}" x2="{right}" y2="{cy(s)}" '
                     f'stroke="#8f887a" stroke-width="{0.8 + 0.25 * s}"/>')
        parts.append(f'<text x="{left - 14}" y="{cy(s) + 4}" font-size="11" fill="#888" '
                     f'text-anchor="middle">{_STRING_NAME[s]}</text>')
    for f in range(0, n_cols):
        parts.append(f'<text x="{cx(f)}" y="{bottom + 20}" font-size="10" fill="#777" '
                     f'text-anchor="middle">{"open" if f == 0 else f}</text>')

    # ---- markers ---------------------------------------------------------
    r = 10.5
    for m in markers:
        s, f = m["string"], m["fret"]
        x, y = cx(f), cy(s)
        c1 = TRIAD_COLOURS[m["triads"][0]]
        if boxes is None:
            op = 1.0
        elif _in_box(f, s, boxes):
            op = 1.0
        elif slack and _in_box(f, s, boxes, slack):
            op = 0.55
        else:
            op = 0.18
        ring = "#222" if m["roots"] else "#fff"
        ring_w = 2.4 if m["roots"] else 1.0
        parts.append(f'<g opacity="{op}">')
        if f == 0:  # open string: hollow
            parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#fbfaf7" '
                         f'stroke="{c1}" stroke-width="2"/>')
            txt_fill = c1
        else:
            parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{c1}"/>')
            if len(m["triads"]) > 1:  # shared tone: right half in the other colour
                c2 = TRIAD_COLOURS[m["triads"][1]]
                parts.append(f'<path d="M{x},{y - r} A{r},{r} 0 0 1 {x},{y + r} Z" fill="{c2}"/>')
            parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="none" '
                         f'stroke="{ring}" stroke-width="{ring_w}"/>')
            txt_fill = "#fff"
        txt = m["name"] if labels == "name" else (m["degree"] or "")
        parts.append(f'<text x="{x}" y="{y + 3.5}" font-size="{9 if len(txt) > 1 else 10}" '
                     f'font-weight="bold" fill="{txt_fill}" text-anchor="middle">'
                     f'{html.escape(txt)}</text>')
        parts.append('</g>')

    # ---- legend ----------------------------------------------------------
    ly = bottom + 44
    lx = left
    for i, t in enumerate(pair.triads):
        parts.append(f'<circle cx="{lx + 6}" cy="{ly - 4}" r="6" fill="{TRIAD_COLOURS[i]}"/>')
        parts.append(f'<text x="{lx + 17}" y="{ly}" font-size="11" fill="#444">'
                     f'{html.escape(t.symbol)}  ({html.escape(" ".join(t.names))})</text>')
        lx += 17 + 7 * (len(t.symbol) + len(" ".join(t.names)) + 4) + 18
    parts.append(f'<circle cx="{lx + 6}" cy="{ly - 4}" r="6" fill="none" stroke="#222" '
                 f'stroke-width="2"/>')
    parts.append(f'<text x="{lx + 17}" y="{ly}" font-size="11" fill="#444">root</text>')
    lx += 17 + 7 * 4 + 18
    if pair.common_pcs:
        parts.append(f'<circle cx="{lx + 6}" cy="{ly - 4}" r="6" fill="{TRIAD_COLOURS[0]}"/>')
        parts.append(f'<path d="M{lx + 6},{ly - 10} A6,6 0 0 1 {lx + 6},{ly + 2} Z" '
                     f'fill="{TRIAD_COLOURS[1]}"/>')
        parts.append(f'<text x="{lx + 17}" y="{ly}" font-size="11" fill="#444">shared tone</text>')
        lx += 17 + 7 * 11 + 18
    parts.append(f'<circle cx="{lx + 6}" cy="{ly - 4}" r="6" fill="#fbfaf7" stroke="#888" '
                 f'stroke-width="1.5"/>')
    parts.append(f'<text x="{lx + 17}" y="{ly}" font-size="11" fill="#444">'
                 f'open string (never fingered)</text>')
    parts.append("</svg>")
    return "\n".join(parts)
