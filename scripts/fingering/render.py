"""Human-facing output: the per-note table, an ASCII tab, the flag list, the
cost breakdown, and a SoundSlice-style SVG/HTML tab with cell and chord-tone
labels above the staff (and an optional Web-Audio play-along with a playhead).
"""

from __future__ import annotations

import html
from typing import List, Optional

from scripts.fingering.config import FingeringConfig
from scripts.fingering.costs import DOWN, UP, PULL, HAMMER, PlacedNote
from scripts.fingering.pitch import Note
from scripts.fingering.chords import chord_for_beat

# ASCII / glyph picking marks.
_GLYPH = {DOWN: "⊓", UP: "∨", PULL: "p", HAMMER: "h"}  # ⊓  ∨  p  h


def _glyph(stroke: str) -> str:
    return _GLYPH.get(stroke, stroke)


def _finger_str(p: PlacedNote) -> str:
    if p.finger == 0:
        return "0"
    return f"{p.finger}{'*' if p.is_stretch else ''}"


def _label(note: Note) -> str:
    return note.degree or note.role or ""


# --------------------------------------------------------------------------- #
# Text report
# --------------------------------------------------------------------------- #
def format_note_table(placed: List[PlacedNote]) -> str:
    hdr = f"{'#':>2}  {'beat':>4}  {'pitch':<5}  {'role/deg':<10}  {'str':>3}  {'fret':>4}  {'fin':>4}  {'stk':>3}  {'rest?':>5}"
    lines = [hdr, "-" * len(hdr)]
    for i, p in enumerate(placed):
        lines.append(
            f"{i:>2}  {p.beat:>4g}  {p.note.name:<5}  {_label(p.note):<10}  "
            f"{p.string:>3}  {p.fret:>4}  {_finger_str(p):>4}  {_glyph(p.stroke):>3}  "
            f"{'Y' if p.is_rest_stroke else 'N':>5}"
        )
    return "\n".join(lines)


def _bar_index(p, beats_per_bar: int) -> int:
    return int(p.note.onset // beats_per_bar)


def format_tab_ascii(placed: List[PlacedNote], beats_per_bar: int = 4) -> str:
    """6-line tab, string 1 (high E) on top, picking marks above, bar lines."""
    n = len(placed)
    w = 4  # column width
    # picking + label rows
    pick_row = " " * 4
    deg_row = " " * 4
    cols = {s: [] for s in range(1, 7)}
    for i, p in enumerate(placed):
        sep = "|" if (i > 0 and _bar_index(p, beats_per_bar)
                      > _bar_index(placed[i - 1], beats_per_bar)) else ""
        pad = w - len(sep)
        pick_row += sep + _glyph(p.stroke).center(pad)
        deg_row += sep + (_label(p.note)[:pad]).center(pad)
        for s in range(1, 7):
            cell = str(p.fret) if s == p.string else "-"
            fill = "-" if s != p.string else "-"
            cols[s].append((sep, cell.center(pad, "-") if s == p.string else "-" * pad))
    lines = [f"deg: {deg_row.rstrip()}", f"pick:{pick_row.rstrip()}"]
    string_names = {1: "e", 2: "B", 3: "G", 4: "D", 5: "A", 6: "E"}
    for s in range(1, 7):  # top = string 1
        row = f"{string_names[s]}|--"
        for sep, cellstr in cols[s]:
            row += sep + cellstr
        lines.append(row)
    lines.append("  (⊓ = downstroke/rest-stroke, ∨ = upstroke, p = pull-off, h = hammer-on)")
    return "\n".join(lines)


def _top_contributors(voicing, k: int = 3) -> List:
    return [(t, a) for t, a in voicing.contributions if a > 0][:k]


def format_report(result) -> str:
    cfg = result.config
    out: List[str] = []
    out.append("=" * 74)
    key = result.context.get("key", "?")
    out.append(f"FINGERING + PICKING  (key {key})   notes: {len(result.notes)}   "
               f"total cost: {result.best.total_cost}")
    out.append("=" * 74)

    for w in result.warnings:
        out.append(f"!! {w}")
    if result.warnings:
        out.append("")

    out.append("PHASE 1 (100% picked, orthodox Gypsy rest-strokes):")
    out.append(format_note_table(result.best.placed))
    out.append("")
    out.append(format_tab_ascii(result.best.placed, cfg.beats_per_bar))
    out.append("")

    out.append("FLAGS:")
    if result.best.flags:
        for f in result.best.flags:
            out.append(f"  - {f}")
    else:
        out.append("  (none — clean 2npS, all downbeats on D, no drops)")
    out.append("")

    n_up = sum(1 for p in result.best.placed if p.stroke == UP)
    n_desc = sum(
        1 for i in range(len(result.best.placed) - 1)
        if result.best.placed[i + 1].string > result.best.placed[i].string
    )
    out.append(f"Upstrokes: {n_up}   Descending crossings: {n_desc}   "
               f"(invariant: every U precedes a descending crossing)")
    out.append(f"Total cost: {result.best.total_cost}")
    top = _top_contributors(result.best)
    if top:
        out.append("Top cost contributors (debug by ear): " +
                   ", ".join(f"{t}={a:.2f}" for t, a in top))
    out.append("")

    if result.alternate is not None:
        out.append("-" * 74)
        out.append(f"ALTERNATE VOICING (within alt_margin={cfg.alt_margin}, "
                   f"cost {result.alternate.total_cost}):")
        out.append(format_note_table(result.alternate.placed))
        out.append("")

    if cfg.ornament_engine_enabled:
        out.append("-" * 74)
        out.append("PHASE 2 — ORNAMENT SUGGESTIONS (marked suggestions, not applied):")
        if not result.ornaments:
            out.append("  (no eligible drop sites, or no candidate converts the crossing)")
        for orn in result.ornaments:
            out.append(
                f"  * bar {orn['bar']} note {orn['target_index']} "
                f"(target {orn['target_pitch']}, {orn['gate']}"
                + (f", chord {orn['chord']}" if orn['chord'] else "") + "):")
            out.append(f"      ornament : {orn['ornament']}")
            out.append(f"      parity   : {orn['parity_before']}  =>  {orn['parity_after']}")
            out.append(f"      picks    : {orn['picks_before']} -> {orn['picks_after']}  "
                       f"(added: " +
                       ", ".join(f"{a['name']}[{a['stroke']}]" for a in orn['added_notes']) + ")")
            considered = ", ".join(
                f"{c['name'].split('(')[0].strip()}:{c['result']}"
                for c in orn['all_candidates'])
            out.append(f"      computed : {considered}")
        out.append("")

    out.append("=" * 74)
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# SoundSlice-style SVG + HTML
# --------------------------------------------------------------------------- #
_STRING_Y = {1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5}  # row order, string 1 on top
_STRING_NAME = {1: "e", 2: "B", 3: "G", 4: "D", 5: "A", 6: "E"}


def _cell_spans(notes: List[Note]):
    """Group consecutive notes sharing a cell name -> (start, end_inclusive, name)."""
    spans = []
    i = 0
    while i < len(notes):
        cell = notes[i].cell
        if cell is None:
            i += 1
            continue
        j = i
        while j + 1 < len(notes) and notes[j + 1].cell == cell:
            j += 1
        spans.append((i, j, cell))
        i = j + 1
    return spans


def render_svg(result, tempo: int = 160) -> str:
    placed = result.best.placed
    notes = result.notes
    cfg = result.config
    bpb = cfg.beats_per_bar

    left = 70
    col = 62
    top = 96          # room for chord + cell + degree lanes
    row_h = 26
    n = len(placed)
    width = left + col * n + 40
    staff_h = row_h * 5
    height = top + staff_h + 90

    def x(i):
        return left + col * i + col // 2

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'font-family="Menlo,Consolas,monospace" viewBox="0 0 {width} {height}">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#fbfaf7"/>',
    ]

    # ---- chord lane -------------------------------------------------------
    last_chord = None
    for i in range(n):
        sym = chord_for_beat(result.context, placed[i].note.onset, bpb)
        if sym and sym != last_chord:
            parts.append(
                f'<text x="{x(i)}" y="22" fill="#1a3a8f" font-size="15" '
                f'font-weight="bold" text-anchor="middle">{html.escape(sym)}</text>')
            last_chord = sym

    # ---- cell-name brackets ----------------------------------------------
    for (a, b, name) in _cell_spans(notes):
        x0, x1 = x(a) - col // 2 + 6, x(b) + col // 2 - 6
        y = 40
        parts.append(
            f'<path d="M{x0},{y+6} L{x0},{y} L{x1},{y} L{x1},{y+6}" '
            f'stroke="#b06a00" fill="none" stroke-width="1.4"/>')
        parts.append(
            f'<text x="{(x0+x1)/2}" y="{y-3}" fill="#b06a00" font-size="11" '
            f'text-anchor="middle">{html.escape(str(name))}</text>')

    # ---- degree / role labels + picking marks ----------------------------
    for i, p in enumerate(placed):
        lab = _label(p.note)
        if lab:
            parts.append(
                f'<text x="{x(i)}" y="64" fill="#3a7d3a" font-size="12" '
                f'text-anchor="middle">{html.escape(lab)}</text>')
        # picking glyph just above the staff
        parts.append(
            f'<text x="{x(i)}" y="{top-6}" font-size="15" text-anchor="middle" '
            f'fill="{"#c0392b" if p.stroke == UP else "#222"}">{_glyph(p.stroke)}</text>')

    # ---- staff lines + string labels -------------------------------------
    for s in range(1, 7):
        yy = top + _STRING_Y[s] * row_h
        parts.append(
            f'<line x1="{left-10}" y1="{yy}" x2="{left+col*n}" y2="{yy}" '
            f'stroke="#cfc9bd" stroke-width="1"/>')
        parts.append(
            f'<text x="{left-24}" y="{yy+4}" font-size="12" fill="#888">'
            f'{_STRING_NAME[s]}</text>')

    # ---- bar lines (from real onsets) --------------------------------------
    bar_cols = [0] + [i for i in range(1, n)
                      if _bar_index(placed[i], bpb) > _bar_index(placed[i - 1], bpb)] + [n]
    for i in bar_cols:
        bx = left + col * i
        parts.append(
            f'<line x1="{bx}" y1="{top}" x2="{bx}" y2="{top+staff_h}" '
            f'stroke="#9a9384" stroke-width="1.5"/>')

    # ---- fret numbers on the string, boxed like SoundSlice ----------------
    for i, p in enumerate(placed):
        yy = top + _STRING_Y[p.string] * row_h
        fill = "#fdeaea" if p.stroke == UP else "#ffffff"
        parts.append(
            f'<rect x="{x(i)-12}" y="{yy-11}" width="24" height="22" rx="4" '
            f'fill="{fill}" stroke="#333" stroke-width="1"/>')
        parts.append(
            f'<text x="{x(i)}" y="{yy+5}" font-size="13" text-anchor="middle" '
            f'fill="#111">{p.fret}</text>')
        # small finger annotation under staff
        parts.append(
            f'<text x="{x(i)}" y="{top+staff_h+16}" font-size="10" '
            f'text-anchor="middle" fill="#777">{_finger_str(p)}</text>')

    # ---- playhead (animated by JS) ---------------------------------------
    parts.append(
        f'<line id="playhead" x1="{left}" y1="{top-2}" x2="{left}" '
        f'y2="{top+staff_h+2}" stroke="#c0392b" stroke-width="2" '
        f'opacity="0" />')

    # ---- legend -----------------------------------------------------------
    ly = top + staff_h + 44
    parts.append(
        f'<text x="{left-24}" y="{ly}" font-size="11" fill="#666">'
        f'⊓ down/rest-stroke   ∨ up (parity)   fingers: 0=open 1-4 *=stretch'
        f'</text>')
    parts.append(
        f'<text x="{left-24}" y="{ly+16}" font-size="11" fill="#666">'
        f'total cost {result.best.total_cost}'
        + (f"   |   {len(result.ornaments)} ornament suggestion(s)"
           if cfg.ornament_engine_enabled else "")
        + '</text>')

    parts.append("</svg>")
    return "\n".join(parts)


def render_html(result, tempo: int = 160) -> str:
    """SVG tab plus a Web-Audio 'play with moving playhead' button (SoundSlice feel)."""
    svg = render_svg(result, tempo)
    midis = [p.note.midi for p in result.best.placed]
    cfg = result.config
    left = 70
    col = 62
    # note x-centres for the playhead
    xs = [left + col * i + col // 2 for i in range(len(midis))]
    beat_ms = int(60000 / max(1, tempo))
    import json as _json
    return f"""<!doctype html><html><head><meta charset="utf-8"></head>
<body style="margin:0;background:#fbfaf7;font-family:Menlo,monospace">
<div style="padding:8px">
  <button id="play" style="font-size:14px;padding:6px 14px;border-radius:6px;
    border:1px solid #333;background:#fff;cursor:pointer">&#9654; Play</button>
  <label style="margin-left:12px;font-size:13px">tempo
    <input id="tempo" type="number" value="{tempo}" min="30" max="300"
      style="width:60px"></label>
</div>
<div id="tab">{svg}</div>
<script>
const MIDIS = {_json.dumps(midis)};
const XS = {_json.dumps(xs)};
const BASE_BEAT_MS = {beat_ms};
let ctx = null;
function freq(m){{return 440*Math.pow(2,(m-69)/12);}}
document.getElementById('play').onclick = function(){{
  const tempo = parseInt(document.getElementById('tempo').value)||{tempo};
  const beat = 60000/tempo;
  ctx = ctx || new (window.AudioContext||window.webkitAudioContext)();
  const head = document.getElementById('playhead');
  const t0 = ctx.currentTime;
  MIDIS.forEach((m,i)=>{{
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.type='triangle'; o.frequency.value=freq(m);
    const s = t0 + i*beat/1000;
    g.gain.setValueAtTime(0.0001,s);
    g.gain.exponentialRampToValueAtTime(0.25,s+0.01);
    g.gain.exponentialRampToValueAtTime(0.0001,s+beat/1000*0.9);
    o.connect(g); g.connect(ctx.destination); o.start(s); o.stop(s+beat/1000);
  }});
  head.setAttribute('opacity','1');
  MIDIS.forEach((m,i)=>{{
    setTimeout(()=>{{head.setAttribute('x1',XS[i]);head.setAttribute('x2',XS[i]);}}, i*beat);
  }});
  setTimeout(()=>head.setAttribute('opacity','0'), MIDIS.length*beat+150);
}};
</script>
</body></html>"""
